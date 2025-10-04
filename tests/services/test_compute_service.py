
# tests/services/test_compute_service.py
import pytest
import libvirt
import sqlite3
from unittest.mock import patch, MagicMock, call

from src.services.compute_service import ComputeService, VmNotFoundError
from src.database.db_connector import DBConnector

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
        print(f"Fake domain {self._name} destroyed.")
        return 0

    def undefine(self):
        print(f"Fake domain {self._name} undefined.")
        return 0

@pytest.fixture
def mock_db_connector():
    """DBConnector를 모킹하여 실제 DB 호출을 방지합니다."""
    with patch('src.services.compute_service.DBConnector') as mock:
        # with 구문을 흉내내기 위해 __enter__와 __exit__를 모킹합니다.
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_cursor # 테스트 함수에서는 cursor 객체를 사용합니다.

@pytest.fixture
def mock_libvirt():
    """libvirt.open 함수만 모킹하여 실제 하이퍼바이저 연결을 방지합니다."""
    with patch('src.services.compute_service.libvirt.open') as mock_open:
        mock_conn = MagicMock()
        mock_open.return_value = mock_conn
        
        # 테스트에서 libvirt 상수(e.g. libvirt.VIR_DOMAIN_RUNNING)를 사용할 수 있도록
        # 실제 libvirt 모듈을 mock_conn 객체에 연결해주는 트릭
        mock_conn.lookupByUUIDString.side_effect = lambda uuid: FakeDomain(uuid=uuid)
        yield mock_conn

@pytest.fixture
def compute_service(mock_libvirt):
    """테스트를 위한 ComputeService 인스턴스를 생성합니다."""
    # __init__에서 libvirt.open()이 호출되므로, mock_libvirt fixture가 먼저 실행되어야 합니다.
    service = ComputeService()
    return service

class TestComputeService:
    """ComputeService의 단위 테스트 모음"""

    def test_list_vms_empty(self, compute_service, mock_db_connector):
        """DB에 VM이 없을 때 빈 리스트를 반환하는지 테스트합니다."""
        # Arrange: DB가 빈 리스트를 반환하도록 설정
        mock_db_connector.fetchall.return_value = []

        # Act: list_vms 호출
        vms = compute_service.list_vms()

        # Assert: 결과가 빈 리스트인지 확인
        assert vms == []
        mock_db_connector.execute.assert_called_once()

    def test_list_vms_with_data(self, compute_service, mock_db_connector, mock_libvirt):
        """DB에 VM이 있을 때 libvirt에서 상태를 가져와 통합된 목록을 반환하는지 테스트합니다."""
        # Arrange
        # 1. DB에서 반환할 가짜 VM 데이터 설정
        db_vms = [
            {'name': 'test-vm-1', 'uuid': 'uuid-1', 'cpu_count': 2, 'ram_mb': 2048, 'created_at': '2025-10-04'},
            {'name': 'test-vm-2', 'uuid': 'uuid-2', 'cpu_count': 1, 'ram_mb': 1024, 'created_at': '2025-10-03'}
        ]
        mock_db_connector.fetchall.return_value = [dict(row) for row in db_vms]

        # 2. libvirt가 반환할 가짜 도메인 객체 설정
        fake_domain_1 = FakeDomain('test-vm-1', 'uuid-1', libvirt.VIR_DOMAIN_RUNNING)
        fake_domain_2 = FakeDomain('test-vm-2', 'uuid-2', libvirt.VIR_DOMAIN_SHUTOFF)
        
        # lookupByUUIDString가 호출될 때 각각 다른 FakeDomain을 반환하도록 설정
        mock_libvirt.lookupByUUIDString.side_effect = [fake_domain_1, fake_domain_2]

        # Act
        vms = compute_service.list_vms()

        # Assert
        # 1. 반환된 VM 목록의 개수가 올바른지 확인
        assert len(vms) == 2
        
        # 2. 각 VM의 상태가 libvirt에서 온 정보로 올바르게 채워졌는지 확인
        assert vms[0]['name'] == 'test-vm-1'
        assert vms[0]['state'] == 'RUNNING'
        assert vms[1]['name'] == 'test-vm-2'
        assert vms[1]['state'] == 'SHUTOFF'

        # 3. libvirt의 lookup 함수가 각 VM의 UUID로 정확히 호출되었는지 확인
        mock_libvirt.lookupByUUIDString.assert_has_calls([
            call('uuid-1'),
            call('uuid-2')
        ])
