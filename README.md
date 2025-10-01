# AI 특화 IaaS 플랫폼 (모놀리식 프로토타입)

## 🎯 프로젝트 현황 (Phase 1 MVP)

현재 **Phase 1 (MVP 구현 완료)** 단계입니다. DB 연동, 동적 XML 생성, 이미지 복제를 통한 VM 생성 API (`POST /v1/vms`)를 안정적으로 구축했습니다.

### 핵심 달성
- **DB 기반 상태 관리**: VM 메타데이터와 이미지 정보를 SQLite DB로 관리합니다.
- **CoW (Copy-on-Write) 디스크**: VM 생성 시 원본 이미지 파일의 Lock 충돌을 막기 위해 디스크 복제본을 생성하는 클라우드 표준 방식을 적용했습니다.
- **VM 생성 API**: RESTful API를 통해 VM을 동적으로 생성할 수 있습니다.

---

## 📂 디렉토리 구조
aas_project/

├── configs/          # VM 정의 XML 템플릿 (vm_template.xml)

├── images/           # VM 생성에 사용되는 OS 이미지 파일 (Git 제외)

├── src/              # 모든 파이썬 소스 코드 (services/, database/, utils/)

├── scripts/          # Vagrant 프로비저닝 등 스크립트 파일

├── Makefile          # 실행 명령어 단축 및 환경 관리 스크립트

└── README.md

- **configs/**: VM 스펙을 위한 동적 XML 템플릿 (`vm_template.xml`)이 저장됩니다.
- **src/**: 백엔드 WSGI 애플리케이션 및 `ComputeService`, `ImageService` 로직이 포함됩니다.
- **.gitignore**: `iaas_metadata.db` 파일이 Git 관리 대상에서 제외됩니다.

---

## 💻 기술 스택

- **언어**: Python 3
- **백엔드**: 순수 WSGI (`wsgiref.simple_server` 기반)
- **가상화**: KVM/QEMU 및 `libvirt-python`
- **개발 환경**: Vagrant와 VirtualBox (중첩 가상화)
- **DB**: SQLite3 (메타데이터 저장용)

---

## ⚙️ 시작하기 및 API 테스트 가이드 (Makefile 사용)

### 1단계: 개발 환경 및 이미지 준비

1.  **Dev-VM 시작**: `vagrant up` 명령어로 Dev-VM을 시작합니다.
2.  **VM 이미지 준비**: `images/` 디렉토리에 클라우드 이미지를 다운로드하고 libvirt의 기본 경로로 이동합니다. (`/var/lib/libvirt/images/ubuntu-test.qcow2` 이름 권장)
3.  **VM 이미지에 비밀번호 주입**: `virsh console` 로그인을 위해 root 계정에 비밀번호를 설정합니다.
    ```bash
    sudo virt-customize -a /var/lib/libvirt/images/ubuntu-test.qcow2 --root-password password:ubuntu
    ```
4.  **DB 초기화**: 프로젝트 루트 디렉토리에서 DB 파일 생성 및 기본 이미지 정보를 삽입합니다.
    ```bash
    # vms 테이블 및 images 테이블 생성, 'Ubuntu-Base-22.04' 이미지 삽입
    make db-init
    ```

### 2단계: WSGI 서버 실행 및 API 검증

1.  **서버 실행**: `make serve` 명령어로 API 서버를 띄웁니다.
    ```bash
    # Dev-VM 내부에서 서버 실행
    make serve 
    ```
2.  **VM 생성 (POST API 테스트)**: 호스트 PC (Windows)에서 REST Client (Postman 등)를 사용하여 VM 생성 요청을 보냅니다. (Dev-VM IP는 `192.168.56.10` 기준)
    ```http
    POST [http://192.168.56.10:8000/v1/vms](http://192.168.56.10:8000/v1/vms) HTTP/1.1
    Content-Type: application/json

    {
        "name": "vm-chulhee-01",
        "cpu": 2,
        "ram": 2048,
        "image_name": "Ubuntu-Base-22.04"
    }
    ```
3.  **VM 목록 확인**: `GET /v1/vms` 호출 또는 `virsh list`로 확인합니다.
    ```bash
    # Dev-VM 내부에서 확인
    virsh list --all
    
    # 호스트 PC에서 API 호출
    curl [http://192.168.56.10:8000/v1/vms](http://192.168.56.10:8000/v1/vms)
    ```

### 3단계: 환경 정리 (Cleanup)

1.  **VM 기록 초기화**: 테스트용 VM 기록만 DB에서 삭제합니다.
    ```bash
    make db-clean
    ```
2.  **VM 완전 제거**: 실행 중인 모든 VM을 강제 종료하고, libvirt 정의를 제거하며, 생성된 디스크 복제본 파일까지 모두 삭제합니다. (VM 생성 실패로 시스템이 꼬였을 때 사용)
    ```bash
    make vm-cleanup
    ```

---

## 🚧 프로젝트 현황 및 기술 부채

- **현재 단계**: Phase 1 (MVP 구현 완료). 이제 VM 생성 API를 기반으로 제어 기능을 확장할 예정입니다.
- **해결된 기술 난제**:
    - `libvirt-python` 권한 문제 (Root 없이 실행 가능)
    - XML 문법/호환성 문제 해결
    - DB를 통한 VM 메타데이터 및 이미지 경로 동적 관리
    - QEMU 디스크 Lock 충돌 해결 및 CoW 복제 로직 적용
- **남아있는 주요 기술 부채**:
    - **VM 삭제/제어 API 완성**: `destroy`, `shutdown`, `start` 로직 및 DB 상태 업데이트.
    - **모니터링 강화**: DB 상태와 libvirt 실시간 상태를 병합하여 조회하는 로직 구현.
    - **WSGI 심화**: WSGI 환경에서 파일 시스템 경로, 요청 본문 처리의 안정성 강화.
    - **Phase 2 준비**: MSA 전환을 위한 RabbitMQ/Celery 도입 및 비동기 처리 설계.

---

## ✍️ Git 커밋 규칙

프로젝트의 커밋 메시지는 `타입: 설명` 형식으로 작성합니다.

-   `feat`: 새로운 기능 구현. (e.g., `feat: implement vm creation api endpoint with db`)
-   `fix`: 버그 수정. (e.g., `fix: resolve qemu-img backing format error`)
-   `docs`: 문서 수정. (e.g., `docs: update readme with current status and make commands`)
-   `chore`: 코드나 의존성 업데이트 등 사소한 변경. (e.g., `chore: add python uuid dependency`)