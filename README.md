# AI 특화 IaaS 플랫폼 (모놀리식 프로토타입)

## 📝 프로젝트 개요

클라우드 시스템의 근본 아키텍처와 동작 원리에 대한 깊은 이해를 목표로, IaaS의 핵심 기능(VM, 네트워크, 스토리지, GPU)을 직접 구현합니다.

---

## 📂 디렉토리 구조

iaas_project/
├── configs/          # VM 정의 XML 파일 등 설정 파일
├── images/           # VM 생성에 사용되는 OS 이미지 파일 (git에 포함되지 않음)
├── src/              # 모든 파이썬 소스 코드가 위치
├── scripts/          # Vagrant 프로비저닝 등 스크립트 파일
└── README.md

-   `configs/`: VM의 CPU, 메모리, 디스크 등의 사양을 정의하는 XML 파일이 저장됩니다.
-   `images/`: KVM 가상머신을 위한 `qcow2` 형식의 OS 이미지를 보관합니다. **(`.gitignore` 파일에 추가되어 Git으로 관리되지 않습니다.)**
-   `src/`: 프로젝트의 모든 코드가 위치합니다. 향후 MSA(Microservices Architecture) 전환 시 기능별 디렉토리로 확장될 예정입니다.
-   `scripts/`: 개발 환경 설정 및 자동화에 필요한 스크립트가 포함됩니다.

---

## 💻 기술 스택

-   **언어**: Python 3
-   **백엔드**: 순수 WSGI
-   **가상화**: KVM/QEMU 및 `libvirt-python`
-   **개발 환경**: Vagrant와 VirtualBox (중첩 가상화)

---

## ⚙️ 시작하기 (VM 생성 가이드)

#### 1단계: 개발 환경 설정 및 파일 준비

1.  **개발 환경 구축**: Vagrant를 설치하고 `vagrant up` 명령어로 개발용 VM을 시작합니다.
2.  **VS Code 접속**: VS Code의 Remote - SSH 기능을 이용해 `iaas-dev-node`에 접속합니다.
3.  **VM 이미지 준비**: `images/` 디렉토리에 우분투 클라우드 이미지를 다운로드한 후, `libvirt`의 기본 경로로 파일을 옮깁니다.

    ```bash
    sudo mv images/jammy-server-cloudimg-amd64.img /var/lib/libvirt/images/ubuntu-test.qcow2
    ```

4.  **필요 도구 설치**: `virt-customize`를 사용하기 위해 `libguestfs-tools` 패키지를 설치합니다.

    ```bash
    sudo apt-get update && sudo apt-get install -y libguestfs-tools
    ```

5.  **VM 이미지에 비밀번호 주입**: `virsh console` 로그인을 위해 `root` 계정에 비밀번호를 설정합니다.

    ```bash
    sudo virt-customize -a /var/lib/libvirt/images/ubuntu-test.qcow2 --root-password password:ubuntu
    ```

6.  **VM 설정 파일 작성**: `configs/` 디렉토리에 `ubuntu-simple.xml` 파일을 생성하고, 콘솔 접속을 위한 `<console>` 태그를 포함합니다.
7.  **VM 생성 스크립트 작성**: `src/` 디렉토리에 `create_vm.py` 파일을 생성하고, `ubuntu-simple.xml`을 읽어오도록 코드를 작성합니다.

#### 2단계: VM 생성 및 검증

1.  **기존 VM 삭제 (선택)**: `Domain already exists` 에러가 발생하면 기존 VM을 삭제합니다.

    ```bash
    sudo virsh destroy ubuntu-simple
    sudo virsh undefine ubuntu-simple
    ```

2.  **VM 생성**: `src/` 디렉토리에서 스크립트를 실행합니다.

    ```bash
    sudo python3 create_vm.py
    ```

3.  **VM 목록 확인**: `virsh` 명령어로 VM이 정상적으로 `running` 상태인지 확인합니다.

    ```bash
    sudo virsh list --all
    ```

4.  **VM 콘솔 접속 및 로그인**: VM에 접속하여 정상 부팅을 확인합니다.

    ```bash
    sudo virsh console ubuntu-simple
    ```

    (로그인 정보: `root` / `ubuntu`)

#### 3단계: VM 삭제 (클린업)

1.  **VM 강제 종료**: 실행 중인 VM을 종료합니다.

    ```bash
    sudo virsh destroy ubuntu-simple
    ```

2.  **VM 영구 삭제**: `libvirt` 데이터베이스에서 VM 정보를 제거합니다.

    ```bash
    sudo virsh undefine ubuntu-simple
    ```

---

## 🚧 프로젝트 현황 및 기술 부채

-   **현재 단계**: **Phase 0 (기술 검증)** - VM 생명주기 관리 프로토타입 구현 완료.
-   **기술 부채**:
    -   소켓과 파일 디스크립터의 근본적인 개념
    -   WSGI와 ASGI의 완벽한 활용 및 프로젝트 적용
    -   I/O 멀티플렉싱의 상세한 동작 원리
    -   VM 네트워크 및 SSH 서비스 자동 설정 (cloud-init 관련)

---

## ✍️ Git 커밋 규칙
프로젝트의 커밋 메시지는 타입: 설명 형식으로 작성합니다.

- feat: 새로운 기능 구현. (e.g., feat: add vm creation api endpoint)

- fix: 버그 수정. (e.g., fix: resolve libvirt undefine error)

- docs: 문서 수정. (e.g., docs: update readme with commit rules)

- chore: 코드나 의존성 업데이트 등 사소한 변경. (e.g., chore: update apt packages)