# ==============================================================================
# IaaS 프로젝트 Makefile (Phase 1 MVP)
# 모든 명령어는 프로젝트 루트 디렉토리에서 실행해야 합니다.
# ==============================================================================

# ------------------------------------------------------------------------------
# 변수 설정
# ------------------------------------------------------------------------------
PYTHON_CMD = python3
APP_FILE = src/app.py
INIT_FILE = src/database/db_init.py

# ------------------------------------------------------------------------------
# 💥 기본 실행 타겟
# ------------------------------------------------------------------------------

# 서버 시작: make serve (python3 src/app.py 실행)
serve:
	@echo "🚀 Starting IaaS Monolith Prototype on port 8000..."
	$(PYTHON_CMD) $(APP_FILE)

# ------------------------------------------------------------------------------
# 🛠️ 환경 관리 타겟
# ------------------------------------------------------------------------------

# DB 초기화: make db-init (vms, images 테이블 생성 및 기본 이미지 삽입)
db-init:
	@echo "💾 Initializing database and inserting base image data..."
	$(PYTHON_CMD) $(INIT_FILE)

# DB 초기화 및 VM 기록 삭제: make db-clean
# images 테이블은 유지하고, vms 테이블의 데이터만 삭제합니다.
db-clean:
	@echo "🧹 Cleaning up VM records in DB..."
	$(PYTHON_CMD) -c "import sqlite3; DB_FILE = 'iaas_metadata.db'; conn = sqlite3.connect(DB_FILE); conn.cursor().execute('DELETE FROM vms'); conn.commit(); conn.close(); print('DB: vms table cleaned.');"
	
# VM 정의 및 디스크 삭제: make vm-cleanup
# libvirt에 등록된 모든 VM 정의를 제거하고, 생성된 디스크 복제본을 삭제합니다. (매우 강력한 청소)
vm-cleanup:
	@echo "🔥 Destroying all running VMs and undefining all definitions..."
	-virsh list --all --name | xargs -r -I {} virsh destroy {} 
	-virsh list --all --name | xargs -r -I {} virsh undefine {}
	@echo "🗑️ Attempting to delete VM disk replicas..."
	-sudo find /var/lib/libvirt/images/ -maxdepth 1 -type f -name '*-vm-*.qcow2' -exec rm -f {} \;
	@echo "Cleanup complete."

# ------------------------------------------------------------------------------
# 🧪 테스트 관련 타겟
# ------------------------------------------------------------------------------

# 특정 테스트 파일 실행: make test file=services/test_compute_service.py
file ?=
test:
	@if [ -z "$(file)" ]; then \
		echo "❌ Error: Please specify a test file."; \
		echo "   Usage: make test file=<path_under_tests_dir>"; \
		exit 1; \
	fi
	@echo "🧪 Running unit test for: tests/$(file)..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest tests/$(file)

# 특정 테스트 파일 실행 (상세 모드): make testv file=services/test_compute_service.py
testv:
	@if [ -z "$(file)" ]; then \
		echo "❌ Error: Please specify a test file."; \
		echo "   Usage: make testv file=<path_under_tests_dir>"; \
		exit 1; \
	fi
	@echo "🧪 Running unit test in verbose mode for: tests/$(file)..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest -v tests/$(file)

# 모든 단위 테스트 실행: make test-all
test-all:
	@echo "🧪 Running all unit tests..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest

# 모든 단위 테스트 실행 (상세 모드): make test-all-v
test-all-v:
	@echo "🧪 Running all unit tests in verbose mode..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest -v

# ------------------------------------------------------------------------------
# 💡 디폴트 명령어 (make help)
# ------------------------------------------------------------------------------
.PHONY: serve db-init db-clean vm-cleanup test testv test-all test-all-v help

help:
	@echo "=================================================================================="
	@echo " IaaS Monolith Prototype Command List (Phase 1 MVP)"
	@echo "=================================================================================="
	@echo " make serve                      : Run the WSGI API server (python3 src/app.py)."
	@echo " make db-init                  : Initialize DB (Create tables & insert base image)."
	@echo " make db-clean                 : Delete all records from the 'vms' table only."
	@echo " make vm-cleanup               : Force destroy all VMs, undefine them, and delete disks."
	@echo " make test file=<path>         : Run tests for a specific file under the 'tests' dir."
	@echo " make testv file=<path>        : Run specific tests in verbose mode."
	@echo " make test-all                 : Run all unit tests."
	@echo " make test-all-v               : Run all unit tests in verbose mode."
	@echo "=================================================================================="
