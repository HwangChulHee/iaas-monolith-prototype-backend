# src/app.py
from wsgiref.simple_server import make_server
import json
import os
import sys
import re

from services.compute_service import ComputeService, VmNotFoundError, VmAlreadyExistsError, ImageNotFoundError

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

def get_project_id(environ):
    """environ에서 X-Project-ID 헤더를 읽어와 project_id를 반환"""
    project_id = environ.get('HTTP_X_PROJECT_ID')
    if not project_id:
        raise ValueError("Missing 'X-Project-ID' header.")
    try:
        return int(project_id)
    except (ValueError, TypeError):
        raise ValueError("'X-Project-ID' must be an integer.")

def handle_exception(e):
    """예외 처리 및 응답 본문 생성"""
    error_message = str(e)
    
    if isinstance(e, VmNotFoundError):
        status = "404 Not Found"
    elif isinstance(e, (ValueError, VmAlreadyExistsError, ImageNotFoundError)):
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
        ('GET', r'^/v1/vms$', list_vms_handler),
        ('POST', r'^/v1/vms$', create_vm_handler),
        ('DELETE', r'^/v1/vms/([a-zA-Z0-9_-]+)$', delete_vm_handler),
        ('POST', r'^/v1/actions/reconcile$', reconcile_vms_handler),
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

def list_vms_handler(environ):
    project_id = get_project_id(environ)
    compute = ComputeService()
    vms = compute.list_vms(project_id)
    return '200 OK', json.dumps({'vms': vms})

def create_vm_handler(environ):
    project_id = get_project_id(environ)
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
    project_id = get_project_id(environ)
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
