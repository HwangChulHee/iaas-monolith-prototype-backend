# 개발 로그

## 2025-10-03

#### ✅ 완료된 작업
- VM 삭제 API (`DELETE /v1/vms/<vm_name>`) 구현 및 테스트 완료.
- 삭제 로직 구현: Libvirt VM 제거, 디스크 파일(.qcow2) 삭제, DB 레코드 삭제.
- `app.py` 라우팅 로직 개선 (정규표현식 기반으로 리팩토링).
- **모니터링 기반 구축**: `list_vms` API가 DB와 libvirt의 실시간 상태를 통합하여 반환하도록 개선.

#### 🐛 트러블슈팅 기록
- **문제**: VM 삭제 시 디스크 파일에 대한 `Permission denied` 오류 발생.
  - **원인**: `vagrant` 사용자로 실행된 API 서버가 `root` 소유의 디스크 파일을 삭제할 권한 없음.
  - **해결**: `os.remove` 대신 `subprocess`를 통해 `sudo rm -f`를 호출하도록 `compute_service.py` 수정.

- **문제**: `destroy_vm` 메서드에서 경로 조작(Path Traversal) 보안 취약점 발견.
  - **원인**: 사용자 입력(`vm_name`)을 검증 없이 파일 경로 생성에 사용.
  - **해결**: `os.path.basename()`을 사용해 파일명만 추출하도록 로직 보강.

- **문제**: `make db-clean` 실행 시 `NameError: __file__ is not defined` 오류 발생.
  - **원인**: `python -c` 명령 환경에서는 `__file__` 변수 사용 불가.
  - **해결**: `Makefile`에서 복잡한 경로 계산 로직을 제거하고, 단순 상대 경로(`iaas_metadata.db`)를 사용하도록 수정.

---

## 완료된 작업 및 로그

### 2025-10-01

-   **완료**: DB 연동 기반 VM 생성 API(POST /v1/vms) 완성.
-   **완료**: 동적 XML, CoW 디스크 복제 로직을 통한 VM 동시 생성 성공.
-   **트러블슈팅**: VM 생성 API 호출 시 XML 문법 오류 및 QEMU/Libvirt 호환성 오류 해결 (XML 템플릿 최소화 및 안정화).
-   **트러블슈팅**: `Failed to get "write" lock` 오류 해결 (CoW 복제본 디스크 생성 로직으로 변경).
-   **트러블슈팅**: VM 이름 중복 생성 가능성 해결 (DB 기반 중복 체크 로직 추가).

### 2025-09-30

-   **완료**: libvirt 그룹에 사용자(vagrant) 권한 추가하여 sudo 없이 API 및 virsh 실행.

### 2025-09-21

-   **트러블슈팅**: libvirt-python 코드 root 권한 실행 문제 해결 (그룹 권한 설정).
-   **학습**: libvirt와 virsh의 관계 및 libvirt-python의 작동 원리 학습.

### 2025-09-20

-   **완료**: VS Code Remote - SSH로 Dev-VM 연결 성공.
-   **완료**: VM 생성을 위한 최소한의 XML 설계도(ubuntu-simple.xml) 작성 완료.
-   **완료**: `virsh` 및 `create_vm.py`를 통해 VM 생성 성공.
-   **완료**: 프로젝트 코드를 GitHub에 업로드 완료.

### 2025-09-19

-   **완료**: 프로젝트 목표, 기능, 로드맵, 기술 스택 등 전체 계획 수립 완료.
-   **완료**: 개발 방법론을 '수직적 슬라이스' 방식으로 확정.
-   **완료**: Vagrant를 이용한 중첩 가상화 개발 환경 설계 및 구축 완료.
-   **트러블슈팅**: `vagrant up` 시 `pip3 install libvirt-python` 실패 해결 (의존성 패키지 추가).
-   **학습**: Vagrant, 중첩 가상화, WSGI, libvirt, IP 개념, IaaS 아키텍처, Terraform과 비교 등 학습.

---

## 요약 및 다음 단계

### 기술 부채
- qemu의 정확한 용도를 모름

### 다음 단계: VM 제어 및 모니터링 기반 완성

이제 VM을 만들 줄 아니, 네 로드맵 Phase 1의 나머지 주요 과업인 VM 생명 주기 관리와 모니터링 기반을 완성해야 해.

1.  **🗑️ 다음 행동: VM 삭제 API 구현**
    가장 먼저 해야 할 일은 VM을 깔끔하게 지우는 기능이야. VM 생성과 달리, 삭제는 세 군데에서 처리해야 돼.
    -   **API**: DELETE /v1/vms/<VM 이름> 엔드포인트 구현.
    -   **Libvirt**: virsh destroy (강제 종료) 후 virsh undefine (정의 제거) 호출.
    -   **DB**: vms 테이블에서 해당 VM 레코드 삭제.
    -   **디스크**: /var/lib/libvirt/images/<vm_name>.qcow2 복제본 파일을 삭제. (이걸 안 지우면 디스크 용량이 낭비돼.)
2.  **📊 모니터링 기반 구축: 실시간 상태 반영**
    현재 GET /v1/vms는 VM의 DB 기록 상태만 보여줘. 만약 VM이 외부에서 강제 종료되면 DB와 실제 상태가 달라져.
    -   **작업**: ComputeService.list_vms() 메서드를 수정해야 해. DB에서 VM 목록(이름, UUID)을 읽은 후, 각 VM마다 libvirt-python의 domain.info()를 호출해서 실제 상태(VIR_DOMAIN_RUNNING 등)를 가져와 DB 정보와 병합해서 반환해야지. (이게 AWS나 OpenStack의 VM 목록 조회 방식이야.)

---


