# tests/utils/test_vm_xml_generator.py
import uuid
from src.utils.vm_xml_generator import generate_vm_xml

def test_generate_vm_xml_successfully():
    """
    Test that generate_vm_xml creates a valid XML string with all parameters correctly substituted.
    """
    # 1. 준비 (Arrange)
    vm_name = "test-vm-01"
    vm_uuid = str(uuid.uuid4())
    cpu_count = 2
    ram_mb = 2048
    image_filepath = "/var/lib/libvirt/images/test-vm-01.qcow2"
    
    # 2. 실행 (Act)
    generated_xml = generate_vm_xml(
        vm_name=vm_name,
        vm_uuid=vm_uuid,
        cpu_count=cpu_count,
        ram_mb=ram_mb,
        image_filepath=image_filepath
    )
    
    # 3. 단언 (Assert)
    assert f"<name>{vm_name}</name>" in generated_xml
    assert f"<uuid>{vm_uuid}</uuid>" in generated_xml
    assert f"<vcpu>{cpu_count}</vcpu>" in generated_xml
    
    # RAM은 KiB로 변환되었는지 확인
    ram_kib = ram_mb * 1024
    assert f"<memory unit='KiB'>{ram_kib}</memory>" in generated_xml
    assert f"<currentMemory unit='KiB'>{ram_kib}</currentMemory>" in generated_xml
    
    # 이미지 파일 경로 확인
    assert f"<source file='{image_filepath}'/>" in generated_xml
    
    # 템플릿의 다른 고정적인 부분도 포함되어 있는지 간단히 확인
    assert "<domain type='kvm'>" in generated_xml
    assert "<driver name='qemu' type='qcow2'/>" in generated_xml
