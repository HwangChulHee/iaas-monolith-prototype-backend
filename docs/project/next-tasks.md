### 🚀 다음 작업 계획: ID & Access Management (IAM) 서비스 MVP 구현

**목표**: 오픈스택의 Keystone을 모델로 삼아, 프로젝트와 사용자를 생성/조회/수정/삭제하고, 프로젝트 범위의 인증 토큰을 발급하는 독립적인 `IdentityService`를 구현합니다.

#### 1단계: `IdentityService` 메서드 구현

`src/services/identity_service.py` 파일을 생성하고 다음 메서드들을 구현합니다.

-   **Project 관리**:
    -   `create_project(name)`: 새 프로젝트 생성
    -   `list_projects()`: 모든 프로젝트 목록 조회
    -   `get_project(project_id)`: 특정 프로젝트 정보 조회
    -   `delete_project(project_id)`: 프로젝트 삭제 (단, 프로젝트에 속한 VM 등 리소스가 없을 경우에만 가능하도록 안전장치 추가)

-   **User 관리**:
    -   `create_user(username, password)`: 새 사용자 생성 (회원가입)
    -   `list_users()`: 모든 사용자 목록 조회
    -   `get_user(user_id)`: 특정 사용자 정보 조회 (비밀번호 해시는 제외)
    -   `delete_user(user_id)`: 사용자 삭제

-   **멤버십 및 역할(Role) 관리**:
    -   `assign_role(user_id, project_id, role_name)`: 사용자를 프로젝트에 특정 역할로 추가
    -   `revoke_role(user_id, project_id, role_name)`: 프로젝트에서 사용자 역할 제거
    -   `list_project_members(project_id)`: 특정 프로젝트에 속한 모든 사용자 및 역할 목록 조회

-   **인증 (Authentication)**:
    -   `authenticate(username, password, project_name)`: 자격증명 및 프로젝트 멤버십을 검증하고, 성공 시 범위가 지정된(scoped) 임시 토큰을 발급.

#### 2단계: IAM API 엔드포인트 구현

`app.py`를 리팩토링하여 `IdentityService`를 사용하는 API 엔드포인트를 추가/수정합니다.

-   **Projects API (`/v1/projects`)**:
    -   `POST /`: `create_project`
    -   `GET /`: `list_projects`
    -   `GET /{project_id}`: `get_project`
    -   `DELETE /{project_id}`: `delete_project`

-   **Users API (`/v1/users`)**:
    -   `POST /`: `create_user`
    -   `GET /`: `list_users`
    -   `GET /{user_id}`: `get_user`
    -   `DELETE /{user_id}`: `delete_user`

-   **멤버십 API**:
    -   `GET /v1/projects/{project_id}/users`: `list_project_members`
    -   `PUT /v1/projects/{project_id}/users/{user_id}/roles/{role_name}`: `assign_role`
    -   `DELETE /v1/projects/{project_id}/users/{user_id}/roles/{role_name}`: `revoke_role`

-   **Auth API (`/v1/auth/tokens`)**:
    -   `POST /`: `authenticate`

#### 3단계: 단위 테스트 및 문서화

-   `tests/services/test_identity_service.py` 파일을 새로 생성하여, `IdentityService`에 구현된 모든 메서드에 대한 단위 테스트를 작성합니다.
-   API의 사용법을 `test.http` 파일에 예시로 추가합니다.