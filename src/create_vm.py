import libvirt
import sys

def read_xml_file(filepath):
    """
    지정된 경로의 XML 파일을 읽어와 내용을 반환합니다.
    """
    try:
        with open(filepath, 'r') as f:
            xml_config = f.read()
            return xml_config
    except FileNotFoundError:
        print(f"오류: {filepath} 파일을 찾을 수 없습니다.", file=sys.stderr)
        sys.exit(1)

try:
    # 1. libvirt 시스템 데몬에 연결. 
    conn = libvirt.open('qemu:///system')
    if conn is None:
        raise Exception('Failed to open connection to the hypervisor.')
        
    # 2. XML 파일을 읽어와 VM 정의
    xml_config = read_xml_file('../configs/ubuntu-simple.xml')

    # 3. VM 설계도(XML)로 VM을 정의 (libvirt에 등록).
    domain = conn.defineXML(xml_config)
    if domain is None:
        raise Exception('Failed to define the VM from XML.')

    # 4. 정의된 VM을 시작(create).
    if domain.create() < 0:
        raise Exception('Failed to start the VM.')

    print(f"VM '{domain.name()}'이 성공적으로 생성되었습니다.")

except Exception as e:
    print(f"오류 발생: {e}", file=sys.stderr)
    sys.exit(1)

finally:
    if 'conn' in locals() and conn:
        conn.close()