# src/services/compute_service.py
import libvirt
import sqlite3
import uuid
from datetime import datetime
import os
import subprocess

from database.db_connector import DBConnector
from utils.vm_xml_generator import generate_vm_xml
from services.image_service import ImageService

class VmNotFoundError(Exception):
    """VM을 찾을 수 없을 때 발생하는 사용자 정의 예외"""
    pass

class VmAlreadyExistsError(Exception):
    """VM 이름이 이미 존재할 때 발생하는 예외"""
    pass

class ImageNotFoundError(Exception):
    """베이스 이미지를 찾을 수 없을 때 발생하는 예외"""
    pass

class VmCreationError(Exception):
    """VM 생성 과정(디스크, libvirt 등)에서 오류 발생 시 사용하는 예외"""
    pass


class ComputeService:
    def __init__(self, uri="qemu:///system"):
        self.conn = libvirt.open(uri)
        if self.conn is None:
            raise ConnectionError("Failed to open connection to the hypervisor.")

    def create_vm(self, vm_name, cpu_count, ram_mb, image_name):
        """
        VM 생성의 전체 과정을 관리하며, 실패 시 생성된 리소스를 정리하는 롤백 로직을 포함합니다.
        """
        source_filepath = self._validate_vm_and_get_image_path(vm_name, image_name)

        vm_disk_filepath = None
        domain = None
        vm_uuid = str(uuid.uuid4())

        try:
            # 1. VM 디스크 생성
            vm_disk_filepath = ImageService.create_vm_disk(vm_name, source_filepath)

            # 2. VM XML 설정 생성
            xml_config = generate_vm_xml(vm_name, vm_uuid, cpu_count, ram_mb, vm_disk_filepath)

            # 3. Libvirt에 VM 정의
            domain = self.conn.defineXML(xml_config)

            # 4. VM 시작
            if domain.create() < 0:
                raise VmCreationError("Failed to start the VM after definition.")

            # 5. DB에 VM 메타데이터 저장
            self._save_vm_metadata_to_db(vm_name, vm_uuid, cpu_count, ram_mb)

            return vm_name, vm_uuid

        except (libvirt.libvirtError, VmCreationError, sqlite3.Error, Exception) as e:
            print(f"VM '{vm_name}' creation failed: {e}. Starting rollback...")
            self._rollback_vm_creation(domain, vm_disk_filepath)
            # 원래 예외를 새로운 예외로 감싸서 추가 정보를 제공
            raise VmCreationError(f"Failed to create VM '{vm_name}'. Original error: {e}") from e

    def _validate_vm_and_get_image_path(self, vm_name, image_name):
        """VM 생성 전 DB에서 유효성을 검사하고, 베이스 이미지 경로를 반환합니다."""
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM vms WHERE name = ?", (vm_name,))
            if cursor.fetchone():
                raise VmAlreadyExistsError(f"VM name '{vm_name}' already exists.")
            
            cursor.execute("SELECT filepath FROM images WHERE name = ?", (image_name,))
            image_row = cursor.fetchone()
            if not image_row:
                raise ImageNotFoundError(f"Image '{image_name}' not found.")
            
            return image_row["filepath"]

    def _save_vm_metadata_to_db(self, vm_name, vm_uuid, cpu_count, ram_mb):
        """VM 메타데이터를 데이터베이스에 저장합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO vms (name, uuid, state, cpu_count, ram_mb, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (vm_name, vm_uuid, "running", cpu_count, ram_mb, datetime.now()),
                )
                conn.commit()
        except sqlite3.Error as db_e:
            # 이 예외는 create_vm의 메인 try-except 블록에서 처리됩니다.
            raise db_e

    def _rollback_vm_creation(self, domain, disk_path):
        """VM 생성 실패 시 관련 리소스를 정리합니다."""
        # 롤백 1: Libvirt VM 종료 및 정의 제거
        if domain:
            try:
                if domain.isActive():
                    domain.destroy()
                domain.undefine()
                print(f"Rollback: Libvirt domain for '{domain.name()}' cleaned up.")
            except libvirt.libvirtError as e:
                print(f"Rollback Warning: Failed to clean up libvirt domain: {e}")

        # 롤백 2: 생성된 VM 디스크 파일 삭제
        if disk_path and os.path.exists(disk_path):
            try:
                ImageService.delete_vm_disk(disk_path)
                print(f"Rollback: VM disk '{disk_path}' deleted.")
            except Exception as e:
                print(f"Rollback Warning: Failed to delete VM disk '{disk_path}': {e}")

    def list_vms(self):
        """DB의 VM 목록을 기반으로, libvirt에서 실시간 상태를 가져와 통합된 목록을 반환합니다."""
        vms_from_db = []
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, uuid, cpu_count, ram_mb, created_at FROM vms ORDER BY created_at DESC"
            )
            # state는 실시간으로 가져올 것이므로 SELECT 목록에서 제외
            vms_from_db = [dict(row) for row in cursor.fetchall()]

        # 실시간 정보를 포함할 최종 VM 목록
        vms_with_realtime_state = []
        for vm_data in vms_from_db:
            try:
                domain = self.conn.lookupByUUIDString(vm_data["uuid"])
                state_code, _, _, _, _ = domain.info()
                # 실시간 상태를 DB 정보에 추가
                vm_data["state"] = self._map_vm_state(state_code)
            except libvirt.libvirtError:
                # libvirt에 VM이 없으면 'UNKNOWN' 상태로 처리
                vm_data["state"] = "UNKNOWN"
            
            vms_with_realtime_state.append(vm_data)
            
        return vms_with_realtime_state

    def _map_vm_state(self, state_code):
        """libvirt의 정수 상태 코드를 사람이 읽을 수 있는 문자열로 변환합니다."""
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

    def destroy_vm(self, vm_name):
        """VM의 모든 리소스를 정리하고 DB에서 기록을 삭제합니다. 중간에 오류가 발생해도 끝까지 정리을 시도합니다."""
        safe_vm_name = os.path.basename(vm_name)
        if safe_vm_name != vm_name:
            raise ValueError(f"Invalid characters in VM name: '{vm_name}'")

        # 1. DB에서 VM 정보 조회. 없으면 여기서 중단.
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT uuid FROM vms WHERE name = ?", (safe_vm_name,))
            db_record = cursor.fetchone()
            if db_record is None:
                raise VmNotFoundError(f"VM '{safe_vm_name}' not found in database.")
            vm_uuid = db_record["uuid"]

        try:
            # 2. Libvirt 리소스 정리 시도
            try:
                domain = self.conn.lookupByUUIDString(vm_uuid)
                if domain.isActive():
                    domain.destroy() # 강제 종료
                domain.undefine()    # 정의 제거
                print(f"Libvirt Info: Domain for VM '{safe_vm_name}' cleaned up.")
            except libvirt.libvirtError as e:
                # 이미 삭제되었거나 다른 libvirt 오류 발생 시, 경고만 남기고 계속 진행
                print(f"Libvirt Warning: Failed to clean up domain for VM '{safe_vm_name}': {e}. Proceeding cleanup.")

            # 3. 디스크 리소스 정리 시도
            disk_filepath = os.path.join("/var/lib/libvirt/images", f"{safe_vm_name}.qcow2")
            try:
                # ImageService를 사용하는 것이 더 일관성 있음 (추후 리팩토링 가능)
                subprocess.run(['sudo', 'rm', '-f', disk_filepath], check=True)
                print(f"Disk Info: Disk for VM '{safe_vm_name}' deleted.")
            except subprocess.CalledProcessError as e:
                print(f"Disk Cleanup Warning: Failed to delete disk '{disk_filepath}': {e}. Proceeding cleanup.")
        
        finally:
            # 4. 최종적으로 DB에서 VM 기록 삭제 (가장 중요)
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM vms WHERE name = ?", (safe_vm_name,))
                conn.commit()
                print(f"DB Info: Record for VM '{safe_vm_name}' deleted.")

        return True

    def reconcile_vms(self):
        """
        Libvirt와 DB의 VM 목록을 비교하여 불일치하는 '유령 VM'을 찾아냅니다.
        (DB에는 없지만 Libvirt에는 존재하는 VM)
        """
        # 1. Libvirt에서 모든 VM의 UUID 조회
        try:
            all_domains = self.conn.listAllDomains(0)
            libvirt_uuids = {domain.UUIDString() for domain in all_domains}
        except libvirt.libvirtError as e:
            print(f"Error fetching domains from libvirt: {e}")
            return []

        # 2. DB에서 모든 VM의 UUID 조회
        db_uuids = set()
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT uuid FROM vms")
            rows = cursor.fetchall()
            db_uuids = {row['uuid'] for row in rows}

        # 3. 두 목록을 비교하여 '유령 VM'의 UUID를 식별
        ghost_vm_uuids = libvirt_uuids - db_uuids

        # 4. '유령 VM'의 상세 정보 (이름, UUID)를 조회하여 반환
        ghost_vms = []
        if ghost_vm_uuids:
            for uuid in ghost_vm_uuids:
                try:
                    domain = self.conn.lookupByUUIDString(uuid)
                    ghost_vms.append({
                        "name": domain.name(),
                        "uuid": uuid,
                        "state": self._map_vm_state(domain.info()[0])
                    })
                except libvirt.libvirtError:
                    # UUID로 조회가 실패하는 경우는 거의 없지만, 방어 코드 추가
                    continue
        
        return ghost_vms

    def __del__(self):
        if self.conn:
            self.conn.close()