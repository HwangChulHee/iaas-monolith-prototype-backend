from abc import ABC, abstractmethod
from typing import Optional
from src.database import models

class IRoleRepository(ABC):
    @abstractmethod
    def find_by_name(self, name: str) -> Optional[models.Role]:
        """이름으로 특정 역할을 조회합니다."""
        pass
