### 🚀 다음 작업 계획: 데이터 접근 계층(DAL) 분리 (리포지토리 패턴 적용)

**목표**: 서비스 계층(`services`)이 특정 데이터베이스 기술(현재 `sqlite3`)에 직접 의존하지 않도록 데이터 접근 계층(DAL)을 분리합니다. 이를 통해 향후 다른 DB로의 교체를 용이하게 하고, 단위 테스트를 단순화하며, MSA 전환을 위한 기반을 마련합니다.

#### 1단계: 리포지토리 인터페이스 정의

`src/repositories/interfaces.py` 파일을 생성하고, 각 도메인 객체(Project, User, VM 등)에 대한 추상 베이스 클래스(ABC) 기반의 인터페이스를 정의합니다.

-   `IProjectRepository(ABC)`
-   `IUserRepository(ABC)`
-   `IVMRepository(ABC)`
-   ... (필요에 따라 추가)

각 인터페이스는 `create`, `find_by_id`, `list_all`, `delete` 등 필요한 메서드를 추상 메서드(`@abstractmethod`)로 정의합니다.

#### 2단계: SQLite 리포지토리 구현

`src/repositories/sqlite` 디렉토리를 생성하고, 위에서 정의한 인터페이스의 SQLite 구현체를 작성합니다.

-   `sqlite_project_repository.py` -> `SqliteProjectRepository(IProjectRepository)`
-   `sqlite_user_repository.py` -> `SqliteUserRepository(IUserRepository)`
-   `sqlite_vm_repository.py` -> `SqliteVMRepository(IVMRepository)`

이 클래스들은 실제 SQL 쿼리를 실행하고 `DBConnector`를 사용하는 로직을 포함합니다.

#### 3단계: 서비스 계층 리팩토링 (의존성 주입)

기존 서비스(`IdentityService`, `ComputeService`)를 리팩토링하여 더 이상 직접 DB에 접근하지 않도록 수정합니다.

-   서비스의 생성자(`__init__`)가 리포지토리 객체를 인자로 받도록 변경합니다. (의존성 주입)
    ```python
    # 예시: IdentityService
    def __init__(self, user_repo: IUserRepository, project_repo: IProjectRepository):
        self.user_repo = user_repo
        self.project_repo = project_repo
    ```
-   서비스 내의 모든 DB 관련 코드를 리포지토리 메서드 호출로 변경합니다.
    ```python
    # 변경 전
    # cursor.execute("INSERT INTO users ...")

    # 변경 후
    # new_user = self.user_repo.create(username, password_hash)
    ```

#### 4단계: `app.py` 수정 (의존성 주입 설정)

`app.py`의 핸들러 함수들에서 서비스 객체를 생성할 때, 구현된 리포지토리 객체를 주입해줍니다.

```python
# 변경 전
# identity = IdentityService()

# 변경 후
# user_repo = SqliteUserRepository()
# project_repo = SqliteProjectRepository()
# identity = IdentityService(user_repo, project_repo)
```

이 단계를 통해 전체 애플리케이션이 새로운 아키텍처로 동작하도록 연결합니다.
