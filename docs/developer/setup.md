# 개발자 빠른 시작 가이드

이 문서는 프로젝트 개발 환경을 설정하고, 코드를 수정하며, 테스트하는 전체 워크플로우를 안내합니다.

## 1. 초기 환경 설정 (최초 1회)

프로젝트에 처음 참여했을 때 단 한 번만 수행하면 되는 과정입니다.

1.  **Dev-VM 시작**: `vagrant up` 명령어로 개발용 가상 머신(Dev-VM)을 시작합니다.

2.  **VM 베이스 이미지 준비** (필요 시):
    -   `images/` 디렉토리에 사용할 클라우드 이미지를 다운로드합니다.
    -   이미지를 libvirt의 기본 경로로 이동시키고, 비밀번호를 설정합니다. (상세 과정은 생략)

3.  **의존성 설치**: 프로젝트에 필요한 모든 Python 패키지를 설치합니다.
    ```bash
    make install
    ```

4.  **데이터베이스 초기화**: DB 파일을 생성하고, 테이블 스키마와 기본 데이터를 삽입합니다.
    ```bash
    make db-init
    ```

## 2. 일상적인 개발 워크플로우

코드를 수정하고 기능을 개발할 때 반복적으로 사용하는 명령어들입니다.

-   **애플리케이션 서버 실행**:
    ```bash
    make serve
    ```

-   **전체 단위 테스트 실행**:
    ```bash
    make test-all
    ```

-   **특정 파일만 테스트 실행**:
    ```bash
    make test file=services/test_compute_service.py
    ```

## 3. 코드 품질 관리

코드의 일관성과 품질을 유지하기 위한 명령어들입니다. Git에 커밋하기 전에 항상 실행하는 것을 권장합니다.

-   **코드 스타일 및 에러 검사 (`lint`)**:
    ```bash
    make lint
    ```

-   **코드 자동 포맷팅 (`format`)**:
    ```bash
    make format
    ```

## 4. API 검증

`make serve`로 서버를 실행한 후, `test.http` 파일이나 Postman 같은 REST Client를 사용하여 API가 의도대로 동작하는지 직접 확인할 수 있습니다.

```http
### VM 생성 요청 예시
POST http://192.168.56.10:8000/v1/vms HTTP/1.1
Content-Type: application/json
X-Auth-Token: {{auth_token}} # 인증 토큰 필요

{
    "name": "my-first-vm",
    "cpu": 1,
    "ram": 1024,
    "image_name": "Ubuntu-Base-22.04"
}
```

## 5. 환경 정리

개발 환경을 깨끗하게 정리하고 싶을 때 사용하는 명령어들입니다.

-   **Python 캐시 삭제**: `__pycache__` 등 파이썬 실행 시 생성되는 캐시 파일들을 삭제합니다.
    ```bash
    make clean
    ```

-   **VM 레코드 삭제**: DB의 `vms` 테이블 내용만 모두 삭제합니다.
    ```bash
    make db-clean
    ```

-   **[주의] VM 완전 삭제**: libvirt에 정의된 모든 VM과 관련 디스크 이미지까지 전부 삭제합니다. 시스템이 꼬였을 때 사용하세요.
    ```bash
    make vm-cleanup
    ```

-   **[매우 위험] 전체 초기화**: 위의 모든 정리 작업(`clean`, `db-clean`, `vm-cleanup`)을 한 번에 실행합니다. 개발 환경을 완전히 초기 상태로 되돌리고 싶을 때만 사용하세요.
    ```bash
    make clean-all
    ```