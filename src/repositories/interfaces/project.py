from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from src.database import models

class IProjectRepository(ABC):
    @abstractmethod
    def create(self, project_model: models.Project) -> models.Project:
        """새로운 프로젝트를 데이터베이스에 생성합니다."""
        pass

    @abstractmethod
    def find_by_id(self, project_id: int) -> Optional[models.Project]:
        """고유 ID로 특정 프로젝트를 조회합니다."""
        pass

    @abstractmethod
    def find_by_name(self, name: str) -> Optional[models.Project]:
        """이름으로 특정 프로젝트를 조회합니다."""
        pass

    @abstractmethod
    def list_all(self) -> List[models.Project]:
        """모든 프로젝트의 목록을 조회합니다."""
        pass

    @abstractmethod
    def delete(self, project: models.Project) -> bool:
        """특정 프로젝트를 데이터베이스에서 삭제합니다."""
        pass

    @abstractmethod
    def list_members(self, project_id: int) -> List[Dict[str, Any]]:
        """
        특정 프로젝트에 속한 모든 사용자와 그들의 역할을 조회합니다.

        Args:
            project_id: 멤버를 조회할 프로젝트의 ID.

        Returns:
            사용자 정보(id, username)와 역할(role)이 포함된 딕셔너리의 리스트.
            (예: [{'id': 1, 'username': 'admin', 'role': 'admin'}])
        """
        pass

    @abstractmethod
    def assign_role_to_user(self, user: models.User, project: models.Project, role: models.Role):
        """특정 사용자에게 프로젝트 역할을 부여합니다. 이미 역할이 존재하면 무시합니다."""
        pass

    @abstractmethod
    def revoke_role_from_user(self, user: models.User, project: models.Project, role: models.Role):
        """사용자의 특정 프로젝트 역할을 회수합니다."""
        pass
