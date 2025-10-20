# ==============================================================================
# IaaS Project Makefile
# 
# 사용법:
#   make <target>
#
#   예: make serve, make test-all
#   인자 없이 `make`만 실행하면 도움말이 표시됩니다.
# ==============================================================================

# ------------------------------------------------------------------------------
# 설정
# ------------------------------------------------------------------------------

# .PHONY: 파일 이름과 혼동되지 않도록 가상 타겟을 명시합니다.
.PHONY: help serve install db-init db-clean lint format clean vm-cleanup clean-all test test-all testv test-all-v

# .DEFAULT_GOAL: `make` 명령어만 입력했을 때 실행할 기본 타겟을 설정합니다.
.DEFAULT_GOAL := help

# 변수 설정
PYTHON_CMD = python3
LINT_DIRS = src tests

# ------------------------------------------------------------------------------
# 명령어 목록 (아래 형식에 맞춰 추가/수정하면 `make help`에 자동 반영됩니다)
# target-name: ## 설명
# ------------------------------------------------------------------------------

help: ## ✨ 이 도움말 메시지를 표시합니다.
	@awk 'BEGIN {FS = ":.*?## "; printf "\n\033[1mUsage:\033[0m\n  make \033[36m<target>\033[0m\n\n\033[1mTargets:\033[0m\n"} /^[a-zA-Z_-]+:.*?## / { printf "  \033[36m%%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- Application ---
serve: ## 🚀 애플리케이션 서버를 시작합니다.
	@echo "🚀 Starting IaaS Monolith Prototype on port 8000..."
	$(PYTHON_CMD) src/app.py

# --- Dependencies ---
install: ## 📦 requirements.txt를 기반으로 Python 의존성을 설치합니다.
	@echo "📦 Installing dependencies from requirements.txt..."
	pip install -r requirements.txt

# --- Database ---
db-init: ## 💾 데이터베이스 스키마와 기본 데이터를 생성/초기화합니다.
	@echo "💾 Initializing database and inserting base data..."
	PYTHONPATH=src $(PYTHON_CMD) -m database.db_init

db-clean: ## 🧹 'vms' 테이블의 모든 레코드를 삭제합니다.
	@echo "🧹 Cleaning up VM records in DB..."
	$(PYTHON_CMD) -c "import sqlite3; DB_FILE = 'iaas_metadata.db'; conn = sqlite3.connect(DB_FILE); conn.cursor().execute('DELETE FROM vms'); conn.commit(); conn.close(); print('DB: vms table cleaned.');"

# --- Code Quality ---
lint: ## 🔎 Ruff를 사용하여 코드 스타일 및 에러를 검사합니다.
	@echo "🔎 Checking code for style and errors..."
	ruff check $(LINT_DIRS)

format: ## 🎨 Ruff를 사용하여 코드를 자동으로 포맷팅합니다.
	@echo "🎨 Formatting code..."
	ruff format $(LINT_DIRS)

# --- Testing ---
test-all: ## 🧪 모든 단위 테스트를 실행합니다.
	@echo "🧪 Running all unit tests..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest

test-all-v: ## 🧪 모든 단위 테스트를 상세 모드(verbose)로 실행합니다.
	@echo "🧪 Running all unit tests in verbose mode..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest -v

file ?= 
test: ## 🎯 특정 테스트 파일을 지정하여 실행합니다. (예: make test file=services/test_compute_service.py)
	@if [ -z "$(file)" ]; then \
		echo "❌ Error: Please specify a test file."; \
		echo "   Usage: make test file=<path_under_tests_dir>"; \
		exit 1; \
	fi
	@echo "🧪 Running unit test for: tests/$(file)..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest tests/$(file)

testv: ## 🎯 특정 테스트 파일을 상세 모드(verbose)로 실행합니다.
	@if [ -z "$(file)" ]; then \
		echo "❌ Error: Please specify a test file."; \
		echo "   Usage: make testv file=<path_under_tests_dir>"; \
		exit 1; \
	fi
	@echo "🧪 Running unit test in verbose mode for: tests/$(file)..."
	PYTHONPATH=src $(PYTHON_CMD) -m pytest -v tests/$(file)

# --- Cleanup ---
clean: ## 🗑️ Python 캐시 파일 (__pycache__, .pytest_cache)을 삭제합니다.
	@echo "🗑️ Removing Python cache files..."
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	rm -rf .pytest_cache

vm-cleanup: ## 🔥 [주의] 모든 libvirt VM과 관련 디스크 이미지를 삭제합니다.
	@echo "🔥 Destroying all running VMs and undefining all definitions..."
	-virsh list --all --name | xargs -r -I {} virsh destroy {}
	-virsh list --all --name | xargs -r -I {} virsh undefine {}
	@echo "🗑️ Attempting to delete VM disk replicas..."
	-sudo find /var/lib/libvirt/images/ -maxdepth 1 -type f -name '*-vm-*.qcow2' -exec rm -f {} \;
	@echo "Cleanup complete."

clean-all: vm-cleanup db-clean clean ## ☢️ [매우 위험] 모든 정리 작업을 실행합니다. (VM, DB, 캐시)
	@echo "☢️ Full cleanup complete."