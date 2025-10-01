# src/database/db_connector.py
import sqlite3
import os
from pathlib import Path

# DB 파일 경로: db_init.py와 동일한 방식으로 프로젝트 루트의 DB 파일 지정
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_FILE = str(PROJECT_ROOT / 'iaas_metadata.db')

class DBConnector:
    """SQLite 연결을 관리하는 Context Manager"""
    def __init__(self):
        self.conn = None

    def __enter__(self):
        # with 블록 시작 시 연결 (DB 파일이 있어야 함)
        self.conn = sqlite3.connect(DB_FILE)
        # 쿼리 결과를 딕셔너리(key-value) 형태로 가져오기 위해 row_factory 설정
        self.conn.row_factory = sqlite3.Row 
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        # with 블록 종료 시 연결 해제
        if self.conn:
            self.conn.close()

# 사용 예시:
# with DBConnector() as conn:
#     cursor = conn.cursor()
#     cursor.execute("SELECT * FROM vms")
#     results = cursor.fetchall()