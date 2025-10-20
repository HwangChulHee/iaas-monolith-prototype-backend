import subprocess
import os
from typing import Optional

from src.repositories.interfaces import IImageRepository
from src.services.exceptions import ImageNotFoundError

class ImageService:
    def __init__(self, image_repo: IImageRepository):
        """
        ImageService를 초기화합니다.

        Args:
            image_repo: 이미지 데이터에 접근하기 위한 리포지토리 객체.
        """
        self.image_repo = image_repo
        self.image_base_dir = "/var/lib/libvirt/images"

    def validate_image_and_get_path(self, image_name: str) -> str:
        """
        DB에서 이미지를 찾아 유효성을 검사하고, 존재하면 파일 경로를 반환합니다.

        Args:
            image_name: 검증할 이미지의 이름.

        Returns:
            이미지의 실제 파일 시스템 경로.

        Raises:
            ImageNotFoundError: DB에서 해당 이름의 이미지를 찾지 못했을 때.
            FileNotFoundError: DB에는 기록이 있으나 실제 이미지 파일이 없을 때.
        """
        image = self.image_repo.find_by_name(image_name)
        if not image:
            raise ImageNotFoundError(f"Image '{image_name}' not found in database.")
        
        if not os.path.exists(image.filepath):
            # DB에는 있지만 실제 파일이 없는 경우
            raise FileNotFoundError(f"Source image file not found on disk: {image.filepath}")
            
        return image.filepath

    def create_vm_disk(self, vm_name: str, source_filepath: str) -> str:
        """
        CoW(Copy-on-Write) 방식으로 새 VM 디스크를 생성합니다.

        qemu-img 유틸리티를 사용하여 원본 이미지를 backing file으로 하는
        새로운 qcow2 디스크 이미지를 생성합니다.

        Args:
            vm_name: 생성할 VM의 이름. 새 디스크 파일명에 사용됩니다.
            source_filepath: 원본이 될 backing file의 경로.

        Returns:
            새로 생성된 VM 디스크의 전체 경로.

        Raises:
            Exception: 디스크 생성에 실패했을 때.
        """
        target_filename = f"{vm_name}.qcow2"
        target_filepath = os.path.join(self.image_base_dir, target_filename)

        try:
            command = [
                'sudo', 'qemu-img', 'create', 
                '-f', 'qcow2', 
                '-F', 'qcow2',
                '-b', source_filepath, 
                target_filepath
            ]
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to create CoW disk for {vm_name}: {e.stderr}")
        except FileNotFoundError:
            raise Exception("qemu-img command not found. Install qemu-utils.")
            
        return target_filepath
  
    def delete_vm_disk(self, disk_filepath: str) -> bool:
        """
        VM 디스크 파일을 삭제합니다. 주로 VM 생성 실패 시 롤백에 사용됩니다.

        Args:
            disk_filepath: 삭제할 디스크 파일의 전체 경로.

        Returns:
            성공적으로 삭제되었거나 파일이 원래 없었으면 True를 반환합니다.

        Raises:
            Exception: 디스크 파일 삭제에 실패했을 때.
        """
        if not os.path.exists(disk_filepath):
            print(f"Disk file not found, skipping delete: {disk_filepath}")
            return True
        try:
            subprocess.run(['sudo', 'rm', '-f', disk_filepath], check=True)
            print(f"Disk file successfully deleted: {disk_filepath}")
            return True
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to delete disk file '{disk_filepath}': {e.stderr}")

    def delete_vm_disk_by_name(self, vm_name: str) -> bool:
        """
        VM 이름을 기반으로 디스크 파일을 찾아 삭제합니다.

        Args:
            vm_name: 삭제할 디스크에 해당하는 VM의 이름.

        Returns:
            성공적으로 삭제되었으면 True를 반환합니다.
        """
        disk_filepath = os.path.join(self.image_base_dir, f"{vm_name}.qcow2")
        return self.delete_vm_disk(disk_filepath)
