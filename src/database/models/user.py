from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from ..database import Base

class User(Base):
    """
    시스템에 로그인하고 리소스를 소유할 수 있는 사용자를 나타냅니다.
    사용자는 하나 이상의 프로젝트에 다양한 역할(Role)로 소속될 수 있습니다.
    OpenStack의 'User'와 동일한 개념입니다.
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)

    project_associations = relationship("UserProjectRole", back_populates="user", cascade="all, delete-orphan")
