# src/services/image_service.py
import subprocess
import os
import shutil

class ImageService:
    @staticmethod
    def create_vm_disk(vm_name, source_filepath):
        """
        CoW (Copy-on-Write) 방식으로 원본 이미지(source_filepath)를 기반으로
        새 VM 디스크(복제본)를 생성합니다. (qemu-img create -f qcow2 -b ...)
        """
        # 새 VM 디스크의 파일 경로를 정의합니다.
        # libvirt 표준 경로를 사용하고, VM 이름을 파일명으로 사용합니다.
        target_dir = "/var/lib/libvirt/images"
        target_filename = f"{vm_name}.qcow2"
        target_filepath = os.path.join(target_dir, target_filename)

        if not os.path.exists(source_filepath):
            raise FileNotFoundError(f"Source image file not found: {source_filepath}")
        
        # ⚠️ WARNING: /var/lib/libvirt/images는 root 권한이 필요합니다.
        # 현재는 sudoers 파일에 권한을 추가하지 않았다고 가정하고 subprocess.run을 사용합니다.
        
        try:
            # qemu-img create -f qcow2 -b [원본 이미지] [새 디스크 경로]
            command = [
                'sudo', 'qemu-img', 'create', 
                '-f', 'qcow2', 
                '-F', 'qcow2',  # 👈 원본 파일(Backing file)의 포맷 명시
                '-b', source_filepath, 
                target_filepath
            ]
            
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            print(f"Disk creation output: {result.stdout}")

        except subprocess.CalledProcessError as e:
            # 권한 문제, 파일 시스템 문제 등 에러가 발생했을 때
            raise Exception(f"Failed to create CoW disk for {vm_name}: {e.stderr}")
        except FileNotFoundError:
            # sudo나 qemu-img 명령어를 찾지 못할 때
            raise Exception("qemu-img command not found. Install qemu-utils.")
            
        # 새로 생성된 디스크 파일 경로 반환
        return target_filepath
  
    @staticmethod
    def delete_vm_disk(disk_filepath):
        """
        VM 생성 시 복제된 디스크 파일을 삭제합니다. (롤백용)
        """
        # 디스크 파일 경로 조작 방지 (basename을 쓰지 않도록 주의. 전체 경로를 받아야 함.)
        
        if not os.path.exists(disk_filepath):
            # 파일이 없으면 그냥 통과
            print(f"Disk file not found, skipping delete: {disk_filepath}")
            return True

        try:
            # ⚠️ WARNING: /var/lib/libvirt/images 경로이므로 sudo 권한이 필요합니다.
            subprocess.run(['sudo', 'rm', '-f', disk_filepath], check=True)
            print(f"Disk file successfully deleted: {disk_filepath}")
            return True
        except subprocess.CalledProcessError as e:
            # 삭제 실패 시 예외 발생
            raise Exception(f"Failed to delete disk file '{disk_filepath}': {e.stderr}")