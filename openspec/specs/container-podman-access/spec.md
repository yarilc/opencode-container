# container-podman-access Specification

## Purpose

Control which Podman engines can launch OpenCode and when the session receives delegated authority over a host engine.

## Requirements

### Requirement: Verified launch engine
The wrapper SHALL require a Linux rootless Podman launch engine before image inspection, building, or container creation. It MUST reject named connections, TCP/SSH endpoints, implicit remote services, and Unix endpoints without an absolute pathname beyond slash characters.

#### Scenario: Explicit same-host Unix launch
- **WHEN** an explicit same-host absolute Unix endpoint reports rootless `true`, OS `linux`, and ServiceIsRemote `true` or `false`
- **THEN** launch validation succeeds independently of session delegation

#### Scenario: Invalid context or engine
- **WHEN** a named connection, TCP/SSH endpoint, slash-only Unix endpoint, rootful engine, non-Linux engine, invalid remote boolean, or remote engine without explicit Unix endpoint is selected
- **THEN** startup fails before image operations or container creation

### Requirement: Complete verification responses
The wrapper MUST retain query failure status and complete output including trailing records. It SHALL accept only the required fields and records, with at most one final LF, rejecting CR characters, missing fields, invalid booleans, and extra blank or nonblank records.

#### Scenario: Launch response validation
- **WHEN** the launch query fails or returns anything other than one complete rootless/OS/remote record
- **THEN** no image operation or container creation occurs

#### Scenario: Delegation response validation
- **WHEN** enabled delegation returns incomplete data, invalid rootless status, a relative host path, CR, or additional records
- **THEN** startup fails before image operations even if its first record appears valid

### Requirement: Exact explicit delegation
The wrapper SHALL expose the Podman service only when `OPENCODE_CONTAINER_PODMAN` equals exactly `1`. All other values SHALL disable delegation, omit the socket mount, and explicitly unset session `CONTAINER_HOST`, including image defaults. Enabled but unverifiable delegation MUST stop startup before image operations. The wrapper MUST never start or enable the service.

#### Scenario: Disabled values
- **WHEN** the switch is unset, empty, `0`, `true`, `yes`, `01`, invalid text, or whitespace-padded `1`
- **THEN** no delegation query or socket mount occurs and session `CONTAINER_HOST` is absent
- **AND** a valid Unix launch connection can still be used by the wrapper

#### Scenario: Unavailable opted-in service
- **WHEN** the switch equals `1` but the selected socket cannot be verified
- **THEN** startup fails with actionable service/access diagnostics and no automatic fallback or service activation

### Requirement: Verified socket selection and host remapping
Enabled delegation SHALL select the first nonempty value among `OPENCODE_CONTAINER_PODMAN_SOCKET`, the Unix launch endpoint path, and `${XDG_RUNTIME_DIR:-/run/user/<uid>}/podman/podman.sock`. The socket MUST be absolute, physically resolved, accessible for read/write, and queried at that exact endpoint. The service MUST report rootless `true` and an absolute host socket pathname. A host socket reported as a `unix://` URL SHALL be reduced to its pathname before validation. The reported pathname SHALL NOT consist only of slash characters. When it exists in the wrapper's own filesystem namespace, it SHALL be a Unix socket; a pathname the wrapper cannot see is accepted as the remapped socket of a containerized wrapper, whose answer stays trusted. Delegated sessions SHALL get private tmpfs mounts at `/var/lib/containers` and `/run/containers`.

#### Scenario: Remapped caller socket
- **WHEN** the selected accessible socket reports a different absolute host source containing spaces or commas
- **THEN** the reported source is mounted at `/run/podman/podman.sock` and the session receives `CONTAINER_HOST=unix:///run/podman/podman.sock`
- **AND** the launch connection remains unchanged

#### Scenario: Override precedence
- **WHEN** a nonempty explicit socket override and a Unix launch endpoint are both configured
- **THEN** only the override is used for delegation verification
- **AND** a relative or inaccessible override fails rather than falling through to defaults

#### Scenario: Podman 5 reports a socket URL
- **WHEN** the selected service reports its host socket as `unix:///run/user/1000/podman/podman.sock`
- **THEN** the wrapper mounts `/run/user/1000/podman/podman.sock` at `/run/podman/podman.sock`

#### Scenario: Invalid socket URL
- **WHEN** the reported value is `unix://` followed by an empty, relative or slash-only pathname, or a bare slash-only pathname such as `/`
- **THEN** the wrapper fails before image operations or startup, and the host root is never mounted

#### Scenario: Host socket path is not a socket
- **WHEN** the service reports a host socket path that exists in the wrapper's namespace as a directory, a regular file, a dangling link or another non-socket
- **THEN** the wrapper fails before image operations naming the reported path, and nothing is mounted from it

#### Scenario: Nested Podman storage
- **WHEN** a delegated session starts
- **THEN** `/var/lib/containers` and `/run/containers` are private tmpfs mounts, absent from sessions without delegation

### Requirement: Preserve host security policy
Delegation MUST NOT add SELinux label disabling, automatic relabeling, privilege escalation, or extra capabilities. Existing capability dropping, no-new-privileges, read-only root, keep-id identity, and process limits SHALL remain enforced.

#### Scenario: Host policy denies socket access
- **WHEN** enabled delegation is denied by host permissions or SELinux policy
- **THEN** the failure is reported with explicit host-policy remediation guidance
- **AND** the wrapper does not weaken policy or retry with relaxed confinement

### Requirement: Delegation only in unrestricted mode
`OPENCODE_CONTAINER_PODMAN=1` SHALL be accepted only with explicit `OPENCODE_CONTAINER_NETWORK=unrestricted`. In offline and provider modes it SHALL fail before image or resource operations, explaining that the host API bypasses egress enforcement. Shell, YOLO and native permission settings SHALL NOT change this.

#### Scenario: Delegation requested in a restricted mode
- **WHEN** the wrapper starts in offline or provider mode with `OPENCODE_CONTAINER_PODMAN=1`, in OpenCode or shell mode, with or without YOLO
- **THEN** it exits nonzero before image or resource operations and names explicit unrestricted mode as the only mode with delegation

#### Scenario: Delegation in unrestricted mode
- **WHEN** the wrapper starts in unrestricted mode with `OPENCODE_CONTAINER_PODMAN=1`
- **THEN** delegation behaves as before this change
