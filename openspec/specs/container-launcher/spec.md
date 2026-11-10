# container-launcher Specification

## Purpose

Expose consistent wrapper controls while preserving OpenCode arguments and predictable, restricted per-user image creation.

## Requirements

### Requirement: Transparent arguments and wrapper help
The wrapper SHALL consume only `--container-build`, `--container-shell`, `--container-git-worktree`, `--container-qualify`, the internal `--container-qualify-probe` and `--container-help`, forwarding all other arguments unchanged and in order to OpenCode. Wrapper help MUST succeed without Podman, state creation, image operations, or service access; native OpenCode `--help` MUST remain an agent argument. Help SHALL describe the network modes and their limits.

#### Scenario: Side-effect-free help
- **WHEN** `--container-help` is requested with Podman absent or invalid runtime settings
- **THEN** wrapper usage and contracts are printed successfully without filesystem or engine side effects

#### Scenario: Normal argument forwarding
- **WHEN** OpenCode arguments contain spaces, empty strings, flags, or native `--help`
- **THEN** they reach OpenCode with their original boundaries and order after wrapper controls are removed

#### Scenario: Help describes the network contract
- **WHEN** `--container-help` is requested
- **THEN** the output names `OPENCODE_CONTAINER_NETWORK` with its three values, `OPENCODE_CONTAINER_MAINTENANCE`, `OPENCODE_CONTAINER_CONFIG_DIR`, the CA variables and `--container-qualify`
- **AND** it states the residual exfiltration limit of provider mode

### Requirement: Explicit image refresh and error handling
`--container-build` SHALL build or refresh the selected image before starting the selected session. Ordinary startup SHALL build only when image inspection returns missing-image status 1 and MUST stop on every other inspection error. Every build SHALL require exact `OPENCODE_CONTAINER_MAINTENANCE=1`, or stop before any build or pull. All modes except help MUST apply engine, delegation, restricted and state preflights before image operations.

#### Scenario: Unexpected inspection failure
- **WHEN** image inspection fails with an engine/storage status other than 1
- **THEN** no automatic build or container creation occurs and the failure is reported

#### Scenario: Missing image and explicit refresh
- **WHEN** the image is missing or `--container-build` is requested, with `OPENCODE_CONTAINER_MAINTENANCE=1`
- **THEN** a successful preflight is followed by a build from the wrapper's physical recipe directory and then the requested OpenCode or shell session
- **AND** build failure prevents session creation

#### Scenario: Build without maintenance authorization
- **WHEN** the image is missing or `--container-build` is requested and `OPENCODE_CONTAINER_MAINTENANCE` is unset or differs from exactly `1`
- **THEN** the wrapper exits nonzero naming the variable, without building, pulling or creating a container

### Requirement: Shell mode
`--container-shell` SHALL bypass the OpenCode entrypoint and start `/bin/bash` without OpenCode arguments. It MUST retain the same state, mount, identity, environment, delegation, lifecycle, and preflight contracts as a normal session.

#### Scenario: Shell with agent arguments
- **WHEN** shell mode is requested alongside arbitrary OpenCode arguments
- **THEN** Bash starts directly and those agent arguments are omitted

### Requirement: Explicit parent workspace exposure
`--container-git-worktree` SHALL mount the immediate parent of the original physical working directory read/write at the same absolute path while preserving that original directory as workdir. Ordinary sessions MUST expose only the current workspace. Wrapper help and documentation MUST describe the broader parent access.

#### Scenario: Worktree via symlink
- **WHEN** worktree mode is requested from a symlinked working directory
- **THEN** the physical directory's immediate parent is mounted and the session starts in the original physical directory
- **AND** workspace naming continues to use that original directory's basename

### Requirement: Common entry point with deprecated shim
The wrapper SHALL be `opencode-container.sh` at the repository root. `opencode-wrapper` SHALL remain as a deprecated shim: it prints one stderr warning naming the new script, then replaces itself with it, passing all arguments unchanged and preserving stdin, the exit status and signal handling. The shim SHALL work when invoked through a symlink or alias. Wrapper diagnostics SHALL use the `opencode-container:` prefix.

#### Scenario: Invocation through the old name
- **WHEN** the operator runs `opencode-wrapper run "hello world" --help`, directly or through a symlink
- **THEN** stderr contains one deprecation warning naming `opencode-container.sh`
- **AND** the session behaves exactly as if `opencode-container.sh run "hello world" --help` had been run, including its exit status

#### Scenario: Help through the new name
- **WHEN** the operator runs `opencode-container.sh --container-help`
- **THEN** help is printed without the deprecation warning and without engine queries or state creation

### Requirement: YOLO switch
`OPENCODE_CONTAINER_YOLO` SHALL enable the OpenCode permission bypass with the common boolean words: `1`, `true`, `yes` enable it and unset, empty, `0`, `false`, `no` disable it, case-insensitively. Any other value SHALL stop with status 1 naming the variable before engine queries or state creation. When enabled, the session SHALL receive `OPENCODE_PERMISSION={"*":"allow"}`. The switch SHALL NOT change mounts, environment forwarding, delegation or hardening.

#### Scenario: Bypass scope
- **WHEN** YOLO is enabled and the OpenCode configuration contains `ask` or `deny` rules
- **THEN** OpenCode auto-approves every permission request, including those rules, as the native bypass flags of the other wrappers do

#### Scenario: YOLO enabled
- **WHEN** `OPENCODE_CONTAINER_YOLO=TRUE` is set
- **THEN** the session's resolved OpenCode configuration has permission `{"*":"allow"}` as its last rule
- **AND** the mounts, forwarded names and delegation settings equal those of the same launch without YOLO

#### Scenario: YOLO disabled
- **WHEN** `OPENCODE_CONTAINER_YOLO` is unset, empty, `0`, `false` or `no`
- **THEN** the wrapper adds no permission setting, and configured OpenCode permissions apply unchanged

#### Scenario: Invalid value
- **WHEN** `OPENCODE_CONTAINER_YOLO=maybe` is set
- **THEN** the wrapper exits with status 1 naming the variable before any engine query

#### Scenario: Conflicting permission input
- **WHEN** YOLO is enabled and a nonempty `OPENCODE_PERMISSION` is set on the host
- **THEN** the wrapper exits with status 1 explaining that the two cannot be combined, before any engine query

### Requirement: Image name override
`OPENCODE_CONTAINER_IMAGE` SHALL select the image used for inspection, build and session creation. When it is unset or empty, the wrapper SHALL use `localhost/opencode-cli:latest`. A value containing whitespace or control characters SHALL stop with status 1 before engine queries.

#### Scenario: Default image
- **WHEN** `OPENCODE_CONTAINER_IMAGE` is unset
- **THEN** the wrapper inspects, builds when missing under maintenance authorization, and runs `localhost/opencode-cli:latest`, passing no user identity build arguments

#### Scenario: Custom image name
- **WHEN** `OPENCODE_CONTAINER_IMAGE=localhost/opencode-custom:test` is set, the image is missing and maintenance is authorized
- **THEN** the wrapper inspects, builds and runs exactly that name

### Requirement: Ignored version variables
When `OPENCODE_CONTAINER_VERSION` or `OPENCODE_VERSION` is set, the wrapper SHALL print one stderr warning that the variable is ignored and that the version is pinned in `Containerfile`, and SHALL continue with the selected image.

#### Scenario: Legacy version variable set
- **WHEN** `OPENCODE_VERSION=1.17.0` is set
- **THEN** stderr contains one warning naming the variable, the build passes no version argument, and the session starts normally
