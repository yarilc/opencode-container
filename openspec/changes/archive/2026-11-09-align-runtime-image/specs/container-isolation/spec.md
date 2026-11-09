## ADDED Requirements

### Requirement: Sessions have explicit resource budgets
Every OpenCode and shell container SHALL be created with a memory limit, a CPU limit and a process limit. The defaults SHALL be 4 GiB memory, 2 CPUs and 512 processes. `OPENCODE_CONTAINER_MEMORY_LIMIT`, `OPENCODE_CONTAINER_CPU_LIMIT` and `OPENCODE_CONTAINER_PIDS_LIMIT` SHALL override them. Only an unset variable SHALL select its default; no value SHALL disable a budget.

#### Scenario: Accepted formats
- **WHEN** the operator sets a budget variable
- **THEN** memory accepts a positive integer with unit `k`, `m` or `g`, CPU accepts a positive decimal with at most three fractional digits up to 1024, and the process limit accepts an integer from 1 to 4194304

#### Scenario: Default budgets
- **WHEN** a session starts with none of the budget variables set
- **THEN** the container is created with 4 GiB memory, 2 CPUs and 512 processes

#### Scenario: Operator overrides budgets
- **WHEN** the operator sets `OPENCODE_CONTAINER_MEMORY_LIMIT=8g`, `OPENCODE_CONTAINER_CPU_LIMIT=1.5` and `OPENCODE_CONTAINER_PIDS_LIMIT=1024`
- **THEN** the container is created with exactly those limits

#### Scenario: Invalid or unbounded budget value
- **WHEN** a budget variable is set but empty or whitespace, zero, negative, `-1`, `max`, non-numeric, out of range, or has an unsupported unit
- **THEN** the wrapper exits with status 1 and names the variable before any engine query, state creation or image operation

### Requirement: Resource budgets are verified, not assumed
Before starting the application, each launch SHALL inspect the created container and require its configured memory, CPU and process limits to equal the selected budgets. A mismatch or missing limit SHALL stop startup with an actionable diagnostic, without a retry using weaker limits. Runtime verification SHALL measure the effective cgroup v2 limits inside the session.

#### Scenario: Engine ignores a budget
- **WHEN** the created container reports no limit or a different limit for memory, CPU or processes
- **THEN** the wrapper removes only its own container and exits non-zero before the application starts
- **AND** the diagnostic names rootless cgroup v2 controller delegation

#### Scenario: Effective limits are measured
- **WHEN** the real-engine runtime checks run a session with default and overridden budgets
- **THEN** the container's cgroup v2 `memory.max`, `pids.max` and `cpu.max` match the selected budgets
- **AND** a process count beyond the process limit fails inside the session

### Requirement: Isolated persistent state option
`OPENCODE_CONTAINER_STATE_DIR` SHALL select a private host directory mounted read/write as the persistent `/opencode-home`, replacing the shared host XDG state for that session. The wrapper SHALL create and validate it with the same rules as the shared state before any engine query, without repairing permissions or importing credentials. It SHALL NOT overlap the workspace mount.

#### Scenario: Isolated state selected
- **WHEN** `OPENCODE_CONTAINER_STATE_DIR` names a missing absolute directory
- **THEN** the directory and its `.config/opencode`, `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode` subdirectories are created privately and the directory is mounted at `/opencode-home`
- **AND** the host XDG OpenCode directories are not mounted

#### Scenario: Insecure or overlapping state directory
- **WHEN** the selected directory is relative or empty, belongs to another user, has group or other permissions, or equals, contains or lies inside the workspace mount
- **THEN** the wrapper exits with status 1 naming the variable and path, before any engine query, and changes nothing

#### Scenario: State persists
- **WHEN** a file is written below `/opencode-home` in one session with the same state directory
- **THEN** the next session with that directory sees it

### Requirement: Hardening controls are documented
Wrapper help and the README SHALL document the budget variables with defaults and accepted formats, the lifetime variable, the state directory option, the unsafe-workspace override with the refused directories, and that capabilities are dropped in every mode. They SHALL state that budgets and tmpfs sizes do not bound workspace or state storage growth. Help SHALL remain free of engine queries and state creation.

#### Scenario: Operator reads wrapper help
- **WHEN** the operator runs `--container-help`
- **THEN** the output lists `OPENCODE_CONTAINER_MEMORY_LIMIT`, `OPENCODE_CONTAINER_CPU_LIMIT`, `OPENCODE_CONTAINER_PIDS_LIMIT`, `OPENCODE_CONTAINER_RUN_TIMEOUT`, `OPENCODE_CONTAINER_STATE_DIR` and `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE` with their defaults
- **AND** it states that capabilities are dropped and budgets do not limit persistent storage
- **AND** no engine query or state creation occurs

## MODIFIED Requirements

### Requirement: Consistent effective HOME and XDG layout
Sessions SHALL use `HOME=/opencode-home` with the four XDG bases below it. Without `OPENCODE_CONTAINER_STATE_DIR`, `/opencode-home` SHALL be an ephemeral tmpfs, and the caller's validated host OpenCode XDG directories SHALL be mounted at fixed paths below it. Other host HOME content MUST NOT become writable or be mounted implicitly.

#### Scenario: Default layout with host state
- **WHEN** a session starts without `OPENCODE_CONTAINER_STATE_DIR`
- **THEN** `HOME` is `/opencode-home`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` are `/opencode-home/.config`, `/opencode-home/.local/share`, `/opencode-home/.cache` and `/opencode-home/.local/state`
- **AND** the caller's host XDG OpenCode directories are mounted read/write at the `opencode` subdirectory of each base
- **AND** files written elsewhere below `/opencode-home` do not survive the session

#### Scenario: Nonstandard HOME and symlinked XDG base
- **WHEN** the host HOME is nonstandard and a host XDG base resolves through a symlink
- **THEN** the physical validated OpenCode directories are mounted at the fixed destinations under `/opencode-home`

### Requirement: Optional integrations require exact opt-in
`$HOME/.agents` SHALL be mounted read-only at `/opencode-home/.agents` only when `OPENCODE_CONTAINER_AGENTS_DIR` is exactly `1`. `/etc/opencode` SHALL be mounted read-only at `/etc/opencode` only when `OPENCODE_CONTAINER_SYSTEM_CONFIG` is exactly `1`. Any other value, including empty, `true` or `yes`, SHALL leave the directory unmounted. An opt-in whose directory does not exist SHALL stop with status 1 and name the variable and the path, before any engine query or state creation.

#### Scenario: Integration directories exist without opt-in
- **WHEN** `$HOME/.agents` and `/etc/opencode` exist and neither variable is set
- **THEN** neither directory is mounted

#### Scenario: Exact opt-in
- **WHEN** `OPENCODE_CONTAINER_AGENTS_DIR=1` and `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` are set and both directories exist
- **THEN** both are mounted read-only from their physical sources, at `/opencode-home/.agents` and `/etc/opencode`
- **AND** a write attempt inside the session fails

#### Scenario: Non-exact opt-in value
- **WHEN** either variable is set to a value other than `1`
- **THEN** the corresponding directory is not mounted and startup continues

#### Scenario: Opt-in for a missing directory
- **WHEN** `OPENCODE_CONTAINER_AGENTS_DIR=1` is set and `$HOME/.agents` does not exist
- **THEN** the wrapper exits with status 1 naming the variable and the path
- **AND** no engine query, state directory or image operation occurs

### Requirement: Preserve sandbox identity and hardening
Sessions SHALL run with `--userns=keep-id --user <uid>:<gid>` set at launch, so that processes have the caller's numeric identity without an identity baked into the image. Every OpenCode and shell session SHALL drop all capabilities and enable no-new-privileges, with or without delegation and YOLO. The wrapper SHALL NOT add a capability back to resolve an incompatibility.

#### Scenario: Session identity
- **WHEN** a session starts from the generic image
- **THEN** `id -u` and `id -g` report the caller's numeric identity, files created in the workspace belong to the caller, and the effective capability set is empty with `NoNewPrivs: 1`
