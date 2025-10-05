# src/services/identity_service.py
import sqlite3
import hashlib
import uuid
from datetime import datetime, timedelta

from database.db_connector import DBConnector

class ProjectCreationError(Exception):
    pass

class UserCreationError(Exception):
    pass

class ProjectNotEmptyError(Exception):
    pass

class ProjectNotFoundError(Exception):
    pass

class UserNotFoundError(Exception):
    pass

class RoleNotFoundError(Exception):
    pass

class AuthenticationError(Exception):
    pass

class TokenInvalidError(Exception):
    pass

class IdentityService:
    # 단순화를 위해 클래스 변수로 토큰 캐시 사용 (실제 프로덕션에서는 Redis 등 사용)
    _token_cache = {}

    def validate_token(self, token):
        """토큰을 검증하고, 유효하면 토큰 데이터를 반환합니다."""
        token_data = self._token_cache.get(token)
        if not token_data:
            raise TokenInvalidError("Token not found or invalid.")

        if datetime.now() > token_data['expires_at']:
            del self._token_cache[token]  # 만료된 토큰 삭제
            raise TokenInvalidError("Token has expired.")
            
        return token_data

    def create_project(self, name):
        """새로운 프로젝트를 생성합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO projects (name) VALUES (?)", (name,))
                conn.commit()
                project_id = cursor.lastrowid
                return {"id": project_id, "name": name}
        except sqlite3.IntegrityError:
            raise ProjectCreationError(f"Project with name '{name}' already exists.")
        except sqlite3.Error as e:
            raise ProjectCreationError(f"Database error on project creation: {e}")

    def list_projects(self):
        """모든 프로젝트의 목록을 조회합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM projects ORDER BY name ASC")
                projects = [dict(row) for row in cursor.fetchall()]
                return projects
        except sqlite3.Error as e:
            raise Exception(f"Database error on listing projects: {e}")

    def get_project(self, project_id):
        """ID로 특정 프로젝트를 조회합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM projects WHERE id = ?", (project_id,))
                project = cursor.fetchone()
                if not project:
                    raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")
                return dict(project)
        except sqlite3.Error as e:
            raise Exception(f"Database error on getting project: {e}")

    def delete_project(self, project_id):
        """프로젝트를 삭제합니다. 단, VM이 없는 경우에만 가능합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as vm_count FROM vms WHERE project_id = ?", (project_id,))
                if cursor.fetchone()['vm_count'] > 0:
                    raise ProjectNotEmptyError(f"Project '{project_id}' is not empty.")
                
                cursor.execute("DELETE FROM user_project_roles WHERE project_id = ?", (project_id,))
                cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                conn.commit()
                
                if cursor.rowcount == 0:
                    raise ProjectNotFoundError(f"Project with id '{project_id}' not found.")
                return True
        except sqlite3.Error as e:
            raise Exception(f"Database error on deleting project: {e}")

    def create_user(self, username, password):
        """새로운 사용자를 생성합니다. 비밀번호는 해시하여 저장합니다."""
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
                conn.commit()
                user_id = cursor.lastrowid
                return {"id": user_id, "username": username}
        except sqlite3.IntegrityError:
            raise UserCreationError(f"User with username '{username}' already exists.")
        except sqlite3.Error as e:
            raise UserCreationError(f"Database error on user creation: {e}")

    def list_users(self):
        """모든 사용자의 목록을 조회합니다. (비밀번호 해시 제외)"""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, username FROM users ORDER BY username ASC")
                users = [dict(row) for row in cursor.fetchall()]
                return users
        except sqlite3.Error as e:
            raise Exception(f"Database error on listing users: {e}")

    def get_user(self, user_id):
        """ID로 특정 사용자를 조회합니다. (비밀번호 해시 제외)"""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
                if not user:
                    raise UserNotFoundError(f"User with id '{user_id}' not found.")
                return dict(user)
        except sqlite3.Error as e:
            raise Exception(f"Database error on getting user: {e}")

    def delete_user(self, user_id):
        """사용자를 삭제하고, 모든 프로젝트에서 멤버십을 제거합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_project_roles WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                if cursor.rowcount == 0:
                    raise UserNotFoundError(f"User with id '{user_id}' not found.")
                return True
        except sqlite3.Error as e:
            raise Exception(f"Database error on deleting user: {e}")

    def assign_role(self, user_id, project_id, role_name):
        """사용자에게 프로젝트의 역할을 부여합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
                role = cursor.fetchone()
                if not role:
                    raise RoleNotFoundError(f"Role '{role_name}' not found.")
                role_id = role['id']
                
                cursor.execute("INSERT OR IGNORE INTO user_project_roles (user_id, project_id, role_id) VALUES (?, ?, ?)",
                               (user_id, project_id, role_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            raise Exception(f"Database error on assigning role: {e}")

    def revoke_role(self, user_id, project_id, role_name):
        """사용자의 프로젝트 역할을 회수합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
                role = cursor.fetchone()
                if not role:
                    raise RoleNotFoundError(f"Role '{role_name}' not found.")
                role_id = role['id']

                cursor.execute("DELETE FROM user_project_roles WHERE user_id = ? AND project_id = ? AND role_id = ?",
                               (user_id, project_id, role_id))
                conn.commit()
                return True
        except sqlite3.Error as e:
            raise Exception(f"Database error on revoking role: {e}")

    def list_project_members(self, project_id):
        """특정 프로젝트에 속한 멤버와 역할 목록을 조회합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT u.id, u.username, r.name as role 
                    FROM users u
                    JOIN user_project_roles upr ON u.id = upr.user_id
                    JOIN roles r ON upr.role_id = r.id
                    WHERE upr.project_id = ?
                """, (project_id,))
                members = [dict(row) for row in cursor.fetchall()]
                return members
        except sqlite3.Error as e:
            raise Exception(f"Database error on listing project members: {e}")

    def authenticate(self, username, password, project_name):
        """사용자 자격증명을 검증하고, 성공 시 범위가 지정된 토큰을 발급합니다."""
        try:
            with DBConnector() as conn:
                cursor = conn.cursor()
                # 1. 사용자 및 비밀번호 검증
                cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()
                if not user:
                    raise AuthenticationError("Invalid username or password.")
                
                password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                if user['password_hash'] != password_hash:
                    raise AuthenticationError("Invalid username or password.")
                
                # 2. 프로젝트 검증
                cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
                project = cursor.fetchone()
                if not project:
                    raise AuthenticationError(f"Project '{project_name}' not found.")
                
                # 3. 사용자-프로젝트 멤버십 검증
                cursor.execute("SELECT role_id FROM user_project_roles WHERE user_id = ? AND project_id = ?", (user['id'], project['id']))
                if not cursor.fetchone():
                    raise AuthenticationError(f"User '{username}' is not a member of project '{project_name}'.")

                # 4. 토큰 생성 및 저장
                token = str(uuid.uuid4())
                expires_at = datetime.now() + timedelta(hours=1)
                self._token_cache[token] = {
                    'user_id': user['id'],
                    'project_id': project['id'],
                    'expires_at': expires_at
                }
                return {"token": token, "expires_at": expires_at.isoformat()}

        except sqlite3.Error as e:
            raise AuthenticationError(f"Database error during authentication: {e}")
