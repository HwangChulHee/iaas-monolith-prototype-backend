# 개발 로그

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

### 아키텍처 비판: AWS와 오픈스택 관점

네 VM 생성 로직은 이제 Nova-API/EC2 API의 최소 요건을 갖췄어. 하지만 다음 단계에서 아키텍처적 허점이 드러날 수 있다.

-   **🚨 리스크 1: 디스크 롤백 부재**
    -   **현황**: ComputeService.create_vm에서 VM 생성 중 Libvirt 오류가 나거나 DB 저장 실패가 발생했을 때, 생성된 디스크 복제본이나 DB 레코드를 자동으로 삭제(롤백)하는 로직이 없어.
    -   **AWS/OpenStack**: 모든 클라우드 작업은 트랜잭션처럼 처리돼. 중간에 실패하면 원 상태로 되돌리는 롤백 메커니즘이 필수야.
    -   **난관**: 네 destroy_vm 로직을 create_vm의 except 블록 안에서 재사용하는 방식으로 롤백 기능을 구현해야 해. 난이도가 좀 있지만, MSA 전환 시 안정성을 높이는 기반이 돼.
-   **🚨 리스크 2: 비동기 처리의 필요성 (Phase 2 준비)**
    -   **현황**: POST /v1/vms 요청은 VM이 완전히 running 상태가 될 때까지 HTTP 연결을 잡고 기다려.
    -   **AWS/OpenStack**: VM 생성은 시간이 오래 걸리는 작업이므로, API 서버는 요청을 받자마자 202 Accepted를 반환하고, 실제 VM 생성은 **메시지 큐(RabbitMQ)**로 넘겨서 Nova Compute 워커가 비동기적으로 처리해.
    -   **난관**: 네 로드맵의 Phase 2가 바로 이 RabbitMQ/Celery 도입이야. 지금은 모놀리식이지만, 다음 VM 제어 기능을 만들 때부터 비동기 처리를 염두에 두고 코드를 짜는 습관을 들여야 해.