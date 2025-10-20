from abc import ABC, abstractmethod
from typing import Optional
from src.database import models

class IImageRepository(ABC):
    @abstractmethod
    def find_by_name(self, name: str) -> Optional[models.Image]:
        """이름으로 특정 이미지를 조회합니다."""
        pass
