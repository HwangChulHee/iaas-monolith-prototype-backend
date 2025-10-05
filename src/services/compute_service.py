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
        """VM을 강제 종료/삭제하고, 디스크 파일을 삭제한 후 DB 기록을 제거합니다."""
        safe_vm_name = os.path.basename(vm_name)
        if safe_vm_name != vm_name:
            raise ValueError(f"Invalid characters in VM name: '{vm_name}'")

        vm_uuid = None
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT uuid FROM vms WHERE name = ?", (safe_vm_name,))
            db_record = cursor.fetchone()
            if db_record is None:
                raise VmNotFoundError(f"VM '{safe_vm_name}' not found.")
            vm_uuid = db_record["uuid"]

        try:
            domain = self.conn.lookupByUUIDString(vm_uuid)
            if domain.isActive():
                domain.destroy()
            domain.undefine()
        except libvirt.libvirtError as e:
            error_msg = str(e)
            if "Domain not found" in error_msg or "no domain with matching" in error_msg:
                print(f"Libvirt Info: VM '{safe_vm_name}' not found, proceeding with cleanup.")
            else:
                print(f"Libvirt Warning: {e}. Proceeding with cleanup.")

        DISK_IMAGE_PATH_BASE = "/var/lib/libvirt/images"
        disk_filepath = os.path.join(DISK_IMAGE_PATH_BASE, f"{safe_vm_name}.qcow2")
        try:
            subprocess.run(['sudo', 'rm', '-f', disk_filepath], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Subprocess Error: 'sudo rm -f' for disk '{disk_filepath}' failed: {e}. Continuing cleanup.")

        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vms WHERE name = ?", (safe_vm_name,))
            conn.commit()

        return True

    def __del__(self):
        if self.conn:
            self.conn.close()