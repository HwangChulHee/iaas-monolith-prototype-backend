# 개발 환경 설정 및 테스트 가이드

이 문서는 프로젝트 개발 환경을 설정하고 API를 테스트하는 방법을 안내합니다.

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
    POST http://192.168.56.10:8000/v1/vms HTTP/1.1
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
    curl http://192.168.56.10:8000/v1/vms
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
