# Changelog

All notable changes to `cloudmesh-ai-commander` will be documented in this file.

## [0.1.0] - 2026-05-07

### Added
- **Commander Orchestration**: Automated vLLM and mock server deployment on UVA.
- **Tunnel Management**: Integrated `Tunnel` utility for managed SSH port-forwarding.
- **Configuration System**: Added `config.yaml` for model and deployment parameterization.
- **Process Cleanup**: Added `stop` command to terminate tunnels and release ports.
- **Security**: Automated credential synchronization and directory permission hardening.

### Fixed
- **Tunnel Leaks**: Implemented `lsof` fallback to ensure orphaned SSH processes are terminated.
