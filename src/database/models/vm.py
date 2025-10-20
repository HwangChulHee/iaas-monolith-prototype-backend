from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base

class VM(Base):
    """
    사용자가 생성하고 관리하는 가상 머신(인스턴스)을 나타냅니다.
    CPU, RAM, 디스크 등의 리소스를 가지며, 특정 프로젝트에 소속됩니다.
    OpenStack의 'Server' 또는 AWS의 'EC2 Instance'에 해당합니다.
    """
    __tablename__ = "vms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    uuid = Column(String, unique=True, nullable=False)
    state = Column(String, nullable=False)
    cpu_count = Column(Integer, nullable=False)
    ram_mb = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    project = relationship("Project", back_populates="vms")
