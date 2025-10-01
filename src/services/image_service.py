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