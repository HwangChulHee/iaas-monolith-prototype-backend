# src/app.py
from wsgiref.simple_server import make_server
import json
import os
import sys
import re  # 👈 정규표현식 모듈 임포트

# ComputeService 임포트
from services.compute_service import ComputeService, VmNotFoundError

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
        raise Exception("Invalid or missing JSON body.")

def handle_exception(e):
    """예외 처리 및 응답 본문 생성"""
    error_message = str(e)
    try:
        error_message = error_message.decode("utf-8")
    except (AttributeError, UnicodeDecodeError):
        pass
    
    # 사용자 정의 예외에 따라 상태 코드 분기
    if isinstance(e, VmNotFoundError):
        status = "404 Not Found"
        response_body = json.dumps({"error": error_message})
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
    
    # 💡 정규표현식을 사용한 라우팅
    routes = [
        ('GET', r'^/v1/vms$', list_vms_handler),
        ('POST', r'^/v1/vms$', create_vm_handler),
        ('DELETE', r'^/v1/vms/([a-zA-Z0-9_-]+)$', delete_vm_handler),
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
    compute = ComputeService()
    vms = compute.list_vms()
    return '200 OK', json.dumps({'vms': vms})

def create_vm_handler(environ):
    request_data = get_request_data(environ)
    vm_name = request_data.get("name")
    cpu = request_data.get("cpu")
    ram = request_data.get("ram")
    image_name = request_data.get("image_name")

    if not all([vm_name, cpu, ram, image_name]):
        raise ValueError("Missing required VM parameters (name, cpu, ram, image_name).")

    compute = ComputeService()
    vm_name, vm_uuid = compute.create_vm(vm_name, cpu, ram, image_name)
    response_body = json.dumps({"message": f"VM {vm_name} created.", "uuid": vm_uuid})
    return '201 Created', response_body

def delete_vm_handler(environ, vm_name):
    compute = ComputeService()
    compute.destroy_vm(vm_name)
    response_body = json.dumps({"message": f"VM '{vm_name}' deleted."})
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
