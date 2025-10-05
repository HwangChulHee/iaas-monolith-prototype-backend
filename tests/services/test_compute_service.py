

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
    @patch("src.services.compute_service.datetime")
    @patch("src.services.compute_service.ImageService", autospec=True)
    @patch("src.services.compute_service.generate_vm_xml")
    @patch("src.services.compute_service.uuid")
    def test_create_vm_success(
        self,
        mock_uuid,
        mock_generate_xml,
        mock_image_service,
        mock_datetime,
        mock_save_db,
        mock_rollback,
        compute_service,
        mock_db_connector,
        mock_libvirt,
    ):
        """VM 생성 성공 시나리오 (Happy Path)를 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, {"filepath": args["base_image_path"]}]
        mock_uuid.uuid4.return_value = args["test_uuid"]
        mock_image_service.create_vm_disk.return_value = args["new_disk_path"]
        mock_generate_xml.return_value = args["dummy_xml"]
        mock_datetime.now.return_value = args["fake_now"]

        mock_domain = MagicMock()
        mock_libvirt.defineXML.return_value = mock_domain
        mock_domain.create.return_value = 0

        # Act
        result_name, result_uuid = compute_service.create_vm(
            args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
        )

        # Assert
        assert result_name == args["vm_name"]
        assert result_uuid == args["test_uuid"]

        mock_image_service.create_vm_disk.assert_called_once_with(
            args["vm_name"], args["base_image_path"]
        )
        mock_generate_xml.assert_called_once_with(
            args["vm_name"],
            args["test_uuid"],
            args["cpu_count"],
            args["ram_mb"],
            args["new_disk_path"],
        )
        mock_libvirt.defineXML.assert_called_once_with(args["dummy_xml"])
        mock_domain.create.assert_called_once()

        mock_save_db.assert_called_once_with(
            args["vm_name"], args["test_uuid"], args["cpu_count"], args["ram_mb"]
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
                args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert args["vm_name"] in str(excinfo.value)
        mock_rollback.assert_not_called()

    @patch.object(ComputeService, '_rollback_vm_creation')
    def test_create_vm_fails_if_image_not_found(
        self, mock_rollback, compute_service, mock_db_connector
    ):
        """DB에 베이스 이미지가 없을 경우 ImageNotFoundError 예외가 발생하는지 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, None]

        # Act & Assert
        with pytest.raises(ImageNotFoundError) as excinfo:
            compute_service.create_vm(
                args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert args["image_name"] in str(excinfo.value)
        mock_rollback.assert_not_called()

    @patch.object(ComputeService, '_rollback_vm_creation')
    @patch("src.services.compute_service.ImageService", autospec=True)
    def test_create_vm_rollback_on_disk_creation_failure(
        self, mock_image_service, mock_rollback, compute_service, mock_db_connector
    ):
        """디스크 생성 실패 시 VmCreationError가 발생하고 롤백이 호출되는지 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, {"filepath": args["base_image_path"]}]
        mock_image_service.create_vm_disk.side_effect = Exception("Disk creation failed")

        # Act & Assert
        with pytest.raises(VmCreationError) as excinfo:
            compute_service.create_vm(
                args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert "Disk creation failed" in str(excinfo.value)
        mock_rollback.assert_called_once_with(None, None)

    @patch.object(ComputeService, '_rollback_vm_creation')
    @patch("src.services.compute_service.ImageService", autospec=True)
    @patch("src.services.compute_service.generate_vm_xml")
    @patch("src.services.compute_service.uuid")
    def test_create_vm_rollback_on_libvirt_define_failure(
        self,
        mock_uuid,
        mock_generate_xml,
        mock_image_service,
        mock_rollback,
        compute_service,
        mock_db_connector,
        mock_libvirt,
    ):
        """Libvirt VM 정의 실패 시 VmCreationError가 발생하고 디스크 삭제 롤백이 호출되는지 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, {"filepath": args["base_image_path"]}]
        mock_uuid.uuid4.return_value = args["test_uuid"]
        mock_image_service.create_vm_disk.return_value = args["new_disk_path"]
        mock_generate_xml.return_value = args["dummy_xml"]
        mock_libvirt.defineXML.side_effect = libvirt.libvirtError("Define failed")

        # Act & Assert
        with pytest.raises(VmCreationError) as excinfo:
            compute_service.create_vm(
                args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert "Define failed" in str(excinfo.value)
        mock_rollback.assert_called_once_with(None, args["new_disk_path"])

    @patch.object(ComputeService, '_rollback_vm_creation')
    @patch("src.services.compute_service.ImageService", autospec=True)
    @patch("src.services.compute_service.generate_vm_xml")
    @patch("src.services.compute_service.uuid")
    def test_create_vm_rollback_on_vm_start_failure(
        self,
        mock_uuid,
        mock_generate_xml,
        mock_image_service,
        mock_rollback,
        compute_service,
        mock_db_connector,
        mock_libvirt,
    ):
        """VM 시작 실패 시 VmCreationError가 발생하고 롤백이 호출되는지 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, {"filepath": args["base_image_path"]}]
        mock_uuid.uuid4.return_value = args["test_uuid"]
        mock_image_service.create_vm_disk.return_value = args["new_disk_path"]
        mock_generate_xml.return_value = args["dummy_xml"]

        mock_domain = MagicMock()
        mock_libvirt.defineXML.return_value = mock_domain
        mock_domain.create.return_value = -1  # VM 시작 실패

        # Act & Assert
        with pytest.raises(VmCreationError) as excinfo:
            compute_service.create_vm(
                args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert "Failed to start the VM" in str(excinfo.value)
        mock_rollback.assert_called_once_with(mock_domain, args["new_disk_path"])

    @patch.object(ComputeService, '_rollback_vm_creation')
    @patch.object(ComputeService, '_save_vm_metadata_to_db')
    @patch("src.services.compute_service.datetime")
    @patch("src.services.compute_service.ImageService", autospec=True)
    @patch("src.services.compute_service.generate_vm_xml")
    @patch("src.services.compute_service.uuid")
    def test_create_vm_rollback_on_db_insert_failure(
        self,
        mock_uuid,
        mock_generate_xml,
        mock_image_service,
        mock_datetime,
        mock_save_db,
        mock_rollback,
        compute_service,
        mock_db_connector,
        mock_libvirt,
    ):
        """DB 저장 실패 시 VmCreationError가 발생하고 모든 리소스가 롤백되는지 테스트합니다."""
        # Arrange
        args = self.VM_DEFAULTS
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, {"filepath": args["base_image_path"]}]

        mock_uuid.uuid4.return_value = args["test_uuid"]
        mock_image_service.create_vm_disk.return_value = args["new_disk_path"]
        mock_generate_xml.return_value = args["dummy_xml"]
        mock_datetime.now.return_value = args["fake_now"]

        mock_domain_instance = FakeDomain(args["vm_name"], args["test_uuid"])
        mock_libvirt.defineXML.return_value = mock_domain_instance

        db_error = sqlite3.Error("Simulated DB Insert Error")
        mock_save_db.side_effect = db_error

        # Act & Assert
        with pytest.raises(VmCreationError) as excinfo:
            compute_service.create_vm(
                args["vm_name"], args["cpu_count"], args["ram_mb"], args["image_name"]
            )

        assert "Simulated DB Insert Error" in str(excinfo.value)
        mock_rollback.assert_called_once_with(mock_domain_instance, args["new_disk_path"])


# ===================================================================
#  list_vms 테스트
# ===================================================================
class TestListVms:
    def test_list_vms_empty(self, compute_service, mock_db_connector):
        """DB에 VM이 없을 때 빈 리스트를 반환하는지 테스트합니다."""
        # Arrange
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = []

        # Act
        vms = compute_service.list_vms()

        # Assert
        assert vms == []
        mock_cursor.execute.assert_called_once()

    def test_list_vms_with_data(self, compute_service, mock_db_connector, mock_libvirt):
        """DB에 VM이 있을 때 libvirt에서 상태를 가져와 통합된 목록을 반환하는지 테스트합니다."""
        # Arrange
        mock_cursor = mock_db_connector.cursor()
        db_vms = [
            {
                "name": "test-vm-1",
                "uuid": "uuid-1",
                "cpu_count": 2,
                "ram_mb": 2048,
                "created_at": "2025-10-04",
            },
            {
                "name": "test-vm-2",
                "uuid": "uuid-2",
                "cpu_count": 1,
                "ram_mb": 1024,
                "created_at": "2025-10-03",
            },
        ]
        mock_cursor.fetchall.return_value = [dict(row) for row in db_vms]

        fake_domain_1 = FakeDomain("test-vm-1", "uuid-1", libvirt.VIR_DOMAIN_RUNNING)
        fake_domain_2 = FakeDomain("test-vm-2", "uuid-2", libvirt.VIR_DOMAIN_SHUTOFF)
        mock_libvirt.lookupByUUIDString.side_effect = [fake_domain_1, fake_domain_2]

        # Act
        vms = compute_service.list_vms()

        # Assert
        assert len(vms) == 2
        assert vms[0]["state"] == "RUNNING"
        assert vms[1]["state"] == "SHUTOFF"
        mock_libvirt.lookupByUUIDString.assert_has_calls(
            [call("uuid-1"), call("uuid-2")]
        )
