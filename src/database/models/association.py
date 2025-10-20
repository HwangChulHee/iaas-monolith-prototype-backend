from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class UserProjectRole(Base):
    """
    사용자(User), 프로젝트(Project), 역할(Role) 사이의 다대다(many-to-many) 관계를
    연결하는 연관 테이블(Association Table) 모델입니다.
    어떤 사용자가 어떤 프로젝트에서 어떤 역할을 가지는지를 명시적으로 정의합니다.
    """
    __tablename__ = 'user_project_roles'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True)
    role_id = Column(Integer, ForeignKey('roles.id'), primary_key=True)

    user = relationship("User", back_populates="project_associations")
    project = relationship("Project", back_populates="user_associations")
    role = relationship("Role")
