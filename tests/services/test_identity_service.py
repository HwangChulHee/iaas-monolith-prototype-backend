# tests/services/test_identity_service.py
import pytest
import sqlite3
from unittest.mock import patch, MagicMock

from services.identity_service import IdentityService, ProjectCreationError, UserCreationError, ProjectNotFoundError, ProjectNotEmptyError, UserNotFoundError, RoleNotFoundError

@pytest.fixture
def mock_db_connector():
    """DBConnector를 모킹하여 실제 DB 접근을 방지합니다."""
    with patch('services.identity_service.DBConnector') as mock_db_class:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

@pytest.fixture
def identity_service():
    """테스트를 위한 IdentityService 인스턴스를 생성합니다."""
    return IdentityService()

class TestProjectManagement:
    def test_create_project_success(self, identity_service, mock_db_connector):
        """프로젝트 생성 성공 시나리오를 테스트합니다."""
        # Arrange
        project_name = "new-project"
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.lastrowid = 5 # 새 프로젝트 ID 시뮬레이션

        # Act
        project = identity_service.create_project(project_name)

        # Assert
        assert project["id"] == 5
        assert project["name"] == project_name
        mock_cursor.execute.assert_called_once_with("INSERT INTO projects (name) VALUES (?)", (project_name,))
        mock_db_connector.commit.assert_called_once()

    def test_create_project_fails_if_name_exists(self, identity_service, mock_db_connector):
        """프로젝트 이름이 중복될 경우 ProjectCreationError가 발생하는지 테스트합니다."""
        # Arrange
        project_name = "existing-project"
        mock_cursor = mock_db_connector.cursor()
        # sqlite3.IntegrityError 시뮬레이션
        mock_cursor.execute.side_effect = sqlite3.IntegrityError

        # Act & Assert
        with pytest.raises(ProjectCreationError) as excinfo:
            identity_service.create_project(project_name)
        
        assert "already exists" in str(excinfo.value)

    def test_list_projects_empty(self, identity_service, mock_db_connector):
        """프로젝트가 없을 때 빈 리스트를 반환하는지 테스트합니다."""
        # Arrange
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = []

        # Act
        projects = identity_service.list_projects()

        # Assert
        assert projects == []
        mock_cursor.execute.assert_called_once_with("SELECT id, name FROM projects ORDER BY name ASC")

    def test_list_projects_with_data(self, identity_service, mock_db_connector):
        """프로젝트가 있을 때 목록을 정확히 반환하는지 테스트합니다."""
        # Arrange
        mock_cursor = mock_db_connector.cursor()
        db_projects = [
            {'id': 1, 'name': 'default'},
            {'id': 2, 'name': 'test-project'}
        ]
        mock_cursor.fetchall.return_value = db_projects

        # Act
        projects = identity_service.list_projects()

        # Assert
        assert len(projects) == 2
        assert projects[0]["name"] == "default"
        assert projects[1]["name"] == "test-project"

    def test_get_project_success(self, identity_service, mock_db_connector):
        """특정 프로젝트 조회 성공을 테스트합니다."""
        # Arrange
        project_id = 1
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'id': project_id, 'name': 'default'}

        # Act
        project = identity_service.get_project(project_id)

        # Assert
        assert project['id'] == project_id
        mock_cursor.execute.assert_called_once_with("SELECT id, name FROM projects WHERE id = ?", (project_id,))

    def test_get_project_not_found(self, identity_service, mock_db_connector):
        """존재하지 않는 프로젝트 조회 시 ProjectNotFoundError 예외를 테스트합니다."""
        # Arrange
        project_id = 999
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = None

        # Act & Assert
        with pytest.raises(ProjectNotFoundError):
            identity_service.get_project(project_id)

    def test_delete_project_success(self, identity_service, mock_db_connector):
        """빈 프로젝트 삭제 성공을 테스트합니다."""
        # Arrange
        project_id = 2
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'vm_count': 0}
        mock_cursor.rowcount = 1

        # Act
        result = identity_service.delete_project(project_id)

        # Assert
        assert result is True
        mock_cursor.execute.assert_any_call("SELECT COUNT(*) as vm_count FROM vms WHERE project_id = ?", (project_id,))
        mock_cursor.execute.assert_any_call("DELETE FROM projects WHERE id = ?", (project_id,))

    def test_delete_project_not_empty(self, identity_service, mock_db_connector):
        """VM이 있는 프로젝트 삭제 시 ProjectNotEmptyError 예외를 테스트합니다."""
        # Arrange
        project_id = 1
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'vm_count': 2}

        # Act & Assert
        with pytest.raises(ProjectNotEmptyError):
            identity_service.delete_project(project_id)

    def test_delete_project_not_found(self, identity_service, mock_db_connector):
        """존재하지 않는 프로젝트 삭제 시 ProjectNotFoundError 예외를 테스트합니다."""
        # Arrange
        project_id = 999
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'vm_count': 0}
        mock_cursor.rowcount = 0

        # Act & Assert
        with pytest.raises(ProjectNotFoundError):
            identity_service.delete_project(project_id)

class TestUserManagement:
    @patch('services.identity_service.hashlib.sha256')
    def test_create_user_success(self, mock_sha256, identity_service, mock_db_connector):
        """사용자 생성 성공 시나리오를 테스트합니다."""
        # Arrange
        username = "testuser"
        password = "password123"
        hashed_password = "hashed_password_string"
        
        mock_hash_obj = MagicMock()
        mock_hash_obj.hexdigest.return_value = hashed_password
        mock_sha256.return_value = mock_hash_obj
        
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.lastrowid = 10

        # Act
        user = identity_service.create_user(username, password)

        # Assert
        assert user["id"] == 10
        assert user["username"] == username
        mock_cursor.execute.assert_called_once_with(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", 
            (username, hashed_password)
        )
        mock_db_connector.commit.assert_called_once()

    def test_create_user_fails_if_name_exists(self, identity_service, mock_db_connector):
        """사용자 이름이 중복될 경우 UserCreationError가 발생하는지 테스트합니다."""
        # Arrange
        username = "existing-user"
        password = "password123"
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.execute.side_effect = sqlite3.IntegrityError

        # Act & Assert
        with pytest.raises(UserCreationError) as excinfo:
            identity_service.create_user(username, password)
        
        assert "already exists" in str(excinfo.value)

    def test_list_users_empty(self, identity_service, mock_db_connector):
        """사용자가 없을 때 빈 리스트를 반환하는지 테스트합니다."""
        # Arrange
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = []

        # Act
        users = identity_service.list_users()

        # Assert
        assert users == []
        mock_cursor.execute.assert_called_once_with("SELECT id, username FROM users ORDER BY username ASC")

    def test_list_users_with_data(self, identity_service, mock_db_connector):
        """사용자가 있을 때 목록을 정확히 반환하는지 테스트합니다."""
        # Arrange
        mock_cursor = mock_db_connector.cursor()
        db_users = [
            {'id': 1, 'username': 'admin'},
            {'id': 2, 'username': 'testuser'}
        ]
        mock_cursor.fetchall.return_value = db_users

        # Act
        users = identity_service.list_users()

        # Assert
        assert len(users) == 2
        assert users[0]["username"] == "admin"
        assert users[1]["username"] == "testuser"

    def test_get_user_success(self, identity_service, mock_db_connector):
        """특정 사용자 조회 성공을 테스트합니다."""
        # Arrange
        user_id = 1
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'id': user_id, 'username': 'admin'}

        # Act
        user = identity_service.get_user(user_id)

        # Assert
        assert user['id'] == user_id
        mock_cursor.execute.assert_called_once_with("SELECT id, username FROM users WHERE id = ?", (user_id,))

    def test_get_user_not_found(self, identity_service, mock_db_connector):
        """존재하지 않는 사용자 조회 시 UserNotFoundError 예외를 테스트합니다."""
        # Arrange
        user_id = 999
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = None

        # Act & Assert
        with pytest.raises(UserNotFoundError):
            identity_service.get_user(user_id)

    def test_delete_user_success(self, identity_service, mock_db_connector):
        """사용자 삭제 성공을 테스트합니다."""
        # Arrange
        user_id = 2
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.rowcount = 1

        # Act
        result = identity_service.delete_user(user_id)

        # Assert
        assert result is True
        mock_cursor.execute.assert_any_call("DELETE FROM user_project_roles WHERE user_id = ?", (user_id,))
        mock_cursor.execute.assert_any_call("DELETE FROM users WHERE id = ?", (user_id,))

    def test_delete_user_not_found(self, identity_service, mock_db_connector):
        """존재하지 않는 사용자 삭제 시 UserNotFoundError 예외를 테스트합니다."""
        # Arrange
        user_id = 999
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.rowcount = 0

        # Act & Assert
        with pytest.raises(UserNotFoundError):
            identity_service.delete_user(user_id)

class TestMembershipManagement:
    def test_assign_role_success(self, identity_service, mock_db_connector):
        """사용자에게 역할을 할당하는 기능 테스트."""
        # Arrange
        user_id, project_id, role_name = 1, 1, "admin"
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'id': 1}

        # Act
        result = identity_service.assign_role(user_id, project_id, role_name)

        # Assert
        assert result is True
        mock_cursor.execute.assert_any_call("SELECT id FROM roles WHERE name = ?", (role_name,))
        mock_cursor.execute.assert_any_call("INSERT OR IGNORE INTO user_project_roles (user_id, project_id, role_id) VALUES (?, ?, ?)", (user_id, project_id, 1))

    def test_assign_role_not_found(self, identity_service, mock_db_connector):
        """존재하지 않는 역할 할당 시 RoleNotFoundError 예외 테스트."""
        # Arrange
        user_id, project_id, role_name = 1, 1, "non-existent-role"
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = None

        # Act & Assert
        with pytest.raises(RoleNotFoundError):
            identity_service.assign_role(user_id, project_id, role_name)

    def test_revoke_role_success(self, identity_service, mock_db_connector):
        """사용자의 역할을 회수하는 기능 테스트."""
        # Arrange
        user_id, project_id, role_name = 1, 1, "admin"
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchone.return_value = {'id': 1}

        # Act
        result = identity_service.revoke_role(user_id, project_id, role_name)

        # Assert
        assert result is True
        mock_cursor.execute.assert_any_call("SELECT id FROM roles WHERE name = ?", (role_name,))
        mock_cursor.execute.assert_any_call("DELETE FROM user_project_roles WHERE user_id = ? AND project_id = ? AND role_id = ?", (user_id, project_id, 1))

    def test_list_project_members(self, identity_service, mock_db_connector):
        """프로젝트 멤버 목록 조회를 테스트합니다."""
        # Arrange
        project_id = 1
        mock_cursor = mock_db_connector.cursor()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'username': 'admin', 'role': 'admin'},
            {'id': 2, 'username': 'testuser', 'role': 'member'}
        ]

        # Act
        members = identity_service.list_project_members(project_id)

        # Assert
        assert len(members) == 2
        assert members[1]['username'] == 'testuser'
        assert members[1]['role'] == 'member'
