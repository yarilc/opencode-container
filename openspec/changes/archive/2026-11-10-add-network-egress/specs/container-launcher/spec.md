## MODIFIED Requirements

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

### Requirement: Image name override
`OPENCODE_CONTAINER_IMAGE` SHALL select the image used for inspection, build and session creation. When it is unset or empty, the wrapper SHALL use `localhost/opencode-cli:latest`. A value containing whitespace or control characters SHALL stop with status 1 before engine queries.

#### Scenario: Default image
- **WHEN** `OPENCODE_CONTAINER_IMAGE` is unset
- **THEN** the wrapper inspects, builds when missing under maintenance authorization, and runs `localhost/opencode-cli:latest`, passing no user identity build arguments

#### Scenario: Custom image name
- **WHEN** `OPENCODE_CONTAINER_IMAGE=localhost/opencode-custom:test` is set, the image is missing and maintenance is authorized
- **THEN** the wrapper inspects, builds and runs exactly that name
