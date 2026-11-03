# wrapper-interface Specification

## Purpose

Expose consistent wrapper controls while preserving OpenCode arguments and predictable, restricted per-user image creation.

## Requirements

### Requirement: Transparent arguments and wrapper help
The wrapper SHALL consume only `--container-build`, `--container-shell`, `--container-git-worktree`, and `--container-help`, forwarding all other arguments unchanged and in order to OpenCode. Wrapper help MUST succeed without Podman, state creation, image operations, or service access; native OpenCode `--help` MUST remain an agent argument.

#### Scenario: Side-effect-free help
- **WHEN** `--container-help` is requested with Podman absent or invalid runtime settings
- **THEN** wrapper usage and contracts are printed successfully without filesystem or engine side effects

#### Scenario: Normal argument forwarding
- **WHEN** OpenCode arguments contain spaces, empty strings, flags, or native `--help`
- **THEN** they reach OpenCode with their original boundaries and order after wrapper controls are removed

### Requirement: Explicit image refresh and error handling
`--container-build` SHALL build or refresh the per-user image before starting the selected session. Ordinary startup SHALL build only when image inspection returns missing-image status 1 and MUST stop on every other inspection error. All modes except help MUST apply engine, enabled delegation, and state preflights before image operations.

#### Scenario: Unexpected inspection failure
- **WHEN** image inspection fails with an engine/storage status other than 1
- **THEN** no automatic build or container creation occurs and the failure is reported

#### Scenario: Missing image and explicit refresh
- **WHEN** the image is missing or `--container-build` is requested
- **THEN** a successful preflight is followed by a build from the wrapper's physical recipe directory and then the requested OpenCode or shell session
- **AND** build failure prevents session creation

### Requirement: Per-user versioned image identity
Image tags SHALL retain OpenCode version, username, UID, and GID. The default version MUST remain `1.18.3`, with the existing `OPENCODE_VERSION` override preserved. The image MUST provide the host user's username and numeric identity.

#### Scenario: Default and overridden versions
- **WHEN** the version is unset or explicitly overridden
- **THEN** the selected tag and build arguments use the corresponding version and host username/UID/GID without changing the default

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

### Requirement: Default-deny build context
The effective Podman build context MUST allow only the root `Dockerfile`, root `opencode-entrypoint`, and chosen root ignore file. Unknown files, nested lookalikes, repository metadata, local state, and credentials MUST be excluded while the required COPY input remains available.

#### Scenario: Probe context contents
- **WHEN** a disposable build context includes the required entrypoint plus unknown root files, nested recipe/helper names, and synthetic credentials
- **THEN** the entrypoint COPY succeeds and attempts to consume any unlisted input fail
