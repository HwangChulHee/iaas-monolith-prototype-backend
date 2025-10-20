from typing import Optional
from sqlalchemy.orm import Session
from src.database import models
from src.repositories.interfaces import IRoleRepository

class SqlalchemyRoleRepository(IRoleRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def find_by_name(self, name: str) -> Optional[models.Role]:
        return self.db.query(models.Role).filter(models.Role.name == name).first()
