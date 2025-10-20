# tests/services/test_compute_service.py
import pytest
import libvirt
from unittest.mock import MagicMock, patch, ANY
from datetime import datetime

from src.services.compute_service import ComputeService, VmNotFoundError, VmAlreadyExistsError, VmCreationError
from src.services.image_service import ImageService
from src.repositories.interfaces import IVMRepository
from src.database import models

# ===================================================================
#  테스트를 위한 가짜 객체 및 Fixture 설정
# ===================================================================

class FakeDomain:
    """libvirt의 Domain 객체를 흉내 내는 가짜 클래스."""
    def __init__(self, name, uuid, state_code=libvirt.VIR_DOMAIN_RUNNING):
        self._name = name
        self._uuid = uuid
        self._state_code = state_code

    def name(self): return self._name
    def UUIDString(self): return self._uuid
    def info(self): return [self._state_code, 2048, 1024, 2, 5000000000]
    def isActive(self): return self._state_code == libvirt.VIR_DOMAIN_RUNNING
    def create(self): return 0
    def destroy(self): self._state_code = libvirt.VIR_DOMAIN_SHUTOFF; return 0
    def undefine(self): return 0

@pytest.fixture
def mock_vm_repo() -> MagicMock:
    """IVMRepository에 대한 모의(Mock) 객체를 생성하여 반환합니다."""
    return MagicMock(spec=IVMRepository)

@pytest.fixture
def mock_image_service() -> MagicMock:
    """ImageService에 대한 모의(Mock) 객체를 생성하여 반환합니다."""
    return MagicMock(spec=ImageService)

@pytest.fixture
def mock_libvirt() -> MagicMock:
    """libvirt.open을 모킹하여 실제 하이퍼바이저 연결을 방지합니다."""
    with patch("src.services.compute_service.libvirt.open") as mock_open:
        mock_conn = MagicMock()
        mock_open.return_value = mock_conn
        yield mock_conn

@pytest.fixture
def compute_service(mock_vm_repo: MagicMock, mock_image_service: MagicMock, mock_libvirt: MagicMock) -> ComputeService:
    """테스트에 사용될 ComputeService 인스턴스를 생성하고, 의존성을 주입합니다."""
    # __del__ 메서드가 테스트 중에 libvirt 연결을 닫으려고 시도하는 것을 방지
    with patch.object(ComputeService, '__del__', lambda x: None):
        yield ComputeService(vm_repo=mock_vm_repo, image_service=mock_image_service)

# ===================================================================
#  create_vm 테스트 스위트
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
    }

    @patch("src.services.compute_service.generate_vm_xml")
    @patch("src.services.compute_service.uuid")
    def test_create_vm_success(self, mock_uuid, mock_generate_xml, compute_service, mock_vm_repo, mock_image_service, mock_libvirt):
        """VM 생성 성공 시나리오 (Happy Path)를 테스트합니다."""
        # === Arrange (테스트 준비) ===
        # 테스트에 필요한 변수들을 미리 설정하고, 모의(Mock) 객체들의 행동을 정의합니다.
        args = self.VM_DEFAULTS

        # 시나리오: 서비스가 의존하는 다른 객체들이 성공적으로 동작하는 상황을 가정합니다.
        mock_uuid.uuid4.return_value = "test-uuid"
        mock_image_service.validate_image_and_get_path.return_value = args["base_image_path"]
        mock_vm_repo.find_by_name_and_project_id.return_value = None  # VM이 아직 존재하지 않음을 시뮬레이션
        mock_image_service.create_vm_disk.return_value = args["new_disk_path"]
        mock_generate_xml.return_value = "<domain>...</domain>"
        mock_domain = MagicMock()
        mock_libvirt.defineXML.return_value = mock_domain
        mock_domain.create.return_value = 0

        # === Act (실제 테스트 대상 실행) ===
        # 준비된 환경에서 실제 테스트 대상 메서드(create_vm)를 호출합니다.
        result_name, result_uuid = compute_service.create_vm(**{k: v for k, v in args.items() if k in ['project_id', 'vm_name', 'cpu_count', 'ram_mb', 'image_name']})

        # === Assert (결과 검증) ===
        # 메서드의 반환값이 예상과 일치하는지,
        # 그리고 의존하는 객체들의 메서드가 올바르게 호출되었는지 확인합니다.

        # 1. 반환 값 검증
        assert result_name == args["vm_name"]
        assert result_uuid == "test-uuid"

        # 2. 의존 객체들의 메서드가 올바른 인자와 함께 호출되었는지 검증
        mock_image_service.validate_image_and_get_path.assert_called_once_with(args["image_name"])
        mock_vm_repo.find_by_name_and_project_id.assert_called_once_with(args["vm_name"], args["project_id"])
        mock_image_service.create_vm_disk.assert_called_once_with(args["vm_name"], args["base_image_path"])
        
        # 3. 최종적으로 DB 저장을 요청하는 리포지토리의 create 메서드가 호출되었는지 검증
        # ANY: models.VM 객체는 테스트 시점마다 메모리 주소가 달라지므로, 타입만 맞으면 통과하도록 설정
        mock_vm_repo.create.assert_called_once_with(ANY)

    def test_create_vm_fails_if_name_exists(self, compute_service, mock_vm_repo, mock_image_service):
        """VM 이름이 이미 존재할 경우 VmAlreadyExistsError 예외가 발생하는지 테스트합니다."""
        # === Arrange ===
        # 시나리오: find_by_name_and_project_id가 VM 객체를 반환하여, 이미 존재함을 시뮬레이션
        args = self.VM_DEFAULTS
        mock_image_service.validate_image_and_get_path.return_value = args["base_image_path"]
        mock_vm_repo.find_by_name_and_project_id.return_value = models.VM() 

        # === Act & Assert ===
        # VmAlreadyExistsError 예외가 발생하는지 확인
        with pytest.raises(VmAlreadyExistsError):
            compute_service.create_vm(**{k: v for k, v in args.items() if k in ['project_id', 'vm_name', 'cpu_count', 'ram_mb', 'image_name']})
        
        # 검증: 예외가 발생했으므로, VM을 생성하는 create 메서드는 호출되지 않았어야 함
        mock_vm_repo.create.assert_not_called()

# ===================================================================
#  list_vms 테스트 스위트
# ===================================================================
class TestListVms:
    def test_list_vms_with_data(self, compute_service, mock_vm_repo, mock_libvirt):
        """DB에 VM이 있을 때 실시간 상태와 통합된 목록을 반환하는지 테스트합니다."""
        # === Arrange ===
        project_id = 1
        # 시나리오: 리포지토리가 DB에서 2개의 VM 정보를 반환하는 상황을 시뮬레이션
        db_vms = [
            models.VM(name='test-vm-1', uuid='uuid-1', cpu_count=2, ram_mb=2048, created_at=datetime.now()),
            models.VM(name='test-vm-2', uuid='uuid-2', cpu_count=1, ram_mb=1024, created_at=datetime.now())
        ]
        mock_vm_repo.list_by_project_id.return_value = db_vms

        # 시나리오: libvirt는 각 VM에 대해 다른 상태(RUNNING, SHUTOFF)를 반환하도록 설정
        mock_libvirt.lookupByUUIDString.side_effect = [
            FakeDomain('test-vm-1', 'uuid-1', libvirt.VIR_DOMAIN_RUNNING),
            FakeDomain('test-vm-2', 'uuid-2', libvirt.VIR_DOMAIN_SHUTOFF)
        ]

        # === Act ===
        vms = compute_service.list_vms(project_id)

        # === Assert ===
        # 1. 리포지토리 메서드가 올바른 project_id로 호출되었는지 검증
        mock_vm_repo.list_by_project_id.assert_called_once_with(project_id)

        # 2. 최종 반환된 결과가 DB 정보와 libvirt의 실시간 상태를 올바르게 조합했는지 검증
        assert len(vms) == 2
        assert vms[0]['name'] == 'test-vm-1'
        assert vms[0]['state'] == 'RUNNING'
        assert vms[1]['name'] == 'test-vm-2'
        assert vms[1]['state'] == 'SHUTOFF'

# ===================================================================
#  destroy_vm 테스트 스위트
# ===================================================================
class TestDestroyVm:
    def test_destroy_vm_success(self, compute_service, mock_vm_repo, mock_image_service, mock_libvirt):
        """VM 삭제 성공 시나리오를 테스트합니다."""
        # === Arrange ===
        project_id, vm_name, vm_uuid = 1, "test-vm-to-destroy", "destroy-uuid"
        
        # 시나리오: 리포지토리가 삭제할 VM 객체를 성공적으로 찾아 반환하는 상황
        mock_vm = models.VM(name=vm_name, uuid=vm_uuid)
        mock_vm_repo.find_by_name_and_project_id.return_value = mock_vm
        mock_libvirt.lookupByUUIDString.return_value = FakeDomain(vm_name, vm_uuid)

        # === Act ===
        compute_service.destroy_vm(project_id, vm_name)

        # === Assert ===
        # 검증: VM을 찾고, 디스크를 삭제하고, 최종적으로 DB에서 삭제하는 흐름이 모두 호출되었는지 확인
        mock_vm_repo.find_by_name_and_project_id.assert_called_once_with(vm_name, project_id)
        mock_image_service.delete_vm_disk_by_name.assert_called_once_with(vm_name)
        mock_vm_repo.delete.assert_called_once_with(mock_vm)

    def test_destroy_vm_not_found(self, compute_service, mock_vm_repo):
        """삭제할 VM을 찾지 못했을 때 VmNotFoundError 예외가 발생하는지 테스트합니다."""
        # === Arrange ===
        # 시나리오: 리포지토리가 VM을 찾지 못하고 None을 반환하는 상황
        project_id, vm_name = 1, "non-existent-vm"
        mock_vm_repo.find_by_name_and_project_id.return_value = None

        # === Act & Assert ===
        # VmNotFoundError 예외가 발생하는지 확인
        with pytest.raises(VmNotFoundError):
            compute_service.destroy_vm(project_id, vm_name)
