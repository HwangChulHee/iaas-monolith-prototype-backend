### 🚀 다음 작업 제안: VM 생명주기 관리 완성

지금까지 VM의 생성(Create), 조회(Read), 삭제(Delete) 기능을 구현했습니다. 이제 VM의 핵심 생명주기를 완성하기 위해 **시작(Start), 중지(Shutdown), 재시작(Reboot)** 기능을 추가할 차례입니다.

다음과 같은 API들을 구현하는 것을 제안합니다.

-   `POST /v1/vms/{vm_name}/start`
-   `POST /v1/vms/{vm_name}/shutdown`
-   `POST /v1/vms/{vm_name}/reboot`

이를 위해 `ComputeService`에 `start_vm`, `shutdown_vm`, `reboot_vm` 메서드를 추가하고, 각각 libvirt의 `domain.create()`, `domain.shutdown()`, `domain.reboot()` 함수를 호출하도록 구현할 수 있습니다.