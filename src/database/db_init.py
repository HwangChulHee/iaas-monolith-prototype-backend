import hashlib
from .database import engine, SessionLocal, Base
from .models import *

def initialize_db():
    """
    DB와 테이블을 생성하고, 기본 데이터를 삽입합니다.
    SQLAlchemy 모델을 사용하여 모든 작업을 수행합니다.
    """
    print("DB 초기화 중 (SQLAlchemy 사용)...")

    # 모든 테이블을 생성합니다. (이미 존재하면 생성하지 않음)
    Base.metadata.create_all(bind=engine)
    print("테이블 생성 완료.")

    db = SessionLocal()
    try:
        # 기본 데이터가 이미 있는지 확인
        if db.query(User).first():
            print("기본 데이터가 이미 존재합니다. 초기화를 건너뜁니다.")
            return

        print("기본 데이터 삽입 중...")

        # Roles
        admin_role = Role(name='admin')
        member_role = Role(name='member')
        db.add(admin_role)
        db.add(member_role)

        # Project
        default_project = Project(name='default')
        db.add(default_project)

        # User
        password = 'admin'
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        admin_user = User(username='admin', password_hash=password_hash)
        db.add(admin_user)
        
        # 변경사항을 커밋하여 각 객체의 id를 할당받습니다.
        db.commit()

        # User-Project-Role Mapping (명시적 관계 설정)
        association = UserProjectRole(
            user_id=admin_user.id,
            project_id=default_project.id,
            role_id=admin_role.id
        )
        db.add(association)

        # Base Image
        base_image = Image(
            name='Ubuntu-Base-22.04',
            filepath='/var/lib/libvirt/images/ubuntu-test.qcow2',
            min_disk_gb=20,
            min_ram_mb=1024
        )
        db.add(base_image)

        db.commit()
        print("DB 초기화 및 기본 데이터 삽입 완료.")

    except Exception as e:
        print(f"오류 발생: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    initialize_db()