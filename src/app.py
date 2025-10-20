# src/app.py
from wsgiref.simple_server import make_server
import json
import sys
import re

# SQLAlchemy 및 의존성 임포트
from src.database.database import SessionLocal
from src.repositories.sqlalchemy.sqlalchemy_vm_repository import SqlalchemyVMRepository
from src.repositories.sqlalchemy.sqlalchemy_image_repository import SqlalchemyImageRepository
from src.repositories.sqlalchemy.sqlalchemy_project_repository import SqlalchemyProjectRepository
from src.repositories.sqlalchemy.sqlalchemy_user_repository import SqlalchemyUserRepository
from src.repositories.sqlalchemy.sqlalchemy_role_repository import SqlalchemyRoleRepository
from src.services.compute_service import ComputeService
from src.services.image_service import ImageService
from src.services.identity_service import IdentityService
from src.services.exceptions import *

# --------------------------------------------------------------------------
## 요청 처리 유틸리티 함수
# --------------------------------------------------------------------------

def get_request_data(environ):
    try:
        content_length = int(environ.get("CONTENT_LENGTH", 0))
        return json.loads(environ["wsgi.input"].read(content_length)) if content_length > 0 else {}
    except (ValueError, json.JSONDecodeError):
        raise ValueError("Invalid or missing JSON body.")

def authorize_and_get_token_data(environ):
    auth_token = environ.get('HTTP_X_AUTH_TOKEN')
    if not auth_token:
        raise TokenInvalidError("Missing 'X-Auth-Token' header.")
    identity_service = environ['services']['identity']
    return identity_service.validate_token(auth_token)

def handle_exception(e):
    error_map = {
        TokenInvalidError: "401 Unauthorized",
        AuthenticationError: "401 Unauthorized",
        VmNotFoundError: "404 Not Found",
        ProjectNotFoundError: "404 Not Found",
        UserNotFoundError: "404 Not Found",
        RoleNotFoundError: "404 Not Found",
        ImageNotFoundError: "404 Not Found",
        ValueError: "400 Bad Request",
        VmAlreadyExistsError: "400 Bad Request",
        ProjectCreationError: "400 Bad Request",
        UserCreationError: "400 Bad Request",
        ProjectNotEmptyError: "400 Bad Request",
    }
    status = error_map.get(type(e), "500 Internal Server Error")
    return status, json.dumps({"error": str(e)})

# --------------------------------------------------------------------------
## WSGI 애플리케이션 (의존성 주입 및 라우팅)
# --------------------------------------------------------------------------

def application(environ, start_response):
    db_session = SessionLocal()
    try:
        # 1. 의존성 생성 (Repositories -> Services)
        vm_repo = SqlalchemyVMRepository(db_session)
        image_repo = SqlalchemyImageRepository(db_session)
        project_repo = SqlalchemyProjectRepository(db_session)
        user_repo = SqlalchemyUserRepository(db_session)
        role_repo = SqlalchemyRoleRepository(db_session)

        image_service = ImageService(image_repo)
        identity_service = IdentityService(user_repo, project_repo, role_repo, vm_repo)
        compute_service = ComputeService(vm_repo, image_service)

        # 2. 생성된 서비스 객체들을 environ을 통해 핸들러에 전달
        environ['services'] = {
            'compute': compute_service,
            'image': image_service,
            'identity': identity_service
        }

        # 3. 라우팅 및 핸들러 실행
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "")
        
        routes = [
            ('GET', r'^/v1/vms$', list_vms_handler),
            ('POST', r'^/v1/vms$', create_vm_handler),
            ('DELETE', r'^/v1/vms/([a-zA-Z0-9_-]+)$', delete_vm_handler),
            ('POST', r'^/v1/actions/reconcile$', reconcile_vms_handler),
            ('POST', r'^/v1/auth/tokens$', auth_tokens_handler),
            ('POST', r'^/v1/projects$', create_project_handler),
            ('GET', r'^/v1/projects$', list_projects_handler),
            ('GET', r'^/v1/projects/([0-9]+)$', get_project_handler),
            ('DELETE', r'^/v1/projects/([0-9]+)$', delete_project_handler),
            ('GET', r'^/v1/projects/([0-9]+)/users$', list_project_members_handler),
            ('PUT', r'^/v1/projects/([0-9]+)/users/([0-9]+)/roles/([a-zA-Z]+)$', assign_role_handler),
            ('DELETE', r'^/v1/projects/([0-9]+)/users/([0-9]+)/roles/([a-zA-Z]+)$', revoke_role_handler),
            ('POST', r'^/v1/users$', create_user_handler),
            ('GET', r'^/v1/users$', list_users_handler),
            ('GET', r'^/v1/users/([0-9]+)$', get_user_handler),
            ('DELETE', r'^/v1/users/([0-9]+)$', delete_user_handler),
        ]

        handler, path_args = None, []
        for route_method, pattern, route_handler in routes:
            if method == route_method and (match := re.match(pattern, path)):
                handler, path_args = route_handler, match.groups()
                break
        
        if handler:
            status, response_body = handler(environ, *path_args)
        else:
            status, response_body = '404 Not Found', json.dumps({'error': 'Not Found'})

    except Exception as e:
        status, response_body = handle_exception(e)
    finally:
        db_session.close()

    start_response(status, [("Content-Type", "application/json")])
    return [response_body.encode("utf-8")]

# --------------------------------------------------------------------------
## 핸들러 함수 (전체 리팩토링 완료)
# --------------------------------------------------------------------------

def list_vms_handler(environ, *args):
    token_data = authorize_and_get_token_data(environ)
    vms = environ['services']['compute'].list_vms(token_data['project_id'])
    return '200 OK', json.dumps({'vms': vms})

def create_vm_handler(environ, *args):
    token_data = authorize_and_get_token_data(environ)
    data = get_request_data(environ)
    vm_name, vm_uuid = environ['services']['compute'].create_vm(
        project_id=token_data['project_id'], **data
    )
    return '201 Created', json.dumps({"message": f"VM {vm_name} created.", "uuid": vm_uuid})

def delete_vm_handler(environ, vm_name):
    token_data = authorize_and_get_token_data(environ)
    environ['services']['compute'].destroy_vm(token_data['project_id'], vm_name)
    return '200 OK', json.dumps({"message": f"VM '{vm_name}' deleted."})

def reconcile_vms_handler(environ, *args):
    ghost_vms = environ['services']['compute'].reconcile_vms()
    return '200 OK', json.dumps({"ghost_vms": ghost_vms})

def auth_tokens_handler(environ, *args):
    data = get_request_data(environ)
    token = environ['services']['identity'].authenticate(**data)
    return '201 Created', json.dumps(token)

def create_project_handler(environ, *args):
    data = get_request_data(environ)
    project = environ['services']['identity'].create_project(data.get('name'))
    return '201 Created', json.dumps(project)

def list_projects_handler(environ, *args):
    projects = environ['services']['identity'].list_projects()
    return '200 OK', json.dumps({"projects": projects})

def get_project_handler(environ, project_id):
    project = environ['services']['identity'].get_project(int(project_id))
    return '200 OK', json.dumps(project)

def delete_project_handler(environ, project_id):
    environ['services']['identity'].delete_project(int(project_id))
    return '204 No Content', ''

def create_user_handler(environ, *args):
    data = get_request_data(environ)
    user = environ['services']['identity'].create_user(**data)
    return '201 Created', json.dumps(user)

def list_users_handler(environ, *args):
    users = environ['services']['identity'].list_users()
    return '200 OK', json.dumps({"users": users})

def get_user_handler(environ, user_id):
    user = environ['services']['identity'].get_user(int(user_id))
    return '200 OK', json.dumps(user)

def delete_user_handler(environ, user_id):
    environ['services']['identity'].delete_user(int(user_id))
    return '204 No Content', ''

def list_project_members_handler(environ, project_id):
    members = environ['services']['identity'].list_project_members(int(project_id))
    return '200 OK', json.dumps({"members": members})

def assign_role_handler(environ, project_id, user_id, role_name):
    environ['services']['identity'].assign_role(int(user_id), int(project_id), role_name)
    return '204 No Content', ''

def revoke_role_handler(environ, project_id, user_id, role_name):
    environ['services']['identity'].revoke_role(int(user_id), int(project_id), role_name)
    return '204 No Content', ''

# --------------------------------------------------------------------------
## 서버 실행
# --------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        with make_server("", 8000, application) as httpd:
            print("Serving IaaS Monolith Prototype on port 8000...")
            httpd.serve_forever()
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)