### 🚀 다음 작업 계획: 오픈스택 모델 기반 인증/인가/테넌시 구현

#### Phase 1: 테넌시(Tenancy) 기반 구축 (현재 진행)

**목표**: 모든 리소스가 특정 `Project`에 소속되도록 하여, 리소스 격리의 기반을 다집니다.

1.  **DB 스키마 확장**:
    -   `projects` 테이블 (`id`, `name`) 생성.
    -   `users` 테이블 (`id`, `username`, `password_hash`) 생성.
    -   `roles` 테이블 (`id`, `name` - 예: 'admin', 'member') 생성.
    -   사용자-프로젝트-역할을 연결하는 매핑 테이블 `user_project_roles` (`user_id`, `project_id`, `role_id`) 생성.
    -   `vms` 테이블에 `project_id` 외래 키(Foreign Key) 추가.
    -   `db_init.py` 스크립트가 위 테이블들을 생성하고, 기본 관리자(admin)와 프로젝트를 시드(seed)하도록 수정.

2.  **서비스 계층에 테넌시 적용**:
    -   `ComputeService`의 모든 메서드가 `project_id`를 인자로 받도록 수정.
    -   모든 SQL 쿼리에 `WHERE project_id = ?` 조건을 추가하여, 해당 프로젝트의 리소스만 제어하도록 로직 변경.

3.  **API 계층 임시 수정**:
    -   실제 인증 구현 전까지, API 요청 헤더(`X-Project-ID`)로 `project_id`를 전달받아 서비스 계층에 넘겨주는 방식으로 임시 구현.

#### Phase 2: 인증(Authentication) 서비스 구현 (Keystone-Lite)

**목표**: 사용자가 ID/PW로 로그인하여, 자신의 신원과 프로젝트 범위가 담긴 임시 토큰을 발급받는 프로세스를 구현합니다.

1.  **토큰 발급 API 구현**:
    -   `POST /v1/auth/tokens` 엔드포인트 생성.
    -   요청 본문으로 `username`, `password`, `project_name`을 받아 유효성을 검증.
    -   인증 성공 시, 해당 사용자와 프로젝트 정보가 담긴 임시 토큰(Access Token)을 생성하여 반환.

2.  **토큰 기반 API 요청 처리**:
    -   기존 `X-Project-ID` 헤더 대신, `X-Auth-Token` 헤더로 토큰을 받도록 API 서버(`app.py`) 수정.
    -   API 요청 수신 시, 토큰의 유효성을 검증하고 토큰에 명시된 `project_id`를 추출하여 서비스 계층에 전달하는 미들웨어(Middleware) 로직 구현.

#### Phase 3: 인가(Authorization) 로직 구현

**목표**: 토큰에 담긴 역할(Role)을 기반으로, 사용자가 특정 작업을 수행할 권한이 있는지 확인하는 로직을 구현합니다.

1.  **역할 기반 접근 제어(RBAC) 적용**:
    -   `ComputeService`의 주요 메서드(예: `destroy_vm`)가 특정 역할(예: 'admin')을 요구하도록 로직 추가.
    -   API 미들웨어에서 토큰 검증 시, 사용자의 역할 정보까지 함께 추출하여 서비스 계층에 전달.
    -   요구되는 역할이 없을 경우, '403 Forbidden' 에러를 반환.