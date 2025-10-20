from typing import List, Optional
from sqlalchemy.orm import Session
from src.database import models
from src.repositories.interfaces import IVMRepository

class SqlalchemyVMRepository(IVMRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, vm_model: models.VM) -> models.VM:
        self.db.add(vm_model)
        self.db.commit()
        self.db.refresh(vm_model)
        return vm_model

    def find_by_name_and_project_id(self, name: str, project_id: int) -> Optional[models.VM]:
        return self.db.query(models.VM).filter(
            models.VM.name == name, 
            models.VM.project_id == project_id
        ).first()

    def list_by_project_id(self, project_id: int) -> List[models.VM]:
        return self.db.query(models.VM).filter(models.VM.project_id == project_id).order_by(models.VM.created_at.desc()).all()

    def list_all_uuids(self) -> List[str]:
        return [row[0] for row in self.db.query(models.VM.uuid).all()]

    def delete(self, vm: models.VM) -> bool:
        if vm:
            self.db.delete(vm)
            self.db.commit()
            return True
        return False

    def count_by_project_id(self, project_id: int) -> int:
        return self.db.query(models.VM).filter(models.VM.project_id == project_id).count()