# src/app.py
from wsgiref.simple_server import make_server
import json
import os
import sys

# ComputeService 임포트
from services.compute_service import ComputeService 

# --------------------------------------------------------------------------
## 요청 처리 유틸리티 함수
# --------------------------------------------------------------------------

def get_request_data(environ):
    """environ에서 요청 본문을 읽어와 JSON으로 파싱"""
    try:
        # 요청 본문의 길이(Content-Length)를 가져와서
        content_length = int(environ.get('CONTENT_LENGTH', 0))
        if content_length > 0:
            # wsgi.input 스트림에서 데이터 읽기
            request_body = environ['wsgi.input'].read(content_length)
            # 바이트 데이터를 디코딩 후 JSON 파싱
            return json.loads(request_body.decode('utf-8'))
        return {}
    except (ValueError, KeyError, json.JSONDecodeError):
        # JSON 형식이 잘못되었거나 Content-Length가 이상할 때
        raise Exception("Invalid or missing JSON body.")

def handle_exception(e):
    """예외 처리 및 500 응답 본문 생성"""
    error_message = str(e)
    # libvirt 에러 등에서 바이트 데이터가 섞여 들어올 경우를 대비
    try:
        error_message = error_message.decode('utf-8')
    except (AttributeError, UnicodeDecodeError):
        pass 
    
    response_body = json.dumps({'error': error_message}) 
    return '500 Internal Server Error', response_body

# --------------------------------------------------------------------------
## WSGI 애플리케이션 함수 (라우팅 및 핸들링)
# --------------------------------------------------------------------------

def application(environ, start_response):
    path = environ.get('PATH_INFO', '')
    method = environ.get('REQUEST_METHOD', '')
    
    try:
        # 1. VM 목록 조회 (GET /v1/vms) - DB 기반
        if path == '/v1/vms' and method == 'GET':
            compute = ComputeService()
            vms = compute.list_vms() # DB에서 목록을 읽어옴
            response_body = json.dumps({'vms': vms})
            status = '200 OK'

        # 2. VM 생성 (POST /v1/vms) - JSON 파싱, DB 연동, XML 생성
        elif path == '/v1/vms' and method == 'POST':
            # 1) JSON 데이터 파싱
            request_data = get_request_data(environ)
            vm_name = request_data.get('name')
            cpu = request_data.get('cpu')
            ram = request_data.get('ram')
            image_name = request_data.get('image_name') # 👈 이미지 이름 파싱
            
            # 2) 필수 인자 검사
            if not all([vm_name, cpu, ram, image_name]):
                raise ValueError("Missing required VM parameters (name, cpu, ram, image_name).")
                
            # 3) ComputeService 호출 (DB 체크, XML 생성, VM 생성, DB 저장 모두 수행)
            compute = ComputeService()
            # 💥 image_name 인자 포함하여 호출 💥
            vm_name, vm_uuid = compute.create_vm(vm_name, cpu, ram, image_name) 
            
            # 4) 응답
            response_body = json.dumps({'message': f"VM {vm_name} created.", 'uuid': vm_uuid})
            status = '201 Created'
        
        # 3. 그 외 404
        else:
            response_body = json.dumps({'error': 'Not Found'})
            status = '404 Not Found'
            
    except Exception as e:
        status, response_body = handle_exception(e)

    # 최종 응답 전송
    start_response(status, [('Content-Type', 'application/json')])
    return [response_body.encode('utf-8')]

if __name__ == '__main__':
    try:
        with make_server('', 8000, application) as httpd:
            print("Serving IaaS Monolith Prototype on port 8000...")
            httpd.serve_forever()
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)