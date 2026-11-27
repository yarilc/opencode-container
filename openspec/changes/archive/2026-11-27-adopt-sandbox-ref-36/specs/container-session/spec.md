# Spec Delta

## MODIFIED Requirements

### Requirement: Explicit network mode admission
Direct invocations of `opencode-container.sh` without a network mode SHALL apply OpenCode's provider default only when provider settings are present; otherwise they SHALL exit with status 1 and setup guidance before any engine call, state creation, or image operation. Options and environment variables other than `--container-help`, `--container-setup`, and `--container-toolchain` SHALL NOT bypass this gate.

#### Scenario: Existing invocation without a mode
- **WHEN** a user runs `opencode-container.sh` with no `OPENCODE_CONTAINER_NETWORK` and no provider settings, interactively or with redirected input
- **THEN** it exits with status 1 and the setup-required message before any engine call, without application output, state or runtime resources
- **AND** the message names `bash <wrapper> --container-setup` and states that an operator can set `OPENCODE_CONTAINER_NETWORK` explicitly

#### Scenario: Empty mode with provider settings
- **WHEN** `OPENCODE_CONTAINER_NETWORK` is empty and the provider settings select a protected installation
- **THEN** the launch runs in provider mode

#### Scenario: Help without a mode
- **WHEN** `--container-help` runs with no mode
- **THEN** help succeeds without engine calls or state side effects

#### Scenario: Options and other settings do not imply setup
- **WHEN** an unconfigured launch uses shell, build, worktree or YOLO, `OPENCODE_CONTAINER_MAINTENANCE=1`, or state, image, endpoint or policy settings
- **THEN** it receives the same setup-required refusal
- **AND** files in the current directory never admit the launch

### Requirement: Read-only engine queries are bounded
Every read-only engine query (`info`, `version`, `ps`, image and container existence and inspection) SHALL be bounded by a timeout. A response with a carriage return or extra records SHALL be refused. `create`, `start`, `build` and `pull` SHALL NOT be bounded.

#### Scenario: Stalled engine query
- **WHEN** a read-only engine query does not answer
- **THEN** the wrapper stops after the query timeout with the query's diagnostic and creates no container
