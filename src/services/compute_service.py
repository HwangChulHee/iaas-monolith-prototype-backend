# src/services/compute_service.py
import libvirt
import sqlite3
import uuid # UUID 생성을 위해 필요
from datetime import datetime

# DB 및 XML 유틸리티 임포트 (네가 만든 파일들)
from database.db_connector import DBConnector 
from utils.vm_xml_generator import generate_vm_xml 
from services.image_service import ImageService

class ComputeService:
    def __init__(self, uri='qemu:///system'):
        self.conn = libvirt.open(uri)
        if self.conn is None:
            raise Exception('Failed to open connection to the hypervisor.')

    # --------------------------------------------------------------------------
    # 💥 VM 생성 (DB 체크 + 디스크 복제 + XML 생성 + Libvirt 호출 + DB 저장)
    # --------------------------------------------------------------------------
    def create_vm(self, vm_name, cpu_count, ram_mb, image_name): # 👈 image_name 인자 추가
        """VM을 생성하고, 성공 시 디스크 복제 후 메타데이터를 DB에 저장합니다."""
        
        # 1. 🛡️ DB에서 VM 이름 중복 체크 및 이미지 정보 조회
        source_filepath = None
        with DBConnector() as conn:
            cursor = conn.cursor()
            
            # 1-1. VM 이름 중복 체크
            cursor.execute("SELECT name FROM vms WHERE name = ?", (vm_name,))
            if cursor.fetchone():
                raise Exception(f"VM name '{vm_name}' already exists in database.")
                
            # 1-2. 이미지 경로 조회 (원본 이미지 파일 경로)
            cursor.execute("SELECT filepath FROM images WHERE name = ?", (image_name,))
            image_row = cursor.fetchone()
            if not image_row:
                raise Exception(f"Image name '{image_name}' not found in database. Check 'Ubuntu-Base-22.04'.")
            
            source_filepath = image_row['filepath']

        # 2. 💡 디스크 복제 및 새 경로 확보 (CoW 방식) 👈 핵심 로직
        try:
            # ImageService를 호출하여 새로운 VM 전용 디스크(복제본) 생성
            vm_disk_filepath = ImageService.create_vm_disk(vm_name, source_filepath)
        except Exception as e:
            raise Exception(f"Disk clone failed: {e}")
            
        # 3. 💡 동적 XML 생성 및 Libvirt에 요청
        vm_uuid = str(uuid.uuid4())
        
        # 💥 동적 XML 생성 함수에 복제된 디스크 경로 전달 💥
        xml_config = generate_vm_xml(vm_name, vm_uuid, cpu_count, ram_mb, vm_disk_filepath) 

        try:
            # Libvirt에 VM 정의 및 시작 요청
            domain = self.conn.defineXML(xml_config)
            if domain.create() < 0:
                 raise Exception('Failed to start the VM.')
            
        except libvirt.libvirtError as e:
            # Libvirt 에러 발생 시 (ex: KVM 오류)
            # ⚠️ TODO: VM 생성 실패 시, 생성된 디스크 복제본(vm_disk_filepath)을 삭제하는 롤백 로직이 필요함.
            raise Exception(f"Libvirt operation failed: {e}")

        # 4. 💾 VM 생성 성공 후 DB에 메타데이터 저장 (영속성 확보)
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO vms (name, uuid, state, cpu_count, ram_mb, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (vm_name, vm_uuid, 'running', cpu_count, ram_mb, datetime.now()))
                conn.commit()
        except Exception as db_e:
            # VM은 생성됐으나 DB 저장이 실패했다면 치명적인 에러로 처리
            # ⚠️ TODO: DB 저장 실패 시, Libvirt에 생성된 VM을 제거하는 롤백 로직이 필요함.
            raise Exception(f"VM created, but DB save failed: {db_e}")

        return vm_name, vm_uuid

    # --------------------------------------------------------------------------
    # VM 목록 조회 (DB 기반)
    # --------------------------------------------------------------------------
    def list_vms(self):
        """DB에서 모든 VM 목록을 조회합니다."""
        with DBConnector() as conn:
            # row_factory는 DBConnector에서 설정했으므로 바로 fetchall() 사용
            cursor = conn.cursor()
            cursor.execute("SELECT name, uuid, state, cpu_count, ram_mb, created_at FROM vms ORDER BY created_at DESC")
            vms_data = cursor.fetchall()
            
            # DB 결과를 딕셔너리 리스트로 변환하여 반환
            return [dict(row) for row in vms_data]

    # --------------------------------------------------------------------------
    # VM 삭제 (DB 제거 + Libvirt 제거)
    # --------------------------------------------------------------------------
    def destroy_vm(self, vm_name):
        """VM을 강제 종료/삭제하고 DB에서도 기록을 제거합니다."""
        vm_uuid = None
        
        # 1. 🔍 DB에서 VM의 UUID를 먼저 조회
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT uuid FROM vms WHERE name = ?", (vm_name,))
            row = cursor.fetchone()
            if not row:
                raise Exception(f"VM name '{vm_name}' not found in database.")
            vm_uuid = row['uuid']

        # 2. 💣 Libvirt에서 VM 제거
        try:
            domain = self.conn.lookupByUUIDString(vm_uuid)
            domain.destroy() # 강제 종료
            domain.undefine() # 영구 삭제
        except libvirt.libvirtError as e:
            # VM이 libvirt에는 없으나 DB에만 남아있는 경우 (정상 삭제로 간주)
            print(f"Warning: VM {vm_name} not found in libvirt or already undefine, proceeding with DB removal.")
            pass

        # 3. 🗑️ DB에서 레코드 제거 (영구 삭제)
        with DBConnector() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vms WHERE uuid = ?", (vm_uuid,))
            conn.commit()
            
        return True

    def __del__(self):
        if self.conn:
            self.conn.close()