from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 데이터베이스 연결 문자열 (여기서는 SQLite 사용)
# 실제 애플리케이션에서는 이 부분을 설정 파일로 분리하는 것이 좋습니다.
SQLALCHEMY_DATABASE_URL = "sqlite:///iaas_metadata.db"

# SQLAlchemy 엔진 생성
# connect_args는 SQLite에서만 필요합니다. (thread-safe 설정)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 데이터베이스 세션 생성을 위한 SessionLocal 클래스
# autocommit=False, autoflush=False로 설정하여, 명시적으로 commit을 호출해야 DB에 반영됩니다.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모든 모델 클래스가 상속받을 Base 클래스
# 이 클래스를 상속받아 모델을 정의하면, SQLAlchemy가 테이블을 인식합니다.
Base = declarative_base()
