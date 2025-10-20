from abc import ABC, abstractmethod
from typing import List, Optional
from src.database import models

class IUserRepository(ABC):
    @abstractmethod
    def create(self, user_model: models.User) -> models.User:
        """새로운 사용자를 데이터베이스에 생성합니다."""
        pass

    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[models.User]:
        """고유 ID로 특정 사용자를 조회합니다."""
        pass

    @abstractmethod
    def find_by_username(self, username: str) -> Optional[models.User]:
        """사용자 이름으로 특정 사용자를 조회합니다."""
        pass

    @abstractmethod
    def list_all(self) -> List[models.User]:
        """모든 사용자의 목록을 조회합니다."""
        pass

    @abstractmethod
    def delete(self, user: models.User) -> bool:
        """특정 사용자를 데이터베이스에서 삭제합니다."""
        pass
