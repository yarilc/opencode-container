# Spec Delta

## ADDED Requirements

### Requirement: Verified launch engine
The wrapper SHALL require a Linux rootless Podman launch engine before image inspection, building, or container creation. It MUST reject named connections, TCP/SSH endpoints, implicit remote services, and Unix endpoints without an absolute pathname beyond slash characters.

#### Scenario: Explicit same-host Unix launch
- **WHEN** an explicit same-host absolute Unix endpoint reports rootless `true`, OS `linux`, and ServiceIsRemote `true` or `false`
- **THEN** launch validation succeeds

#### Scenario: Invalid context or engine
- **WHEN** a named connection, TCP/SSH endpoint, slash-only Unix endpoint, rootful engine, non-Linux engine, invalid remote boolean, or remote engine without explicit Unix endpoint is selected
- **THEN** startup fails before image operations or container creation

### Requirement: Complete launch verification responses
The wrapper MUST retain query failure status and complete output including trailing records. It SHALL accept only the required fields and records, with at most one final LF, rejecting CR characters, missing fields, invalid booleans, and extra blank or nonblank records.

#### Scenario: Launch response validation
- **WHEN** the launch query fails or returns anything other than one complete rootless/OS/remote record
- **THEN** no image operation or container creation occurs

### Requirement: Leftover delegation opt-in is refused
Exact `OPENCODE_CONTAINER_PODMAN=1` SHALL stop every session launch and build-only operation before engine queries or image operations, stating that host Podman delegation was removed and pointing to image toolchains (`--container-toolchain add`). Any other value of `OPENCODE_CONTAINER_PODMAN`, and any value of `OPENCODE_CONTAINER_PODMAN_SOCKET`, SHALL be ignored.

#### Scenario: Leftover delegation opt-in in any mode
- **WHEN** an operator invokes `opencode-container.sh` with `OPENCODE_CONTAINER_PODMAN=1` in offline, provider, or unrestricted mode, or with `--container-build`
- **THEN** the launch exits nonzero before any engine call and states that host Podman delegation was removed in favor of image toolchains

#### Scenario: Non-enabling delegation values ignored
- **WHEN** `OPENCODE_CONTAINER_PODMAN` is unset, empty, `0`, `false`, or `true`, or `OPENCODE_CONTAINER_PODMAN_SOCKET` is set
- **THEN** the launcher ignores those variables and mounts no host Podman socket
