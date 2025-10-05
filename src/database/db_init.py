# src/database/db_init.py
import sqlite3
import os
from pathlib import Path
import hashlib

# DB 파일 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = str(PROJECT_ROOT / 'iaas_metadata.db')

# 테이블 DDL 정의
PROJECTS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
"""

USERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
"""

ROLES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
"""

USER_PROJECT_ROLES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS user_project_roles (
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (project_id) REFERENCES projects (id),
    FOREIGN KEY (role_id) REFERENCES roles (id),
    PRIMARY KEY (user_id, project_id, role_id)
);
"""

VM_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS vms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    uuid TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    cpu_count INTEGER NOT NULL,
    ram_mb INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (id)
);
"""

IMAGE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    filepath TEXT NOT NULL,
    min_disk_gb INTEGER,
    min_ram_mb INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_db():
    """DB 파일 및 모든 테이블을 생성/초기화하고 기본 데이터를 삽입합니다."""
    print(f"DB 초기화 중: {DB_FILE}")
    # 기존 DB 파일이 있다면 삭제하여 깨끗한 상태에서 시작
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print("기존 DB 파일 삭제 완료.")

    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 테이블 생성
        print("테이블 생성 중...")
        cursor.execute(PROJECTS_TABLE_DDL)
        cursor.execute(USERS_TABLE_DDL)
        cursor.execute(ROLES_TABLE_DDL)
        cursor.execute(USER_PROJECT_ROLES_TABLE_DDL)
        cursor.execute(VM_TABLE_DDL) # vms 테이블은 새로 만들어야 project_id 적용 가능
        cursor.execute(IMAGE_TABLE_DDL)
        print("테이블 생성 완료.")

        # 기본 데이터 삽입
        print("기본 데이터 삽입 중...")
        # Roles
        cursor.execute("INSERT INTO roles (name) VALUES ('admin'), ('member');")
        
        # Project
        cursor.execute("INSERT INTO projects (name) VALUES ('default');")
        default_project_id = cursor.lastrowid
        
        # User (비밀번호 'admin'을 해시하여 저장)
        password = 'admin'
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?);", ('admin', password_hash))
        admin_user_id = cursor.lastrowid
        
        # User-Project-Role Mapping
        admin_role_id = 1 # 'admin'
        cursor.execute("INSERT INTO user_project_roles (user_id, project_id, role_id) VALUES (?, ?, ?);", 
                       (admin_user_id, default_project_id, admin_role_id))

        # Base Image
        cursor.execute("""
            INSERT OR IGNORE INTO images (name, filepath, min_disk_gb, min_ram_mb) 
            VALUES (?, ?, ?, ?)
        """, ('Ubuntu-Base-22.04', '/var/lib/libvirt/images/ubuntu-test.qcow2', 20, 1024))
        
        conn.commit()
        print("DB 초기화 및 기본 데이터 삽입 완료.")
        
    except sqlite3.Error as e:
        print(f"SQLite 오류 발생: {e}")
        
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    initialize_db()