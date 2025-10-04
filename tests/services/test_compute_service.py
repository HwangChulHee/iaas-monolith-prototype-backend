
# tests/services/test_compute_service.py
import pytest
import libvirt
import sqlite3
from unittest.mock import patch, MagicMock, call
from datetime import datetime

from src.services.compute_service import ComputeService, VmNotFoundError

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

    def destroy(self):
        return 0

    def undefine(self):
        return 0

@pytest.fixture
def mock_db_connector():
    """DBConnector를 모킹하여 connection 객체를 반환합니다."""
    with patch('src.services.compute_service.DBConnector') as mock_db_class:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn # 이제 커넥션을 반환합니다.

@pytest.fixture
def mock_libvirt():
    """libvirt.open 함수만 모킹하여 실제 하이퍼바이저 연결을 방지합니다."""
    with patch('src.services.compute_service.libvirt.open') as mock_open:
        mock_conn = MagicMock()
        mock_open.return_value = mock_conn
        yield mock_conn

@pytest.fixture
def compute_service(mock_libvirt):
    """테스트를 위한 ComputeService 인스턴스를 생성합니다."""
    service = ComputeService()
    return service

class TestComputeService:
    """ComputeService의 단위 테스트 모음"""

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
            {'name': 'test-vm-1', 'uuid': 'uuid-1', 'cpu_count': 2, 'ram_mb': 2048, 'created_at': '2025-10-04'},
            {'name': 'test-vm-2', 'uuid': 'uuid-2', 'cpu_count': 1, 'ram_mb': 1024, 'created_at': '2025-10-03'}
        ]
        mock_cursor.fetchall.return_value = [dict(row) for row in db_vms]

        fake_domain_1 = FakeDomain('test-vm-1', 'uuid-1', libvirt.VIR_DOMAIN_RUNNING)
        fake_domain_2 = FakeDomain('test-vm-2', 'uuid-2', libvirt.VIR_DOMAIN_SHUTOFF)
        mock_libvirt.lookupByUUIDString.side_effect = [fake_domain_1, fake_domain_2]

        # Act
        vms = compute_service.list_vms()

        # Assert
        assert len(vms) == 2
        assert vms[0]['state'] == 'RUNNING'
        assert vms[1]['state'] == 'SHUTOFF'
        mock_libvirt.lookupByUUIDString.assert_has_calls([call('uuid-1'), call('uuid-2')])

    @patch('src.services.compute_service.datetime')
    @patch('src.services.compute_service.ImageService')
    @patch('src.services.compute_service.generate_vm_xml')
    @patch('src.services.compute_service.uuid')
    def test_create_vm_success(self, mock_uuid, mock_generate_xml, mock_image_service, mock_datetime, 
                             compute_service, mock_db_connector, mock_libvirt):
        """VM 생성 성공 시나리오 (Happy Path)를 테스트합니다."""
        # Arrange
        vm_name, cpu_count, ram_mb, image_name = "new-test-vm", 2, 2048, "Ubuntu-Base-22.04"
        base_image_path = "/var/lib/libvirt/images/ubuntu-base.qcow2"
        new_disk_path = f"/var/lib/libvirt/images/{vm_name}.qcow2"
        test_uuid = "a-real-uuid-from-test"
        dummy_xml = "<domain>...</domain>"
        fake_now = datetime(2025, 10, 4, 12, 0, 0)

        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.side_effect = [None, {"filepath": base_image_path}]
        mock_uuid.uuid4.return_value = test_uuid
        mock_image_service.create_vm_disk.return_value = new_disk_path
        mock_generate_xml.return_value = dummy_xml
        mock_datetime.now.return_value = fake_now

        mock_domain = MagicMock()
        mock_libvirt.defineXML.return_value = mock_domain
        mock_domain.create.return_value = 0

        # Act
        result_name, result_uuid = compute_service.create_vm(vm_name, cpu_count, ram_mb, image_name)

        # Assert
        assert result_name == vm_name
        assert result_uuid == test_uuid

        assert mock_cursor.execute.call_count == 3
        mock_cursor.execute.assert_any_call("SELECT name FROM vms WHERE name = ?", (vm_name,))
        mock_cursor.execute.assert_any_call("SELECT filepath FROM images WHERE name = ?", (image_name,))
        
        mock_image_service.create_vm_disk.assert_called_once_with(vm_name, base_image_path)
        mock_generate_xml.assert_called_once_with(vm_name, test_uuid, cpu_count, ram_mb, new_disk_path)
        mock_libvirt.defineXML.assert_called_once_with(dummy_xml)
        mock_domain.create.assert_called_once()

        final_insert_query = mock_cursor.execute.call_args_list[-1]
        assert "INSERT INTO vms" in final_insert_query.args[0]
        assert final_insert_query.args[1] == (vm_name, test_uuid, "running", cpu_count, ram_mb, fake_now)
        
        mock_db_connector.commit.assert_called_once()

    @patch('src.services.compute_service.ImageService')
    def test_create_vm_fails_if_name_exists(self, mock_image_service, compute_service, mock_db_connector):
        """DB에 VM 이름이 이미 존재할 경우 예외가 발생하는지 테스트합니다."""
        # Arrange
        vm_name = "existing-vm"
        mock_cursor = mock_db_connector.cursor()
        # fetchone이 None이 아닌 값을 반환하여, 이름이 이미 존재함을 시뮬레이션
        mock_cursor.fetchone.return_value = (1,)

        # Act & Assert
        with pytest.raises(Exception) as excinfo:
            compute_service.create_vm(vm_name, 2, 2048, "image-name")

        # 예외 메시지가 올바른지 확인
        assert "already exists" in str(excinfo.value)

        # 이름 중복 확인 후, 다른 작업(디스크 생성 등)이 호출되지 않았는지 확인
        mock_image_service.create_vm_disk.assert_not_called()

    @patch('src.services.compute_service.ImageService')
    def test_create_vm_fails_if_image_not_found(self, mock_image_service, compute_service, mock_db_connector):
        """DB에 베이스 이미지가 존재하지 않을 경우 예외가 발생하는지 테스트합니다."""
        # Arrange
        vm_name = "new-vm"
        image_name = "non-existent-image"
        mock_cursor = mock_db_connector.cursor()
        # 1. 이름 중복 검사 -> 통과 (None 반환)
        # 2. 이미지 경로 조회 -> 실패 (None 반환)
        mock_cursor.fetchone.side_effect = [None, None]

        # Act & Assert
        with pytest.raises(Exception) as excinfo:
            compute_service.create_vm(vm_name, 2, 2048, image_name)

        # 예외 메시지가 올바른지 확인
        assert "not found" in str(excinfo.value)
        assert image_name in str(excinfo.value)

        # 이미지 조회 실패 후, 다른 작업(디스크 생성 등)이 호출되지 않았는지 확인
        mock_image_service.create_vm_disk.assert_not_called()
