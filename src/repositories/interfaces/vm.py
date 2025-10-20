from abc import ABC, abstractmethod
from typing import List, Optional
from src.database import models

class IVMRepository(ABC):
    @abstractmethod
    def create(self, vm_model: models.VM) -> models.VM:
        """새로운 VM 정보를 데이터베이스에 생성합니다."""
        pass

    @abstractmethod
    def find_by_name_and_project_id(self, name: str, project_id: int) -> Optional[models.VM]:
        """프로젝트 내에서 이름으로 특정 VM을 조회합니다."""
        pass

    @abstractmethod
    def list_by_project_id(self, project_id: int) -> List[models.VM]:
        """특정 프로젝트에 속한 모든 VM의 목록을 조회합니다."""
        pass

    @abstractmethod
    def list_all_uuids(self) -> List[str]:
        """데이터베이스에 있는 모든 VM의 UUID 목록을 조회합니다."""
        pass

    @abstractmethod
    def delete(self, vm: models.VM) -> bool:
        """특정 VM 정보를 데이터베이스에서 삭제합니다."""
        pass

    @abstractmethod
    def count_by_project_id(self, project_id: int) -> int:
        """특정 프로젝트에 속한 VM의 개수를 조회합니다."""
        pass
