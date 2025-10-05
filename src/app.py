# src/app.py
from wsgiref.simple_server import make_server
import json
import os
import sys
import re

from services.compute_service import ComputeService, VmNotFoundError, VmAlreadyExistsError, ImageNotFoundError
from services.identity_service import (
    IdentityService, ProjectCreationError, UserCreationError, 
    ProjectNotFoundError, ProjectNotEmptyError, UserNotFoundError, 
    RoleNotFoundError, TokenInvalidError, AuthenticationError
)

# --------------------------------------------------------------------------
## 요청 처리 유틸리티 함수
# --------------------------------------------------------------------------

def get_request_data(environ):
    """environ에서 요청 본문을 읽어와 JSON으로 파싱"""
    try:
        content_length = int(environ.get("CONTENT_LENGTH", 0))
        if content_length > 0:
            request_body = environ["wsgi.input"].read(content_length)
            return json.loads(request_body.decode("utf-8"))
        return {}
    except (ValueError, KeyError, json.JSONDecodeError):
        raise ValueError("Invalid or missing JSON body.")

def authorize_and_get_token_data(environ):
    """X-Auth-Token을 검증하고, 유효하면 토큰 데이터를 반환"""
    auth_token = environ.get('HTTP_X_AUTH_TOKEN')
    if not auth_token:
        raise TokenInvalidError("Missing 'X-Auth-Token' header.")
    
    identity = IdentityService()
    token_data = identity.validate_token(auth_token)
    return token_data

def handle_exception(e):
    """예외 처리 및 응답 본문 생성"""
    error_message = str(e)
    
    if isinstance(e, (TokenInvalidError, AuthenticationError)):
        status = "401 Unauthorized"
    elif isinstance(e, (VmNotFoundError, ProjectNotFoundError, UserNotFoundError, RoleNotFoundError)):
        status = "404 Not Found"
    elif isinstance(e, (ValueError, VmAlreadyExistsError, ImageNotFoundError, ProjectCreationError, UserCreationError, ProjectNotEmptyError)):
        status = "400 Bad Request"
    else:
        status = "500 Internal Server Error"
        
    response_body = json.dumps({"error": error_message})
    return status, response_body

# --------------------------------------------------------------------------
## WSGI 애플리케이션 함수 (라우팅 및 핸들링)
# --------------------------------------------------------------------------

def application(environ, start_response):
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "")
    
    routes = [
        # Compute Service (Protected)
        ('GET', r'^/v1/vms$', list_vms_handler),
        ('POST', r'^/v1/vms$', create_vm_handler),
        ('DELETE', r'^/v1/vms/([a-zA-Z0-9_-]+)$', delete_vm_handler),
        
        # Admin/Internal Actions
        ('POST', r'^/v1/actions/reconcile$', reconcile_vms_handler),

        # Identity Service & Auth
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

    handler = None
    path_args = []

    for route_method, pattern, route_handler in routes:
        if method == route_method:
            match = re.match(pattern, path)
            if match:
                handler = route_handler
                path_args = match.groups()
                break
    
    try:
        if handler:
            status, response_body = handler(environ, *path_args)
        else:
            status = '404 Not Found'
            response_body = json.dumps({'error': 'Not Found'})
            
    except Exception as e:
        status, response_body = handle_exception(e)

    start_response(status, [("Content-Type", "application/json")])
    return [response_body.encode("utf-8")]

# --------------------------------------------------------------------------
## 핸들러 함수
# --------------------------------------------------------------------------

# --- Compute Handlers (Protected) ---
def list_vms_handler(environ):
    token_data = authorize_and_get_token_data(environ)
    project_id = token_data['project_id']
    
    compute = ComputeService()
    vms = compute.list_vms(project_id)
    return '200 OK', json.dumps({'vms': vms})

def create_vm_handler(environ):
    token_data = authorize_and_get_token_data(environ)
    project_id = token_data['project_id']

    request_data = get_request_data(environ)
    vm_name = request_data.get("name")
    cpu = request_data.get("cpu")
    ram = request_data.get("ram")
    image_name = request_data.get("image_name")

    if not all([vm_name, cpu, ram, image_name]):
        raise ValueError("Missing required VM parameters (name, cpu, ram, image_name).")

    compute = ComputeService()
    vm_name, vm_uuid = compute.create_vm(project_id, vm_name, cpu, ram, image_name)
    response_body = json.dumps({"message": f"VM {vm_name} created.", "uuid": vm_uuid})
    return '201 Created', response_body

def delete_vm_handler(environ, vm_name):
    token_data = authorize_and_get_token_data(environ)
    project_id = token_data['project_id']

    compute = ComputeService()
    compute.destroy_vm(project_id, vm_name)
    response_body = json.dumps({"message": f"VM '{vm_name}' deleted."})
    return '200 OK', response_body

def reconcile_vms_handler(environ):
    compute = ComputeService()
    ghost_vms = compute.reconcile_vms()
    count = len(ghost_vms)
    response_body = json.dumps({
        "message": f"Reconciliation complete. Found {count} ghost VM(s).",
        "ghost_vms": ghost_vms
    })
    return '200 OK', response_body

# --- Identity Handlers ---
def create_project_handler(environ):
    request_data = get_request_data(environ)
    project_name = request_data.get("name")
    if not project_name:
        raise ValueError("Missing required parameter: name")
    
    identity = IdentityService()
    project = identity.create_project(project_name)
    return '201 Created', json.dumps(project)

def list_projects_handler(environ):
    identity = IdentityService()
    projects = identity.list_projects()
    return '200 OK', json.dumps({"projects": projects})

def get_project_handler(environ, project_id):
    identity = IdentityService()
    project = identity.get_project(int(project_id))
    return '200 OK', json.dumps(project)

def delete_project_handler(environ, project_id):
    identity = IdentityService()
    identity.delete_project(int(project_id))
    return '204 No Content', ''

def create_user_handler(environ):
    request_data = get_request_data(environ)
    username = request_data.get("username")
    password = request_data.get("password")
    if not all([username, password]):
        raise ValueError("Missing required parameters: username, password")
    
    identity = IdentityService()
    user = identity.create_user(username, password)
    return '201 Created', json.dumps(user)

def list_users_handler(environ):
    identity = IdentityService()
    users = identity.list_users()
    return '200 OK', json.dumps({"users": users})

def get_user_handler(environ, user_id):
    identity = IdentityService()
    user = identity.get_user(int(user_id))
    return '200 OK', json.dumps(user)

def delete_user_handler(environ, user_id):
    identity = IdentityService()
    identity.delete_user(int(user_id))
    return '204 No Content', ''

def list_project_members_handler(environ, project_id):
    identity = IdentityService()
    members = identity.list_project_members(int(project_id))
    return '200 OK', json.dumps({"members": members})

def assign_role_handler(environ, project_id, user_id, role_name):
    identity = IdentityService()
    identity.assign_role(int(user_id), int(project_id), role_name)
    return '204 No Content', ''

def revoke_role_handler(environ, project_id, user_id, role_name):
    identity = IdentityService()
    identity.revoke_role(int(user_id), int(project_id), role_name)
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
