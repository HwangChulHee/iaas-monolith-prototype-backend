from typing import Optional
from sqlalchemy.orm import Session
from src.database import models
from src.repositories.interfaces import IImageRepository

class SqlalchemyImageRepository(IImageRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def find_by_name(self, name: str) -> Optional[models.Image]:
        return self.db.query(models.Image).filter(models.Image.name == name).first()
