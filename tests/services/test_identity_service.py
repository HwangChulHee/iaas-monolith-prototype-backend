# tests/services/test_identity_service.py
import pytest
from unittest.mock import MagicMock, patch, ANY
import hashlib

from src.services.identity_service import IdentityService
from src.services.exceptions import *
from src.repositories.interfaces import IUserRepository, IProjectRepository, IRoleRepository, IVMRepository
from src.database import models

# ===================================================================
#  Fixture 설정
# ===================================================================

@pytest.fixture
def mock_user_repo() -> MagicMock:
    """IUserRepository에 대한 모의 객체를 생성합니다."""
    return MagicMock(spec=IUserRepository)

@pytest.fixture
def mock_project_repo() -> MagicMock:
    """IProjectRepository에 대한 모의 객체를 생성합니다."""
    return MagicMock(spec=IProjectRepository)

@pytest.fixture
def mock_role_repo() -> MagicMock:
    """IRoleRepository에 대한 모의 객체를 생성합니다."""
    return MagicMock(spec=IRoleRepository)

@pytest.fixture
def mock_vm_repo() -> MagicMock:
    """IVMRepository에 대한 모의 객체를 생성합니다."""
    return MagicMock(spec=IVMRepository)

@pytest.fixture
def identity_service(
    mock_user_repo: MagicMock, 
    mock_project_repo: MagicMock, 
    mock_role_repo: MagicMock, 
    mock_vm_repo: MagicMock
) -> IdentityService:
    """테스트에 사용될 IdentityService 인스턴스를 생성하고, 의존성을 주입합니다."""
    return IdentityService(mock_user_repo, mock_project_repo, mock_role_repo, mock_vm_repo)

# ===================================================================
#  프로젝트 관리(Project Management) 테스트
# ===================================================================
class TestProjectManagement:
    def test_create_project_success(self, identity_service: IdentityService, mock_project_repo: MagicMock):
        """프로젝트 생성 성공 시나리오를 테스트합니다."""
        # === Arrange (테스트 준비) ===
        project_name = "new-project"
        # 시나리오: 프로젝트 이름이 중복되지 않음
        mock_project_repo.find_by_name.return_value = None
        # 시나리오: 리포지토리가 생성된 프로젝트 모델을 반환
        mock_project_repo.create.return_value = models.Project(id=5, name=project_name)

        # === Act (실제 테스트 대상 실행) ===
        project = identity_service.create_project(project_name)

        # === Assert (결과 검증) ===
        assert project["id"] == 5
        assert project["name"] == project_name
        # 검증: find_by_name과 create가 올바른 인자와 함께 호출되었는지 확인
        mock_project_repo.find_by_name.assert_called_once_with(project_name)
        mock_project_repo.create.assert_called_once_with(ANY) # models.Project 객체

    def test_create_project_fails_if_name_exists(self, identity_service: IdentityService, mock_project_repo: MagicMock):
        """프로젝트 이름이 중복될 경우 ProjectCreationError가 발생하는지 테스트합니다."""
        # === Arrange ===
        project_name = "existing-project"
        # 시나리오: 동일한 이름의 프로젝트가 이미 존재함을 시뮬레이션
        mock_project_repo.find_by_name.return_value = models.Project(id=1, name=project_name)

        # === Act & Assert ===
        with pytest.raises(ProjectCreationError):
            identity_service.create_project(project_name)
        # 검증: create는 호출되지 않았어야 함
        mock_project_repo.create.assert_not_called()

    def test_delete_project_success(self, identity_service: IdentityService, mock_project_repo: MagicMock, mock_vm_repo: MagicMock):
        """비어있는 프로젝트 삭제 성공을 테스트합니다."""
        # === Arrange ===
        project_id = 2
        mock_project = models.Project(id=project_id, name="empty-project")
        # 시나리오: 삭제할 프로젝트가 존재하고, 해당 프로젝트에 VM이 없음
        mock_project_repo.find_by_id.return_value = mock_project
        mock_vm_repo.count_by_project_id.return_value = 0

        # === Act ===
        result = identity_service.delete_project(project_id)

        # === Assert ===
        assert result is True
        # 검증: 프로젝트를 찾고, VM 개수를 확인하고, 최종적으로 프로젝트를 삭제하는 흐름 확인
        mock_project_repo.find_by_id.assert_called_once_with(project_id)
        mock_vm_repo.count_by_project_id.assert_called_once_with(project_id)
        mock_project_repo.delete.assert_called_once_with(mock_project)

    def test_delete_project_not_empty(self, identity_service: IdentityService, mock_project_repo: MagicMock, mock_vm_repo: MagicMock):
        """VM이 있는 프로젝트 삭제 시 ProjectNotEmptyError 예외를 테스트합니다."""
        # === Arrange ===
        project_id = 1
        # 시나리오: 프로젝트에 VM이 2개 존재함을 시뮬레이션
        mock_project_repo.find_by_id.return_value = models.Project(id=project_id, name="default")
        mock_vm_repo.count_by_project_id.return_value = 2

        # === Act & Assert ===
        with pytest.raises(ProjectNotEmptyError):
            identity_service.delete_project(project_id)
        # 검증: delete는 호출되지 않았어야 함
        mock_project_repo.delete.assert_not_called()

# ===================================================================
#  사용자 관리(User Management) 테스트
# ===================================================================
class TestUserManagement:
    @patch('src.services.identity_service.hashlib.sha256')
    def test_create_user_success(self, mock_sha256: MagicMock, identity_service: IdentityService, mock_user_repo: MagicMock):
        """사용자 생성 성공 시나리오를 테스트합니다."""
        # === Arrange ===
        username, password = "testuser", "password123"
        # 시나리오: 사용자 이름이 중복되지 않음
        mock_user_repo.find_by_username.return_value = None
        # 시나리오: 리포지토리가 생성된 사용자 모델을 반환
        mock_user_repo.create.return_value = models.User(id=10, username=username)

        # === Act ===
        user = identity_service.create_user(username, password)

        # === Assert ===
        assert user["id"] == 10
        assert user["username"] == username
        # 검증: find_by_username과 create가 올바르게 호출되었는지 확인
        mock_user_repo.find_by_username.assert_called_once_with(username)
        mock_user_repo.create.assert_called_once_with(ANY) # models.User 객체

    def test_delete_user_success(self, identity_service: IdentityService, mock_user_repo: MagicMock):
        """사용자 삭제 성공을 테스트합니다."""
        # === Arrange ===
        user_id = 2
        mock_user = models.User(id=user_id, username="testuser")
        # 시나리오: 삭제할 사용자가 존재함
        mock_user_repo.find_by_id.return_value = mock_user

        # === Act ===
        result = identity_service.delete_user(user_id)

        # === Assert ===
        assert result is True
        # 검증: 사용자를 찾고, 최종적으로 삭제하는 흐름 확인
        mock_user_repo.find_by_id.assert_called_once_with(user_id)
        mock_user_repo.delete.assert_called_once_with(mock_user)

# ===================================================================
#  인증 및 권한 부여(Auth & Membership) 테스트
# ===================================================================
class TestAuthAndMembership:
    def test_authenticate_success(self, identity_service: IdentityService, mock_user_repo: MagicMock, mock_project_repo: MagicMock):
        """사용자 인증 성공 시나리오를 테스트합니다."""
        # === Arrange ===
        username, password, project_name = "testuser", "password123", "default"
        hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
        # 시나리오: 사용자, 프로젝트가 존재하고, 사용자가 해당 프로젝트의 멤버임
        mock_user = models.User(id=1, username=username, password_hash=hashed_password)
        mock_project = models.Project(id=1, name=project_name)
        mock_user.project_associations = [models.UserProjectRole(user_id=1, project_id=1, role_id=1)] # 멤버십 시뮬레이션

        mock_user_repo.find_by_username.return_value = mock_user
        mock_project_repo.find_by_name.return_value = mock_project

        # === Act ===
        result = identity_service.authenticate(username, password, project_name)

        # === Assert ===
        assert "token" in result
        assert "expires_at" in result

    def test_authenticate_fails_with_wrong_password(self, identity_service: IdentityService, mock_user_repo: MagicMock):
        """잘못된 비밀번호로 인증 실패 시나리오를 테스트합니다."""
        # === Arrange ===
        username, password = "testuser", "wrong_password"
        # 시나리오: 사용자는 존재하지만, DB의 해시값과 다름
        mock_user_repo.find_by_username.return_value = models.User(id=1, username=username, password_hash="correct_hash")

        # === Act & Assert ===
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            identity_service.authenticate(username, password, "default")