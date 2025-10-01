# src/utils/vm_xml_generator.py
import os
from pathlib import Path
import uuid # UUID 생성을 위해 추가

# DB 파일 경로 설정과 동일하게 PROJECT_ROOT를 기준으로 템플릿 파일 경로를 찾습니다.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = str(PROJECT_ROOT / 'configs' / 'vm_template.xml')

def get_xml_template():
    """템플릿 파일을 읽어 XML 내용을 반환합니다."""
    try:
        with open(TEMPLATE_PATH, 'r') as f:
            return f.read()
    except FileNotFoundError:
        # 파일이 없으면 명확한 에러 메시지 반환
        raise Exception(f"VM template file not found at {TEMPLATE_PATH}. Please check 'configs/vm_template.xml'.")

# 템플릿 내용을 한 번만 읽어와서 저장 (성능 최적화)
XML_TEMPLATE = get_xml_template()


def generate_vm_xml(vm_name, vm_uuid, cpu_count, ram_mb, image_filepath): # 👈 image_filepath 인자 추가
    """
    템플릿에 VM 스펙을 채워 넣어 최종 XML을 생성합니다.
    """
    # 메모리는 KiB 단위로 변환
    ram_kib = ram_mb * 1024
    
    # 템플릿 문자열에 모든 동적 변수를 채워 넣습니다.
    xml = XML_TEMPLATE.format(
        vm_name=vm_name,
        vm_uuid=vm_uuid,
        cpu_count=cpu_count,
        ram_kib=ram_kib,
        image_filepath=image_filepath # 👈 이미지 경로 채우기
    )
    return xml