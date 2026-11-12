# Spec Delta

## MODIFIED Requirements

### Requirement: Verified socket selection and host remapping
Enabled delegation SHALL select the first nonempty value among `OPENCODE_CONTAINER_PODMAN_SOCKET`, the Unix launch endpoint path, and `${XDG_RUNTIME_DIR:-/run/user/<uid>}/podman/podman.sock`. The socket MUST be absolute, physically resolved, accessible for read/write, and queried at that exact endpoint. The service MUST report rootless `true` and an absolute host socket pathname beyond slashes. A host socket reported as a `unix://` URL SHALL be reduced to its pathname before validation.

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
- **WHEN** the reported value is `unix://` followed by an empty, relative or slash-only pathname
- **THEN** the wrapper fails before image operations or startup
