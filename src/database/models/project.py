from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from ..database import Base

class Project(Base):
    """
    하나의 격리된 테넌트(tenant) 또는 작업 공간을 나타냅니다.
    모든 VM, 사용자 멤버십은 이 Project 모델에 종속됩니다.
    OpenStack의 'Project' 또는 AWS의 'Account'와 유사한 개념입니다.
    """
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)

    vms = relationship("VM", back_populates="project", cascade="all, delete-orphan")
    user_associations = relationship("UserProjectRole", back_populates="project", cascade="all, delete-orphan")
