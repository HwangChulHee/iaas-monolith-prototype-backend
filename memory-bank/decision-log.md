
## Architectural Weakness: Inefficient VM Listing (N+1 Problem)
- **Date:** 2025-10-04 11:55:51 AM
- **Author:** Unknown User
- **Context:** The `list_vms` function first queries the database to get a list of N VMs and then makes N separate calls to libvirt to fetch the real-time status for each VM.
- **Decision:** Refactor the `list_vms` function to fetch all VM statuses from libvirt in a single call (e.g., using `libvirt.listAllDomains()`). The result should then be combined with the VM data from the database in memory.
- **Alternatives Considered:** 
  - Caching libvirt status for a short period.
  - Accepting the performance degradation.
- **Consequences:** 
  - Significant performance degradation as the number of VMs grows.
  - Poor scalability and user experience for the primary list endpoint.
