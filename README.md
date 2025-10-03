# 나만의 IaaS 플랫폼 (모놀리식 프로토타입)

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python) ![Status](https://img.shields.io/badge/Status-Phase%201%20MVP-brightgreen?style=for-the-badge) [![Docs](https://img.shields.io/badge/Docs-Read%20Here-blueviolet?style=for-the-badge)](./docs/README.md)

> KVM/QEMU와 libvirt를 기반으로 AWS, OpenStack과 같은 클라우드 IaaS의 핵심 기능을 직접 구현하며 내부 동작 원리를 학습하는 프로젝트입니다.

---

## 🚀 프로젝트 현황

현재 **Phase 1 (MVP 구현 완료)** 단계이며, VM 생성 API를 기반으로 제어 기능을 확장할 예정입니다.

- **주요 달성 내용**:
    - **DB 기반 상태 관리**: VM 메타데이터와 이미지 정보를 SQLite DB로 관리합니다.
    - **CoW (Copy-on-Write) 디스크**: VM 생성 시 원본 이미지 파일의 Lock 충돌을 막기 위해 디스크 복제본을 생성하는 클라우드 표준 방식을 적용했습니다.
    - **VM 생성 API**: RESTful API를 통해 VM을 동적으로 생성할 수 있습니다.

- **남아있는 주요 기술 부채**:
    - **VM 삭제/제어 API 완성**: `destroy`, `shutdown`, `start` 로직 및 DB 상태 업데이트.
    - **모니터링 강화**: DB 상태와 libvirt 실시간 상태를 병합하여 조회하는 로직 구현.
    - **Phase 2 준비**: MSA 전환을 위한 RabbitMQ/Celery 도입 및 비동기 처리 설계.

---

## 📂 디렉토리 구조

- `configs/`: VM 정의 XML 템플릿 (`vm_template.xml`)
- `docs/`: 모든 프로젝트 문서
- `src/`: 모든 파이썬 소스 코드 (`services/`, `database/`, `utils/`)
- `scripts/`: Vagrant 프로비저닝 등 스크립트 파일
- `Makefile`: 실행 명령어 단축 및 환경 관리 스크립트

---

## 💻 기술 스택

- **언어**: Python 3
- **백엔드**: 순수 WSGI (`wsgiref.simple_server` 기반)
- **가상화**: KVM/QEMU 및 `libvirt-python`
- **개발 환경**: Vagrant와 VirtualBox (중첩 가상화)
- **DB**: SQLite3 (메타데이터 저장용)

---

## ⚙️ 개발자 가이드

프로젝트 설정, API 테스트, 아키텍처, 기여 방법 등 상세한 개발자 문서는 `docs/` 디렉토리를 참고하세요.

- **[💻 개발 환경 설정](./docs/developer/setup.md)**
- **[🏛️ 아키텍처 개요](./docs/developer/architecture.md)**
- **[🤝 기여 방법](./docs/developer/contributing.md)**