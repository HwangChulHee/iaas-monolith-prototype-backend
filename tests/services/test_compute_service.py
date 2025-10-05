

# tests/services/test_compute_service.py
import pytest
import libvirt
import sqlite3
from unittest.mock import patch, MagicMock, call
from datetime import datetime

from services.image_service import ImageService
from src.services.compute_service import (
    ComputeService, 
    VmNotFoundError,
    VmAlreadyExistsError,
    ImageNotFoundError,
    VmCreationError
)


# 테스트용 가짜 libvirt 도메인 객체
class FakeDomain:
    def __init__(self, name, uuid, state_code=libvirt.VIR_DOMAIN_RUNNING):
        self._name = name
        self._uuid = uuid
        self._state_code = state_code

    def name(self):
        return self._name

    def UUIDString(self):
        return self._uuid

    def info(self):
        # state, maxmem, memory, vcpus, cputime
        return [self._state_code, 2048, 1024, 2, 5000000000]

    def isActive(self):
        return self._state_code == libvirt.VIR_DOMAIN_RUNNING

    def create(self):
        return 0

    def destroy(self):
        self._state_code = libvirt.VIR_DOMAIN_SHUTOFF
        return 0

    def undefine(self):
        return 0


@pytest.fixture
def mock_db_connector():
    """DBConnector를 모킹하여 connection 객체를 반환합니다."""
    with patch("src.services.compute_service.DBConnector") as mock_db_class:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn


@pytest.fixture
def mock_libvirt():
    """libvirt.open 함수만 모킹하여 실제 하이퍼바이저 연결을 방지합니다."""
    with patch("src.services.compute_service.libvirt.open") as mock_open:
        mock_conn = MagicMock()
        mock_open.return_value = mock_conn
        yield mock_conn


@pytest.fixture
def compute_service(mock_libvirt):
    """테스트를 위한 ComputeService 인스턴스를 생성합니다."""
    return ComputeService()


# ===================================================================
#  create_vm 테스트
# ===================================================================
class TestCreateVm:
    VM_DEFAULTS = {
        "project_id": 1,
        "vm_name": "new-test-vm",
        "cpu_count": 2,
        "ram_mb": 2048,
        "image_name": "Ubuntu-Base-22.04",
        "base_image_path": "/var/lib/libvirt/images/ubuntu-base.qcow2",
        "new_disk_path": "/var/lib/libvirt/images/new-test-vm.qcow2",
        "test_uuid": "a-real-uuid-from-test",
        "dummy_xml": "<domain>...</domain>",
        "fake_now": datetime(2025, 10, 4, 12, 0, 0),
    }

    @patch.object(ComputeService, '_rollback_vm_creation')
    @patch.object(ComputeService, '_save_vm_metadata_to_db')
    @patch.object(ComputeService, '_validate_vm_and_get_image_path')
    @patch("src.services.compute_service.ImageService", autospec=True)
    @patch("src.services.compute_service.generate_vm_xml")
    @patch("src.services.compute_service.uuid")
    def test_create_vm_success(
        self,
        mock_uuid,
        mock_generate_xml,
        mock_image_service,
        mock_validate,
        mock_save_db,
        mock_rollback,
        compute_service,
        mock_libvirt,
    ):
        """VM 생성 성공 시나리오 (Happy Path)를 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_validate.return_value = args["base_image_path"]
        mock_uuid.uuid4.return_value = args["test_uuid"]
        mock_image_service.create_vm_disk.return_value = args["new_disk_path"]
        mock_generate_xml.return_value = args["dummy_xml"]

        mock_domain = MagicMock()
        mock_libvirt.defineXML.return_value = mock_domain
        mock_domain.create.return_value = 0

        # Act
        result_name, result_uuid = compute_service.create_vm(
            args["project_id"], args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
        )

        # Assert
        assert result_name == args["vm_name"]
        assert result_uuid == args["test_uuid"]

        mock_validate.assert_called_once_with(args["project_id"], args["vm_name"], args["image_name"])
        mock_save_db.assert_called_once_with(
            args["project_id"], args["vm_name"], args["test_uuid"], args["cpu_count"], args["ram_mb"]
        )
        mock_rollback.assert_not_called()

    @patch.object(ComputeService, '_rollback_vm_creation')
    def test_create_vm_fails_if_name_exists(self, mock_rollback, compute_service, mock_db_connector):
        """DB에 VM 이름이 이미 존재할 경우 VmAlreadyExistsError 예외가 발생하는지 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = (1,)

        # Act & Assert
        with pytest.raises(VmAlreadyExistsError) as excinfo:
            compute_service.create_vm(
                args["project_id"], args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert "already exists in this project" in str(excinfo.value)
        mock_rollback.assert_not_called()


# ===================================================================
#  list_vms 테스트
# ===================================================================
class TestListVms:
    def test_list_vms_empty(self, compute_service, mock_db_connector):
        """DB에 VM이 없을 때 빈 리스트를 반환하는지 테스트합니다."""
        # Arrange
        project_id = 1
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = []

        # Act
        vms = compute_service.list_vms(project_id)

        # Assert
        assert vms == []
        mock_cursor.execute.assert_called_once_with(
            "SELECT name, uuid, cpu_count, ram_mb, created_at FROM vms WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,)
        )

    def test_list_vms_with_data(self, compute_service, mock_db_connector, mock_libvirt):
        """DB에 VM이 있을 때 libvirt에서 상태를 가져와 통합된 목록을 반환하는지 테스트합니다."""
        # Arrange
        project_id = 1
        mock_cursor = mock_db_connector.cursor()
        db_vms = [
            {'name': 'test-vm-1', 'uuid': 'uuid-1', 'cpu_count': 2, 'ram_mb': 2048, 'created_at': '2025-10-04'},
            {'name': 'test-vm-2', 'uuid': 'uuid-2', 'cpu_count': 1, 'ram_mb': 1024, 'created_at': '2025-10-03'}
        ]
        mock_cursor.fetchall.return_value = [dict(row) for row in db_vms]

        fake_domain_1 = FakeDomain('test-vm-1', 'uuid-1', libvirt.VIR_DOMAIN_RUNNING)
        fake_domain_2 = FakeDomain('test-vm-2', 'uuid-2', libvirt.VIR_DOMAIN_SHUTOFF)
        mock_libvirt.lookupByUUIDString.side_effect = [fake_domain_1, fake_domain_2]

        # Act
        vms = compute_service.list_vms(project_id)

        # Assert
        assert len(vms) == 2
        assert vms[0]['state'] == 'RUNNING'
        assert vms[1]['state'] == 'SHUTOFF'

# ===================================================================
#  destroy_vm 테스트
# ===================================================================
class TestDestroyVm:
    @patch('src.services.compute_service.subprocess.run')
    def test_destroy_vm_success(self, mock_subprocess_run, compute_service, mock_db_connector, mock_libvirt):
        """VM 삭제 성공 시나리오 (Happy Path)를 테스트합니다."""
        # Arrange
        project_id = 1
        vm_name = "test-vm-to-destroy"
        vm_uuid = "destroy-uuid"

        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {"uuid": vm_uuid}

        mock_domain = FakeDomain(vm_name, vm_uuid)
        mock_libvirt.lookupByUUIDString.return_value = mock_domain

        # Act
        compute_service.destroy_vm(project_id, vm_name)

        # Assert
        mock_cursor.execute.assert_any_call("SELECT uuid FROM vms WHERE name = ? AND project_id = ?", (vm_name, project_id))
        mock_cursor.execute.assert_any_call("DELETE FROM vms WHERE name = ? AND project_id = ?", (vm_name, project_id))

    def test_destroy_vm_not_found(self, compute_service, mock_db_connector, mock_libvirt):
        """DB에 VM이 없을 때 VmNotFoundError 예외가 발생하는지 테스트합니다."""
        # Arrange
        project_id = 1
        vm_name = "non-existent-vm"
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = None

        # Act & Assert
        with pytest.raises(VmNotFoundError):
            compute_service.destroy_vm(project_id, vm_name)

    @patch('src.services.compute_service.subprocess.run')
    def test_destroy_vm_cleans_up_if_domain_not_found_in_libvirt(self, mock_subprocess_run, compute_service, mock_db_connector, mock_libvirt):
        """Libvirt에 VM이 없어도 나머지 리소스(디스크, DB)가 정리되는지 테스트합니다."""
        # Arrange
        project_id = 1
        vm_name = "ghost-vm"
        vm_uuid = "ghost-uuid"

        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {"uuid": vm_uuid}

        mock_libvirt.lookupByUUIDString.side_effect = libvirt.libvirtError("Domain not found")

        # Act
        compute_service.destroy_vm(project_id, vm_name)

        # Assert
        mock_cursor.execute.assert_any_call("DELETE FROM vms WHERE name = ? AND project_id = ?", (vm_name, project_id))
        mock_db_connector.commit.assert_called_once()

# ===================================================================
#  reconcile_vms 테스트
# ===================================================================
class TestReconcileVms:
    def test_reconcile_vms_no_ghosts(self, compute_service, mock_db_connector, mock_libvirt):
        """불일치하는 VM이 없을 때 빈 리스트를 반환하는지 테스트합니다."""
        # Arrange
        managed_domain = FakeDomain("managed-vm", "managed-uuid")
        mock_libvirt.listAllDomains.return_value = [managed_domain]
        
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = [{"uuid": "managed-uuid"}]

        # Act
        ghost_vms = compute_service.reconcile_vms()

        # Assert
        assert ghost_vms == []

    def test_reconcile_vms_finds_ghosts(self, compute_service, mock_db_connector, mock_libvirt):
        """DB에 없는 '유령 VM'을 정확히 찾아내는지 테스트합니다."""
        # Arrange
        managed_domain = FakeDomain("managed-vm", "managed-uuid")
        ghost_domain = FakeDomain("ghost-vm", "ghost-uuid", state_code=libvirt.VIR_DOMAIN_SHUTOFF)

        mock_libvirt.listAllDomains.return_value = [managed_domain, ghost_domain]
        mock_libvirt.lookupByUUIDString.return_value = ghost_domain
        
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = [{"uuid": "managed-uuid"}]

        # Act
        ghost_vms = compute_service.reconcile_vms()

        # Assert
        assert len(ghost_vms) == 1
        assert ghost_vms[0]["name"] == "ghost-vm"
        mock_libvirt.lookupByUUIDString.assert_called_once_with("ghost-uuid")
