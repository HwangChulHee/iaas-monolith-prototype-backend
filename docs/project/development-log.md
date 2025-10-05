# 개발 로그

## 2025-10-05 (저녁 3)

#### ✅ 완료된 작업
- **상태 동기화(Reconciliation) 기능 구현**: 실제 하이퍼바이저의 상태와 시스템 DB의 상태를 동기화하는 기능의 기반을 마련함.
  - **'유령 VM' 탐지 로직 추가**: `ComputeService`에 `reconcile_vms` 메서드를 추가하여, Libvirt에는 존재하지만 DB에는 없는 VM을 식별하는 기능을 구현.
  - **API 엔드포인트 추가**: `POST /v1/actions/reconcile` 엔드포인트를 `app.py`에 추가하여, 관리자가 수동으로 상태 동기화 프로세스를 실행하고 '유령 VM' 목록을 확인할 수 있도록 함.
  - **단위 테스트 작성**: `TestReconcileVms` 테스트 스위치를 추가하여, '유령 VM'이 있을 때와 없을 때 모두 정확하게 동작하는지 검증 완료.

---

## 2025-10-05 (저녁 2)

#### ✅ 완료된 작업
- **`destroy_vm` 메서드 리팩토링**: `try...finally` 구조를 도입하여 `destroy_vm` 메서드의 안정성을 강화함.
  - **개선**: Libvirt, 디스크, DB 정리 작업을 분리하고, 중간에 오류가 발생하더라도 최종적으로 DB 레코드가 반드시 삭제되도록 보장하여 '고아 레코드' 발생을 원천적으로 차단함.
- **`destroy_vm` 단위 테스트 커버리지 확보**:
  - **성공 케이스**: 모든 리소스가 정상적으로 삭제되는지 검증.
  - **실패 케이스 (VM 없음)**: DB에 VM이 없을 때 `VmNotFoundError`가 발생하는지 검증.
  - **실패 케이스 (Libvirt 도메인 없음)**: Libvirt에 도메인이 없어도 디스크와 DB 레코드가 정상적으로 삭제되는 '청소부' 역할을 검증.

#### 🤔 논의된 내용
- **'유령 VM' 처리 방안 논의**: Libvirt에는 존재하지만 DB에는 없는 VM의 처리 방안에 대해 논의함.
  - **결론**: 해당 VM은 `destroy_vm`의 책임 범위를 벗어나며, 주기적으로 상태를 비교하여 동기화하는 'Reconciliation' 프로세스가 필요하다는 결론을 내림. 이 기능은 향후 로드맵에 추가하기로 함.

---

## 2025-10-05 (저녁)

#### ✅ 완료된 작업
- **`create_vm` 메서드 리팩토링**: `ComputeService.create_vm`의 에러 처리 로직을 단일 `try-except` 블록으로 중앙화하고, 단계별 롤백 로직을 도입하여 안정성을 대폭 향상시킴.
  - **개선**: `VmAlreadyExistsError`, `ImageNotFoundError`, `VmCreationError` 등 명시적인 커스텀 예외를 정의하여 에러 발생 원인을 명확히 함.
  - **롤백 범위**: VM 생성 과정 중 어느 단계에서 실패하더라도 이전에 생성된 리소스(libvirt 도메인, 디스크 이미지)가 모두 정리되도록 보장.
- **단위 테스트 커버리지 확장**: 리팩토링된 `create_vm`의 안정성을 검증하기 위해 다양한 실패 시나리오에 대한 단위 테스트를 추가.
  - 디스크 생성 실패, libvirt VM 정의 실패, VM 시작 실패, 최종 DB 저장 실패 시 각각의 롤백 로직이 정확히 호출되는지 검증 완료.
- **테스트 코드 구조 개선**: `test_compute_service.py`의 테스트 클래스를 `TestCreateVm`과 `TestListVms`로 분리하여 가독성과 유지보수성을 높임.

#### 🐛 트러블슈팅 기록
- **문제**: 테스트 실행 시 `AttributeError` 및 `NameError` 발생.
  - **원인 1 (`AttributeError`)**: 실제 메서드에 `side_effect`나 `assert_called_once` 같은 모의 객체 전용 속성을 사용하려고 시도함.
  - **해결 1**: `@patch.object` 데코레이터를 사용하여 테스트 대상 메서드(`_save_vm_metadata_to_db`, `_rollback_vm_creation`)를 모의 객체로 올바르게 전환함.
  - **원인 2 (`NameError`)**: 테스트 코드에서 새로 정의한 커스텀 예외 클래스를 임포트하지 않음.
  - **해결 2**: `from src.services.compute_service import ...` 구문에 필요한 모든 예외 클래스를 추가함.
- **문제**: DB 저장 실패 테스트 중, 의도치 않은 `AttributeError: 'FakeDomain' object has no attribute 'create'` 발생.
  - **원인**: 테스트에 사용된 모의 객체 `FakeDomain`에 `create` 메서드가 없어 VM 시작 단계에서 실패함.
  - **해결**: `FakeDomain` 클래스에 `create(self): return 0` 메서드를 추가하여 실제 `libvirt` 도메인 객체처럼 동작하도록 수정.

---

## 2025-10-05

#### ✅ 완료된 작업
- **VM 생성 견고성 강화 (Rollback 구현)**: `ComputeService.create_vm` 메서드에 롤백 로직을 구현하여 트랜잭션의 안정성을 확보함.
  - **작동 방식**: DB 저장(Commit) 실패 시, 성공적으로 정의/시작된 Libvirt Domain을 `destroy()` 및 `undefine()`하고, `ImageService.delete_vm_disk`를 호출하여 복제된 디스크 파일(.qcow2)까지 삭제하도록 처리함.
- **단위 테스트 확장**: `test_create_vm_fails_if_db_insert_fails` 테스트를 추가하여 롤백 로직의 호출(Domain.destroy, Domain.undefine, ImageService.delete_vm_disk)을 검증 완료.

#### 🐛 트러블슈팅 기록
- **문제**: 롤백 로직 테스트가 코드 부재로 인해 거짓 성공(False Positive)을 발생시킴.
  - **해결**: 테스트 코드에 롤백 호출 검증 코드를 추가하여 실패를 강제했고, 이를 통해 롤백 로직 구현을 완료함.
- **개선**: `src/services/image_service.py`에 `delete_vm_disk` 메서드를 추가하여 디스크 파일 삭제 기능을 모듈화함.

---


## 2025-10-04

#### ✅ 완료된 작업
- **단위 테스트 기반 구축**: `pytest`와 `unittest.mock`을 도입하여 `ComputeService`에 대한 단위 테스트를 확장.
  - `list_vms` 메서드 검증 완료.
  - `create_vm` 메서드의 성공 케이스 및 주요 실패 케이스(이름 중복, 이미지 없음) 3건을 추가하여 안정성 강화.
- **Makefile 테스트 워크플로우 개선**: 개발 편의성을 위해 테스트 실행 명령어를 `Makefile`에 통합하고, 두 번의 개선을 통해 사용성을 높임.
  - `make test-all`: 프로젝트의 모든 테스트를 실행.
  - `make test file=<path>`: `tests/` 디렉토리 하위의 특정 파일만 지정하여 빠르게 테스트 가능.
- **협업 규칙 정립 및 문서화**: 개발자의 이해 증진 및 코드 품질 향상을 위해 아래 규칙들을 `GEMINI.md`에 명시하고 구체화함.
  - `Teach-back`, `왜? 질문 생활화`, `상호 코드 리뷰`
  - `단계별 설명`, `Sandbox 활용` 등 Gemini의 설명 방식 규칙.
  - `mcp` 툴과 일반 파일 수정의 역할을 구분하는 파일 관리 규칙.


#### 🐛 트러블슈팅 기록
- **문제**: `pytest` 실행 시 `ModuleNotFoundError: No module named 'database'` 발생.
  - **원인**: 테스트 실행 환경에서 `src` 디렉토리를 소스 코드로 인식하지 못함.
  - **해결**: `PYTHONPATH=src` 환경 변수를 설정하여 파이썬이 모듈을 찾을 수 있도록 경로를 지정.
- **문제**: 단위 테스트 실행 시 `AssertionError: assert 'UNKNOWN' == 'RUNNING'` 발생.
  - **원인**: `libvirt` 모듈 전체를 모킹하면서, 테스트 코드의 실제 `libvirt` 상수와 `ComputeService`의 모킹된 `libvirt` 상수가 달라져 상태 매핑이 실패함.
  - **해결**: `patch('src.services.compute_service.libvirt')` 대신 `patch('src.services.compute_service.libvirt.open')`으로 변경하여, 연결만 모킹하고 상수 등은 실제 값을 사용하도록 수정.
- **문제**: `git commit` 명령어 실행 시 `syntax error near unexpected token` 발생.
  - **원인**: 커밋 메시지 내에 포함된 백틱(`) 문자가 셸에 의해 특수 문자로 해석됨.
  - **해결**: 백틱을 작은따옴표(')로 변경하여 셸 파싱 오류를 회피.

---

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


