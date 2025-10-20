from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from src.database import models
from src.repositories.interfaces import IProjectRepository

class SqlalchemyProjectRepository(IProjectRepository):
    def __init__(self, db_session: Session):
        self.db = db_session

    def create(self, project_model: models.Project) -> models.Project:
        self.db.add(project_model)
        self.db.commit()
        self.db.refresh(project_model)
        return project_model

    def find_by_id(self, project_id: int) -> Optional[models.Project]:
        return self.db.query(models.Project).filter(models.Project.id == project_id).first()

    def find_by_name(self, name: str) -> Optional[models.Project]:
        return self.db.query(models.Project).filter(models.Project.name == name).first()

    def list_all(self) -> List[models.Project]:
        return self.db.query(models.Project).order_by(models.Project.name.asc()).all()

    def delete(self, project: models.Project) -> bool:
        if project:
            self.db.delete(project)
            self.db.commit()
            return True
        return False

    def list_members(self, project_id: int) -> List[Dict[str, Any]]:
        project = self.db.query(models.Project).options(joinedload(models.Project.user_associations).joinedload(models.UserProjectRole.user), joinedload(models.Project.user_associations).joinedload(models.UserProjectRole.role)).filter(models.Project.id == project_id).first()
        if not project:
            return []
        
        members = []
        for assoc in project.user_associations:
            members.append({
                "id": assoc.user.id,
                "username": assoc.user.username,
                "role": assoc.role.name
            })
        return members

    def assign_role_to_user(self, user: models.User, project: models.Project, role: models.Role):
        association = models.UserProjectRole(user_id=user.id, project_id=project.id, role_id=role.id)
        self.db.merge(association) # INSERT OR IGNORE와 유사한 동작
        self.db.commit()

    def revoke_role_from_user(self, user: models.User, project: models.Project, role: models.Role):
        association = self.db.query(models.UserProjectRole).filter(
            models.UserProjectRole.user_id == user.id,
            models.UserProjectRole.project_id == project.id,
            models.UserProjectRole.role_id == role.id
        ).first()
        if association:
            self.db.delete(association)
            self.db.commit()
