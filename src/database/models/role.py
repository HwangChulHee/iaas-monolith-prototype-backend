from sqlalchemy import Column, Integer, String
from ..database import Base

class Role(Base):
    """
    사용자가 프로젝트 내에서 가질 수 있는 권한의 집합을 정의합니다.
    (예: 'admin', 'member').
    RBAC(역할 기반 접근 제어)의 핵심 요소입니다.
    """
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
