import libvirt
import uuid
import os
import subprocess
from datetime import datetime

from src.database import models
from src.repositories.interfaces import IVMRepository
from src.utils.vm_xml_generator import generate_vm_xml
from src.services.image_service import ImageService
from src.services.exceptions import (
    VmNotFoundError,
    VmAlreadyExistsError,
    VmCreationError,
)

class ComputeService:
    def __init__(self, vm_repo: IVMRepository, image_service: ImageService, uri="qemu:///system"):
        self.vm_repo = vm_repo
        self.image_service = image_service # ImageService도 의존성으로 주입
        try:
            self.conn = libvirt.open(uri)
        except libvirt.libvirtError:
            # TODO: 로깅 시스템 도입 후 로그 남기기
            raise ConnectionError("Failed to open connection to the hypervisor.")

    def create_vm(self, project_id: int, vm_name: str, cpu_count: int, ram_mb: int, image_name: str):
        """
        새로운 가상 머신을 생성하고 시작합니다.

        VM 생성 전체 과정을 관리하며, 디스크 생성, libvirt VM 정의, VM 시작,
        DB 메타데이터 저장을 포함합니다. 실패 시 생성된 리소스를 정리하는 롤백 로직이 동작합니다.

        Args:
            project_id: VM이 속할 프로젝트의 ID.
            vm_name: 생성할 VM의 이름.
            cpu_count: 할당할 CPU 코어 수.
            ram_mb: 할당할 RAM 크기 (MB).
            image_name: VM을 생성할 기반 이미지의 이름.

        Returns:
            생성된 VM의 이름과 UUID를 담은 튜플 (vm_name, vm_uuid).

        Raises:
            ImageNotFoundError: 요청된 이미지를 찾을 수 없을 때.
            VmAlreadyExistsError: 동일한 이름의 VM이 프로젝트 내에 이미 존재할 때.
            VmCreationError: VM 생성 과정(libvirt, 디스크 등) 중 오류가 발생했을 때.
        """
        # 1. 요청 유효성 검사 (VM 중복, 이미지 존재 여부)
        source_filepath = self.image_service.validate_image_and_get_path(image_name)
        if self.vm_repo.find_by_name_and_project_id(vm_name, project_id):
            raise VmAlreadyExistsError(f"VM name '{vm_name}' already exists in this project.")

        vm_disk_filepath = None
        domain = None
        vm_uuid = str(uuid.uuid4())

        try:
            # 2. VM 디스크 생성
            vm_disk_filepath = self.image_service.create_vm_disk(vm_name, source_filepath)

            # 3. VM XML 설정 생성 및 Libvirt VM 정의
            xml_config = generate_vm_xml(vm_name, vm_uuid, cpu_count, ram_mb, vm_disk_filepath)
            domain = self.conn.defineXML(xml_config)

            # 4. VM 시작
            if domain.create() < 0:
                raise VmCreationError("Failed to start the VM after definition.")

            # 5. DB에 VM 메타데이터 저장 (리포지토리 사용)
            new_vm = models.VM(
                name=vm_name,
                uuid=vm_uuid,
                state="RUNNING",
                cpu_count=cpu_count,
                ram_mb=ram_mb,
                project_id=project_id
            )
            self.vm_repo.create(new_vm)

            return vm_name, vm_uuid

        except (libvirt.libvirtError, VmCreationError, Exception) as e:
            print(f"VM '{vm_name}' creation failed: {e}. Starting rollback...")
            self._rollback_vm_creation(domain, vm_disk_filepath)
            raise VmCreationError(f"Failed to create VM '{vm_name}'. Original error: {e}") from e

    def _rollback_vm_creation(self, domain, disk_path):
        if domain:
            try:
                if domain.isActive():
                    domain.destroy()
                domain.undefine()
            except libvirt.libvirtError as e:
                print(f"Rollback Warning: Failed to clean up libvirt domain: {e}")

        if disk_path and os.path.exists(disk_path):
            self.image_service.delete_vm_disk(disk_path)

    def list_vms(self, project_id: int):
        """
        특정 프로젝트에 속한 VM 목록을 조회하고, 하이퍼바이저에서 실시간 상태를 가져옵니다.

        DB에 저장된 VM 정보와 libvirt를 통해 확인한 실시간 상태를 조합하여 반환합니다.
        만약 VM이 하이퍼바이저에 존재하지 않으면 상태는 'UNKNOWN'으로 표시됩니다.

        Args:
            project_id: 조회할 VM들이 속한 프로젝트의 ID.

        Returns:
            VM의 상세 정보(이름, UUID, CPU, RAM, 생성일, 상태 등)가 포함된
            딕셔너리의 리스트.
        """
        vms_from_db = self.vm_repo.list_by_project_id(project_id)
        
        vms_with_realtime_state = []
        for vm in vms_from_db:
            vm_data = {
                "name": vm.name,
                "uuid": vm.uuid,
                "cpu_count": vm.cpu_count,
                "ram_mb": vm.ram_mb,
                "created_at": vm.created_at.isoformat()
            }
            try:
                domain = self.conn.lookupByUUIDString(vm.uuid)
                state_code, _, _, _, _ = domain.info()
                vm_data["state"] = self._map_vm_state(state_code)
            except libvirt.libvirtError:
                vm_data["state"] = "UNKNOWN"
            vms_with_realtime_state.append(vm_data)
            
        return vms_with_realtime_state

    def destroy_vm(self, project_id: int, vm_name: str):
        """
        특정 VM을 찾아 모든 관련 리소스를 정리하고 데이터베이스에서 삭제합니다.

        libvirt 도메인 종료 및 정의 해제, 연결된 디스크 파일 삭제, DB 기록 삭제를
        포함합니다. 일부 리소스 정리에 실패하더라도 DB 기록은 반드시 삭제를 시도합니다.

        Args:
            project_id: 삭제할 VM이 속한 프로젝트의 ID.
            vm_name: 삭제할 VM의 이름.

        Returns:
            성공적으로 삭제되었으면 True를 반환합니다.

        Raises:
            VmNotFoundError: 해당 프로젝트에서 VM을 찾을 수 없을 때.
        """
        vm_to_delete = self.vm_repo.find_by_name_and_project_id(vm_name, project_id)
        if not vm_to_delete:
            raise VmNotFoundError(f"VM '{vm_name}' not found in project '{project_id}'.")

        try:
            # Libvirt 리소스 정리
            try:
                domain = self.conn.lookupByUUIDString(vm_to_delete.uuid)
                if domain.isActive():
                    domain.destroy()
                domain.undefine()
            except libvirt.libvirtError as e:
                print(f"Libvirt Warning: Failed to clean up domain for VM '{vm_name}': {e}. Proceeding cleanup.")

            # 디스크 리소스 정리
            self.image_service.delete_vm_disk_by_name(vm_name)

        finally:
            # 최종적으로 DB에서 VM 기록 삭제
            self.vm_repo.delete(vm_to_delete)
            print(f"DB Info: Record for VM '{vm_name}' in project '{project_id}' deleted.")

        return True

    def reconcile_vms(self):
        """
        하이퍼바이저와 DB의 상태를 비교하여 불일치하는 VM을 찾아냅니다.

        DB에는 없지만 libvirt에만 존재하는 '유령(Ghost) VM'의 목록을 반환합니다.
        이는 시스템 외부에서 비정상적으로 생성되었거나, DB 오류로 기록이 누락된 VM일 수 있습니다.

        Returns:
            유령 VM의 정보(이름, UUID, 상태)가 포함된 딕셔너리의 리스트.

        Raises:
            ConnectionError: libvirt에 연결할 수 없을 때.
        """
        try:
            all_domains = self.conn.listAllDomains(0)
            libvirt_uuids = {domain.UUIDString() for domain in all_domains}
        except libvirt.libvirtError as e:
            raise ConnectionError(f"Error fetching domains from libvirt: {e}")

        db_uuids = set(self.vm_repo.list_all_uuids())
        ghost_vm_uuids = libvirt_uuids - db_uuids

        ghost_vms = []
        for uuid in ghost_vm_uuids:
            try:
                domain = self.conn.lookupByUUIDString(uuid)
                ghost_vms.append({
                    "name": domain.name(),
                    "uuid": uuid,
                    "state": self._map_vm_state(domain.info()[0])
                })
            except libvirt.libvirtError:
                continue
        
        return ghost_vms

    def _map_vm_state(self, state_code):
        state_map = {
            libvirt.VIR_DOMAIN_NOSTATE: 'NOSTATE',
            libvirt.VIR_DOMAIN_RUNNING: 'RUNNING',
            libvirt.VIR_DOMAIN_BLOCKED: 'BLOCKED',
            libvirt.VIR_DOMAIN_PAUSED: 'PAUSED',
            libvirt.VIR_DOMAIN_SHUTDOWN: 'SHUTDOWN',
            libvirt.VIR_DOMAIN_SHUTOFF: 'SHUTOFF',
            libvirt.VIR_DOMAIN_CRASHED: 'CRASHED',
            libvirt.VIR_DOMAIN_PMSUSPENDED: 'PMSUSPENDED',
        }
        return state_map.get(state_code, 'UNKNOWN')

    def __del__(self):
        if self.conn:
            try:
                self.conn.close()
            except libvirt.libvirtError:
                pass # 이미 닫혔거나 할 수 없는 경우 무시
