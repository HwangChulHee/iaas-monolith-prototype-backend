import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.database import models
from src.repositories.interfaces import (
    IProjectRepository, IUserRepository, IRoleRepository, IVMRepository
)
from src.services.exceptions import (
    ProjectCreationError, UserCreationError, ProjectNotEmptyError, 
    ProjectNotFoundError, UserNotFoundError, RoleNotFoundError, 
    AuthenticationError, TokenInvalidError
)

class IdentityService:
    """프로젝트, 사용자, 역할, 인증 등 신원 및 접근 관리 서비스를 제공합니다."""
    _token_cache = {}

    def __init__(self, user_repo: IUserRepository, project_repo: IProjectRepository, role_repo: IRoleRepository, vm_repo: IVMRepository):
        """
        IdentityService를 초기화합니다.

        Args:
            user_repo: 사용자 데이터에 접근하기 위한 리포지토리.
            project_repo: 프로젝트 데이터에 접근하기 위한 리포지토리.
            role_repo: 역할 데이터에 접근하기 위한 리포지토리.
            vm_repo: VM 데이터에 접근하기 위한 리포지토리 (프로젝트 삭제 시 검증용).
        """
        self.user_repo = user_repo
        self.project_repo = project_repo
        self.role_repo = role_repo
        self.vm_repo = vm_repo

    def create_project(self, name: str) -> Dict[str, Any]:
        """
        새로운 프로젝트를 생성합니다.

        Args:
            name: 생성할 프로젝트의 이름.

        Returns:
            생성된 프로젝트의 ID와 이름을 담은 딕셔너리.

        Raises:
            ProjectCreationError: 동일한 이름의 프로젝트가 이미 존재할 때.
        """
        if self.project_repo.find_by_name(name):
            raise ProjectCreationError(f"Project with name '{name}' already exists.")
        new_project = models.Project(name=name)
        created_project = self.project_repo.create(new_project)
        return {"id": created_project.id, "name": created_project.name}

    def list_projects(self) -> List[Dict[str, Any]]:
        """모든 프로젝트의 목록을 조회합니다."""
        projects = self.project_repo.list_all()
        return [{"id": p.id, "name": p.name} for p in projects]

    def get_project(self, project_id: int) -> Dict[str, Any]:
        """
        ID로 특정 프로젝트를 조회합니다.

        Raises:
            ProjectNotFoundError: 해당 ID의 프로젝트를 찾을 수 없을 때.
        """
        project = self.project_repo.find_by_id(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")
        return {"id": project.id, "name": project.name}

    def delete_project(self, project_id: int) -> bool:
        """
        프로젝트를 삭제합니다. 단, VM이 없는 비어있는 프로젝트만 삭제 가능합니다.

        Raises:
            ProjectNotFoundError: 해당 ID의 프로젝트를 찾을 수 없을 때.
            ProjectNotEmptyError: 프로젝트에 VM이 하나 이상 존재하여 삭제할 수 없을 때.
        """
        project = self.project_repo.find_by_id(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")
        
        if self.vm_repo.count_by_project_id(project_id) > 0:
            raise ProjectNotEmptyError(f"Project '{project_id}' is not empty.")
        
        self.project_repo.delete(project)
        return True

    def create_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        새로운 사용자를 생성합니다. 비밀번호는 해시하여 저장합니다.

        Raises:
            UserCreationError: 동일한 이름의 사용자가 이미 존재할 때.
        """
        if self.user_repo.find_by_username(username):
            raise UserCreationError(f"User with username '{username}' already exists.")
        
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        new_user = models.User(username=username, password_hash=password_hash)
        created_user = self.user_repo.create(new_user)
        return {"id": created_user.id, "username": created_user.username}

    def list_users(self) -> List[Dict[str, Any]]:
        """모든 사용자의 목록을 조회합니다. (비밀번호 제외)"""
        users = self.user_repo.list_all()
        return [{"id": u.id, "username": u.username} for u in users]

    def get_user(self, user_id: int) -> Dict[str, Any]:
        """
        ID로 특정 사용자를 조회합니다. (비밀번호 제외)

        Raises:
            UserNotFoundError: 해당 ID의 사용자를 찾을 수 없을 때.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id '{user_id}' not found.")
        return {"id": user.id, "username": user.username}

    def delete_user(self, user_id: int) -> bool:
        """
        사용자를 삭제합니다. 사용자와 연결된 모든 프로젝트 멤버십도 함께 삭제됩니다.

        Raises:
            UserNotFoundError: 해당 ID의 사용자를 찾을 수 없을 때.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User with id '{user_id}' not found.")
        self.user_repo.delete(user)
        return True

    def assign_role(self, user_id: int, project_id: int, role_name: str) -> bool:
        """
        사용자에게 특정 프로젝트의 역할을 부여합니다.

        Raises:
            UserNotFoundError: 해당 ID의 사용자를 찾을 수 없을 때.
            ProjectNotFoundError: 해당 ID의 프로젝트를 찾을 수 없을 때.
            RoleNotFoundError: 해당 이름의 역할을 찾을 수 없을 때.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user: raise UserNotFoundError(f"User with id '{user_id}' not found.")
        
        project = self.project_repo.find_by_id(project_id)
        if not project: raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")

        role = self.role_repo.find_by_name(role_name)
        if not role: raise RoleNotFoundError(f"Role '{role_name}' not found.")

        self.project_repo.assign_role_to_user(user, project, role)
        return True

    def revoke_role(self, user_id: int, project_id: int, role_name: str) -> bool:
        """
        사용자의 특정 프로젝트 역할을 회수합니다.

        Raises:
            UserNotFoundError: 해당 ID의 사용자를 찾을 수 없을 때.
            ProjectNotFoundError: 해당 ID의 프로젝트를 찾을 수 없을 때.
            RoleNotFoundError: 해당 이름의 역할을 찾을 수 없을 때.
        """
        user = self.user_repo.find_by_id(user_id)
        if not user: raise UserNotFoundError(f"User with id '{user_id}' not found.")
        
        project = self.project_repo.find_by_id(project_id)
        if not project: raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")

        role = self.role_repo.find_by_name(role_name)
        if not role: raise RoleNotFoundError(f"Role '{role_name}' not found.")

        self.project_repo.revoke_role_from_user(user, project, role)
        return True

    def list_project_members(self, project_id: int) -> List[Dict[str, Any]]:
        """
        특정 프로젝트에 속한 모든 멤버와 각자의 역할을 조회합니다.

        Raises:
            ProjectNotFoundError: 해당 ID의 프로젝트를 찾을 수 없을 때.
        """
        if not self.project_repo.find_by_id(project_id):
            raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")
        return self.project_repo.list_members(project_id)

    def authenticate(self, username: str, password: str, project_name: str) -> Dict[str, str]:
        """
        자격증명을 검증하고, 성공 시 프로젝트 범위의 인증 토큰을 발급합니다.

        Raises:
            AuthenticationError: 사용자, 프로젝트, 멤버십 검증에 실패했을 때.
        """
        user = self.user_repo.find_by_username(username)
        if not user:
            raise AuthenticationError("Invalid username or password.")

        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        if user.password_hash != password_hash:
            raise AuthenticationError("Invalid username or password.")

        project = self.project_repo.find_by_name(project_name)
        if not project:
            raise AuthenticationError(f"Project '{project_name}' not found.")

        is_member = any(assoc.project_id == project.id for assoc in user.project_associations)
        if not is_member:
            raise AuthenticationError(f"User '{username}' is not a member of project '{project_name}'.")

        token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(hours=1)
        self._token_cache[token] = {
            'user_id': user.id,
            'project_id': project.id,
            'expires_at': expires_at
        }
        return {"token": token, "expires_at": expires_at.isoformat()}

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        인증 토큰의 유효성을 검증하고, 유효하면 토큰 데이터를 반환합니다.

        Raises:
            TokenInvalidError: 토큰을 찾을 수 없거나 만료되었을 때.
        """
        token_data = self._token_cache.get(token)
        if not token_data:
            raise TokenInvalidError("Token not found or invalid.")

        if datetime.now() > token_data['expires_at']:
            del self._token_cache[token]
            raise TokenInvalidError("Token has expired.")
            
        return token_data