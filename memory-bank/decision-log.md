
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

## Makefile Test Workflow Structure
- **Date:** 2025-10-04 12:45:44 PM
- **Author:** Unknown User
- **Context:** The initial test command `PYTHONPATH=src python3 -m pytest ...` was too long and complex. A simpler, more conventional workflow was needed.
- **Decision:** Refactored the testing workflow into the Makefile with two main targets: `make test-all` for running all tests, and `make test file=<path>` for running specific tests. The `file` path automatically assumes the `tests/` prefix, improving usability.
- **Alternatives Considered:** 
  - Keeping the long command.
  - Using a simple `make test` target without options.
- **Consequences:** 
  - The development workflow for testing is now significantly simpler, more intuitive, and less error-prone.
