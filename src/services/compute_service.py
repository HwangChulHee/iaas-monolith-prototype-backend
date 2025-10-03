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

class ComputeService:
    def __init__(self, uri="qemu:///system"):
        self.conn = libvirt.open(uri)
        if self.conn is None:
            raise Exception("Failed to open connection to the hypervisor.")

    def create_vm(self, vm_name, cpu_count, ram_mb, image_name):
        """VM을 생성하고, 성공 시 디스크 복제 후 메타데이터를 DB에 저장합니다."""
        
        # 1. DB에서 VM 이름 중복 여부 확인 및 원본 이미지 경로 조회
        source_filepath = None
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM vms WHERE name = ?", (vm_name,))
            if cursor.fetchone():
                raise Exception(f"VM name '{vm_name}' already exists in database.")
            cursor.execute("SELECT filepath FROM images WHERE name = ?", (image_name,))
            image_row = cursor.fetchone()
            if not image_row:
                raise Exception(f"Image name '{image_name}' not found in database. Check 'Ubuntu-Base-22.04'.")
            source_filepath = image_row["filepath"]

        # 2. ImageService를 통해 VM 전용 디스크 복제 (CoW)
        try:
            vm_disk_filepath = ImageService.create_vm_disk(vm_name, source_filepath)
        except Exception as e:
            raise Exception(f"Disk clone failed: {e}")

        # 3. VM의 고유 UUID 생성 및 XML 설정 정의
        vm_uuid = str(uuid.uuid4())
        xml_config = generate_vm_xml(vm_name, vm_uuid, cpu_count, ram_mb, vm_disk_filepath)

        # 4. Libvirt를 통해 VM을 정의하고 시작
        try:
            domain = self.conn.defineXML(xml_config)
            if domain.create() < 0:
                raise Exception("Failed to start the VM.")
        except libvirt.libvirtError as e:
            raise Exception(f"Libvirt operation failed: {e}")

        # 5. 성공 시, VM 메타데이터를 DB에 최종 저장
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
        except Exception as db_e:
            raise Exception(f"VM created, but DB save failed: {db_e}")

        return vm_name, vm_uuid

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