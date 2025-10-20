from sqlalchemy import Column, Integer, String, DateTime, func
from ..database import Base

class Image(Base):
    """
    VM을 생성할 때 사용하는 부팅 가능한 디스크 템플릿을 정의합니다.
    (예: 'Ubuntu-22.04-Base').
    OpenStack의 'Image' 또는 AWS의 'AMI'와 동일한 개념입니다.
    """
    __tablename__ = "images"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    filepath = Column(String, nullable=False)
    min_disk_gb = Column(Integer)
    min_ram_mb = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
