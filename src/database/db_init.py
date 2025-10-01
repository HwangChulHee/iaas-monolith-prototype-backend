# src/database/db_init.py
import sqlite3
import os
from pathlib import Path

# DB 파일 경로: 프로젝트 루트 디렉토리에 'iaas_metadata.db' 파일을 생성
# __file__ (db_init.py) -> src/database -> src -> iaas_project (루트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = str(PROJECT_ROOT / 'iaas_metadata.db')

# VM 메타데이터를 저장할 테이블 정의 (DDL)
VM_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS vms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,       -- VM 고유 이름 (중복 방지 핵심)
    uuid TEXT NOT NULL UNIQUE,       -- Libvirt에서 할당한 고유 ID
    state TEXT NOT NULL,             -- 'running', 'shut off', 'paused', 'error' 등
    cpu_count INTEGER NOT NULL,
    ram_mb INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

# 💥 VM 이미지 테이블 (추가)
IMAGE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,       -- 사용자가 볼 이미지 이름 (예: Ubuntu 22.04 LTS)
    filepath TEXT NOT NULL,          -- libvirt가 사용하는 실제 qcow2 파일 경로
    min_disk_gb INTEGER,
    min_ram_mb INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

def initialize_db():
    """DB 파일 생성 및 vms 테이블을 초기화합니다."""
    print(f"DB 초기화 중: {DB_FILE}")
    conn = None
    try:
        # DB 파일에 연결 (파일이 없으면 새로 생성)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. vms 테이블 생성
        cursor.execute(VM_TABLE_DDL)
        
         # 2. images 테이블 생성
        cursor.execute(IMAGE_TABLE_DDL)
        
        # 3. 기본 이미지 정보 삽입 (INSERT OR IGNORE)
        # 네가 가진 이미지를 기반으로 기본 데이터를 넣어준다.
        cursor.execute("""
            INSERT OR IGNORE INTO images (name, filepath, min_disk_gb, min_ram_mb) 
            VALUES (?, ?, ?, ?)
        """, ('Ubuntu-Base-22.04', '/var/lib/libvirt/images/ubuntu-test.qcow2', 20, 1024))
        
        conn.commit()
        print("vms 테이블 초기화 완료.")
        
    except sqlite3.Error as e:
        print(f"SQLite 오류 발생: {e}")
        
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    initialize_db()