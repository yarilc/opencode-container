## ADDED Requirements

### Requirement: Common entry point
The wrapper SHALL be `opencode-container.sh` at the repository root, and wrapper diagnostics SHALL use the `opencode-container:` prefix. There SHALL be no other entry point: the earlier `opencode-wrapper` shim is removed, and the earlier `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION` variables SHALL have no effect and produce no notice.

#### Scenario: Earlier names
- **WHEN** `OPENCODE_VERSION=1.17.0` or `OPENCODE_CONTAINER_VERSION=1.17.0` is set
- **THEN** the launch behaves as if the variable were unset, with no notice, and the build passes no version argument

#### Scenario: Help through the entry point
- **WHEN** the operator runs `opencode-container.sh --container-help`
- **THEN** help is printed without engine queries or state creation

## REMOVED Requirements

### Requirement: Common entry point with deprecated shim
**Reason**: The project has no release, so the shared core removes legacy names without compatibility hooks (launcher contract U2).
**Migration**: Run `opencode-container.sh`; see "Common entry point".

### Requirement: Ignored version variables
**Reason**: The version-variable notices are legacy names removed with the shim (U2); the core prints no notice for them.
**Migration**: None; the OpenCode version stays pinned in `Containerfile`.

## MODIFIED Requirements

### Requirement: Transparent arguments and wrapper help
The wrapper SHALL consume only `--container-build`, `--container-shell`, `--container-git-worktree`, `--container-qualify`, the internal `--container-qualify-probe` and `--container-help`, forwarding all other arguments unchanged and in order to OpenCode. Wrapper help MUST succeed without Podman, state creation, image operations, or service access, and SHALL use the layout of the shared launcher core followed by OpenCode's agent part; native OpenCode `--help` MUST remain an agent argument. Help SHALL describe the network modes and their limits.

#### Scenario: Side-effect-free help
- **WHEN** `--container-help` is requested with Podman absent or invalid runtime settings
- **THEN** wrapper usage and contracts are printed successfully without filesystem or engine side effects
- **AND** it lists every common `OPENCODE_CONTAINER_*` variable with its default, and then OpenCode's own variables

#### Scenario: Normal argument forwarding
- **WHEN** OpenCode arguments contain spaces, empty strings, flags, or native `--help`
- **THEN** they reach OpenCode with their original boundaries and order after wrapper controls are removed

#### Scenario: Help describes the network contract
- **WHEN** `--container-help` is requested
- **THEN** the output names `OPENCODE_CONTAINER_NETWORK` with its three values and the provider default, `OPENCODE_CONTAINER_MAINTENANCE`, `OPENCODE_CONTAINER_CONFIG_DIR`, the CA variables and `--container-qualify`
- **AND** it states the residual exfiltration limit of provider mode with each base profile's hosts

### Requirement: Explicit image refresh and error handling
`--container-build` with OpenCode arguments SHALL rebuild the selected image, using the layer cache, before starting the selected session. Without OpenCode arguments (`--container-shell` and `--container-git-worktree` do not count) it SHALL validate every launch setting, build the image and exit without creating a container. Ordinary startup SHALL build only when image inspection returns missing-image status 1 and MUST stop on every other inspection error. Every image SHALL carry a `build-inputs-hash` label over its build inputs; ordinary startup SHALL refuse an image whose label differs, naming the rebuild command. Every build SHALL require exact `OPENCODE_CONTAINER_MAINTENANCE=1`, or stop before any build or pull, and SHALL pull the exact base first, then run with `--pull=never` and the docker format, without a timeout. All modes except help MUST apply engine, delegation, restricted and state preflights before image operations.

#### Scenario: Unexpected inspection failure
- **WHEN** image inspection fails with an engine/storage status other than 1
- **THEN** no automatic build or container creation occurs and the failure is reported

#### Scenario: Missing image and explicit refresh
- **WHEN** the image is missing, or `--container-build` is requested with OpenCode arguments, with `OPENCODE_CONTAINER_MAINTENANCE=1`
- **THEN** a successful preflight is followed by a build from the wrapper's physical recipe directory and then the requested OpenCode or shell session
- **AND** build failure prevents session creation

#### Scenario: Build without maintenance authorization
- **WHEN** the image is missing or `--container-build` is requested and `OPENCODE_CONTAINER_MAINTENANCE` is unset or differs from exactly `1`
- **THEN** the wrapper exits nonzero naming the variable, without building, pulling or creating a container

#### Scenario: Build-only refresh
- **WHEN** `OPENCODE_CONTAINER_NETWORK=unrestricted OPENCODE_CONTAINER_MAINTENANCE=1 OPENCODE_CONTAINER_IMAGE=localhost/opencode-cli:setup-x opencode-container.sh --container-build` runs
- **THEN** the image is built with a matching `build-inputs-hash` label and the wrapper exits 0 without creating a container
- **AND** an invalid budget or a relative `OPENCODE_CONTAINER_STATE_DIR` fails before any image operation, naming the setting

#### Scenario: Stale image
- **WHEN** the image exists without a `build-inputs-hash` label, or with one that differs from the current inputs
- **THEN** ordinary startup stops before container creation, naming `--container-build` and `OPENCODE_CONTAINER_MAINTENANCE=1`

### Requirement: Shell mode
`--container-shell` SHALL bypass the OpenCode entrypoint and start `/bin/bash` with the remaining arguments in every network mode, without the approval bypass. It MUST retain the same state, mount, identity, environment, delegation, lifecycle, and preflight contracts as a normal session.

#### Scenario: Shell with agent arguments
- **WHEN** shell mode is requested with `-c "echo ok"`
- **THEN** Bash starts directly, runs `-c` and `echo ok` as two arguments and prints `ok`
- **AND** with `OPENCODE_CONTAINER_YOLO=1` the shell session has no `OPENCODE_PERMISSION={"*":"allow"}`

### Requirement: YOLO switch
`OPENCODE_CONTAINER_YOLO` SHALL enable the OpenCode permission bypass with the common boolean words: `1`, `true`, `yes` enable it and unset, empty, `0`, `false`, `no` disable it, case-insensitively. Any other value SHALL stop with status 1 naming the variable before engine queries or state creation. When enabled, an OpenCode session SHALL receive `OPENCODE_PERMISSION={"*":"allow"}`; shell mode and the qualification probe SHALL ignore it. The switch SHALL NOT change mounts, environment forwarding, delegation or hardening.

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
- **WHEN** YOLO is enabled for an OpenCode session and a nonempty `OPENCODE_PERMISSION` is set on the host
- **THEN** the wrapper exits with status 1 explaining that the two cannot be combined, before any engine query
