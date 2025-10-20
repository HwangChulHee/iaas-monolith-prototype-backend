from typing import List, Optional
from sqlalchemy.orm import Session
from src.database import models
from src.repositories.interfaces import IUserRepository

class SqlalchemyUserRepository(IUserRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, user_model: models.User) -> models.User:
        self.db.add(user_model)
        self.db.commit()
        self.db.refresh(user_model)
        return user_model

    def find_by_id(self, user_id: int) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def find_by_username(self, username: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.username == username).first()

    def list_all(self) -> List[models.User]:
        return self.db.query(models.User).order_by(models.User.username.asc()).all()

    def delete(self, user: models.User) -> bool:
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        return False
