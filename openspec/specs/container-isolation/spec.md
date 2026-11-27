# container-isolation Specification

## Purpose

Define the persistent and ephemeral filesystem boundaries and environment inputs available to an OpenCode sandbox session.

## Requirements

### Requirement: Private persistent state preflight
Before image operations the wrapper SHALL privately create missing OpenCode config/data/cache/state directories at their fixed host paths, physically resolve each, and verify caller ownership, read/write/traverse access, and no group/other permission bits. It MUST reject insecure existing paths without chmod/chown or credential copying. Creation MUST NOT change the caller's umask.

#### Scenario: Missing directories
- **WHEN** one or more writable OpenCode XDG directories do not exist
- **THEN** they are created with private permissions under a scoped creation umask and validated before image inspection or building

#### Scenario: Existing state fails validation
- **WHEN** a resolved directory is inaccessible, belongs to another user, has group/other permissions, is a broken symlink, or is not a directory
- **THEN** startup stops before image operations with a path-specific diagnostic
- **AND** existing permissions, ownership, and credentials remain unchanged

### Requirement: Consistent effective HOME and XDG layout
Sessions SHALL use `HOME=/opencode-home` with the four XDG bases below it. Without `OPENCODE_CONTAINER_STATE_DIR`, `/opencode-home` SHALL be an ephemeral tmpfs, and the caller's validated OpenCode directories at fixed paths below the host home SHALL be mounted at fixed paths below it; host `XDG_*_HOME` variables SHALL NOT relocate them. Other host HOME content MUST NOT become writable or be mounted implicitly.

#### Scenario: Default layout with host state
- **WHEN** a session starts without `OPENCODE_CONTAINER_STATE_DIR`
- **THEN** `HOME` is `/opencode-home`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` are `/opencode-home/.config`, `/opencode-home/.local/share`, `/opencode-home/.cache` and `/opencode-home/.local/state`
- **AND** the caller's fixed host OpenCode directories are mounted read/write at the `opencode` subdirectory of each base
- **AND** files written elsewhere below `/opencode-home` do not survive the session

#### Scenario: Nonstandard HOME and symlinked XDG base
- **WHEN** the host HOME is nonstandard and a fixed host OpenCode directory resolves through a symlink
- **THEN** the physical validated OpenCode directories are mounted at the fixed destinations under `/opencode-home`

#### Scenario: Host XDG variables are set
- **WHEN** the host sets `XDG_CONFIG_HOME=/srv/config` and `XDG_DATA_HOME=/srv/data`
- **THEN** the session still mounts `~/.config/opencode`, `~/.local/share/opencode`, `~/.cache/opencode` and `~/.local/state/opencode` below the caller's home, and nothing below `/srv` is created or mounted

#### Scenario: Configuration directory override
- **WHEN** `OPENCODE_CONTAINER_CONFIG_DIR` names a private absolute directory
- **THEN** that directory is validated like the other state and mounted at `/opencode-home/.config/opencode`, while the data, cache and state directories keep their fixed paths
- **AND** a relative value fails before engine queries, naming the variable

#### Scenario: Session names the effective configuration directory
- **WHEN** any session starts, with or without a host `OPENCODE_CONTAINER_CONFIG_DIR`
- **THEN** the session has `OPENCODE_CONTAINER_CONFIG_DIR=/opencode-home/.config/opencode` and the host value is not forwarded

### Requirement: Physical bind paths and integration boundaries
The wrapper SHALL preserve physical absolute workspace and state bind sources, support spaces and commas without argument splitting, and start in the original physical working directory. Only the workspace, four OpenCode state directories, and explicitly enabled service socket SHALL be host-writable. Opted-in `.agents` and `/etc/opencode` mounts MUST be read-only.

#### Scenario: Paths contain delimiters
- **WHEN** workspace, XDG, opted-in integration, or reported socket paths contain spaces or commas
- **THEN** the intended complete paths are mounted with the specified access mode

#### Scenario: Optional integrations
- **WHEN** integration directories are opted in and exist
- **THEN** they are mounted read-only at their intended destinations
- **AND** the host home, `.claude`, SSH/AWS/Docker directories, global Git configuration, and Podman configuration are not implicitly mounted

### Requirement: Explicit ephemeral storage
The root filesystem SHALL remain read-only. Automatic read-only tmpfs provisioning SHALL add no writable path beyond the explicit temporary and device mounts. `/tmp`, `/var/tmp`, `/run` and, in shared-state mode, the home MUST have explicit ephemeral tmpfs mounts with capacity limits and nosuid/nodev. `/tmp`, `/var/tmp` and the home SHALL have mode 1777; `/run` SHALL NOT be writable by the session user. `/tmp` and the home MUST remain executable for OpenTUI, because the profile declares executable temporary storage.

#### Scenario: Effective mount flags
- **WHEN** a real session inspects its mounts
- **THEN** `/tmp` is executable, nosuid/nodev, mode 1777, and limited to 512 MiB
- **AND** `/var/tmp` is noexec, nosuid/nodev, mode 1777, and limited to 512 MiB
- **AND** `/run` is noexec, nosuid/nodev, limited to 32 MiB and not writable by the session user
- **AND** in shared-state mode `/opencode-home` is executable, nosuid/nodev, mode 1777, and limited to 512 MiB

#### Scenario: Temporary lifetime and renderer startup
- **WHEN** files are written to temporary mounts and the session ends
- **THEN** a subsequent session does not retain those files
- **AND** interactive OpenTUI startup can extract and load its shared library from `/tmp`

### Requirement: Explicit environment allowlist without credential arguments
The wrapper MUST forward only nonempty inherited values of `TERM`, `COLORTERM`, `LANG`, `LC_ALL`, in unrestricted mode the proxy variables (`ALL_PROXY` included), the OpenCode native variables, the credential the mode allows and `OPENCODE_CONTAINER_ENV_VARS`. Values MUST be forwarded by name and kept out of engine-client arguments. Every session SHALL set `USER` to the caller's name and `EDITOR` and `VISUAL` to `nano`; other nonsecret identity/path assignments SHALL remain explicit. Forwarded and image-default settings MUST NOT override disabled delegation. Offline and provider modes SHALL forward no inherited proxy or CA variable.

#### Scenario: Credential forwarding
- **WHEN** a key of the selected provider, `OPENCODE_SERVER_PASSWORD`, a key of another provider and an unlisted variable are set
- **THEN** the selected key and the password reach the session through `--env VARIABLE` and are absent from wrapper-generated Podman arguments
- **AND** the other provider's key and the unlisted value are not forwarded
- **AND** documentation states that container processes and engine inspection can still observe forwarded credentials

#### Scenario: Host proxy settings in a restricted mode
- **WHEN** the host sets `HTTPS_PROXY`, `no_proxy` and `NODE_EXTRA_CA_CERTS`, and the mode is offline or provider
- **THEN** none of these host values reaches the session, and provider sessions see only the relay values and `NO_PROXY=localhost,127.0.0.1,::1`
- **AND** in unrestricted mode `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` and their lowercase forms are forwarded by name

#### Scenario: Fixed identity and editor
- **WHEN** the host sets `EDITOR=vim` and `VISUAL=code`
- **THEN** the session has `USER` with the caller's name, `EDITOR=nano` and `VISUAL=nano`

### Requirement: Preserve sandbox identity and hardening
Sessions SHALL run with `--userns=keep-id --user <uid>:<gid>` set at launch, so that processes have the caller's numeric identity without an identity baked into the image. Every OpenCode and shell session container SHALL drop all capabilities and enable no-new-privileges, with or without YOLO and with or without a session container engine. The wrapper SHALL NOT add a capability back to resolve an incompatibility.

#### Scenario: Session identity
- **WHEN** a session starts from the generic image
- **THEN** `id -u` and `id -g` report the caller's numeric identity, files created in the workspace belong to the caller, and the effective capability set is empty with `NoNewPrivs: 1`

### Requirement: Other agents' state is never mounted
The wrapper SHALL NOT mount `~/.claude`, or any path below it, into an OpenCode session. No setting SHALL change this.

#### Scenario: Claude Code state exists on the host
- **WHEN** `$HOME/.claude` exists, with or without credential files, and a session starts
- **THEN** the generated engine arguments contain no mount whose source or destination is `$HOME/.claude` or a path below it
- **AND** inside the session `$HOME/.claude` does not exist

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

### Requirement: Provider credentials follow the selected provider
`OPENCODE_CONTAINER_PROVIDER` SHALL select the single provider profile whose variables an unrestricted session forwards; accepted values are `anthropic`, `openai`, `google`, `openrouter`, `amazon-bedrock`, `azure`, `opencode` and `none`, the default when unset. Other profiles' variables, `GH_TOKEN` and `GITHUB_TOKEN` SHALL NOT be forwarded unless listed explicitly. Offline mode SHALL forward no provider variable; provider mode SHALL forward only the network profile's credential, and `OPENCODE_CONTAINER_ENV_VARS` SHALL NOT forward another policy profile's credential there.

#### Scenario: Profile variable sets
- **WHEN** a provider value is selected
- **THEN** the nonempty variables of exactly its set are forwarded by name:
  - `anthropic`: `ANTHROPIC_API_KEY`
  - `openai`: `OPENAI_API_KEY`, `OPENAI_BASE_URL`
  - `google`: `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `GEMINI_API_KEY`
  - `openrouter`: `OPENROUTER_API_KEY`
  - `amazon-bedrock`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, `AWS_BEARER_TOKEN_BEDROCK`
  - `azure`: `AZURE_RESOURCE_NAME`, `AZURE_API_KEY`
  - `opencode`: `OPENCODE_API_KEY`
  - `none`: no variable

#### Scenario: Selected provider
- **WHEN** `OPENCODE_CONTAINER_PROVIDER=anthropic` is set and `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` and `GH_TOKEN` are set on the host
- **THEN** only `ANTHROPIC_API_KEY` among them reaches the session, by name

#### Scenario: Profile with several variables
- **WHEN** `OPENCODE_CONTAINER_PROVIDER=amazon-bedrock` is set and some of its variables are set on the host
- **THEN** each nonempty variable of that profile reaches the session by name and unset ones are omitted

#### Scenario: No provider selected
- **WHEN** `OPENCODE_CONTAINER_PROVIDER` is unset or `none`
- **THEN** no provider variable, `GH_TOKEN` or `GITHUB_TOKEN` reaches the session, and no notice is printed
- **AND** credentials stored by `opencode auth login` in the mounted OpenCode data directory remain usable

#### Scenario: Unsupported provider value
- **WHEN** `OPENCODE_CONTAINER_PROVIDER` is empty, differs in case, or names an unsupported provider
- **THEN** the wrapper exits with status 1 naming the variable and listing the accepted values, before any engine query or state creation

#### Scenario: Restricted modes select the credential from the network profile
- **WHEN** provider mode uses profile `openrouter-api` with `OPENCODE_CONTAINER_PROVIDER` unset, and `OPENROUTER_API_KEY` and `OPENAI_API_KEY` are set
- **THEN** only `OPENROUTER_API_KEY` reaches the session, by name
- **AND** `OPENAI_BASE_URL` is not forwarded in restricted modes
- **AND** the same launch with `OPENCODE_CONTAINER_PROVIDER=openai` fails before engine queries, naming both settings
- **AND** with `OPENCODE_CONTAINER_ENV_VARS=OPENAI_API_KEY` the name is skipped with a notice

### Requirement: Operator-listed extra variables
`OPENCODE_CONTAINER_ENV_VARS` SHALL accept a whitespace-separated list of variable names, and each nonempty listed variable SHALL be forwarded by name. A token that is not a valid name (`[A-Za-z_][A-Za-z0-9_]*`) SHALL stop with status 1 naming the token before any engine query or state creation. Names the launcher sets itself SHALL be skipped with one stderr notice each. In offline and provider modes the proxy, CA and protected optional-traffic variables SHALL also be treated as reserved, and in provider mode every other policy profile's credential.

#### Scenario: Extra names forwarded
- **WHEN** `OPENCODE_CONTAINER_ENV_VARS="GH_TOKEN DATABASE_URL"` is set and both variables are nonempty
- **THEN** both reach the session by name and their values are absent from engine arguments

#### Scenario: Invalid name
- **WHEN** the list contains `BAD-NAME` or `X=1`
- **THEN** the wrapper exits with status 1 naming the token before any engine query

#### Scenario: Reserved name
- **WHEN** the list contains `HOME`, `USER`, `TERM`, `EDITOR`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `CONTAINER_HOST` or `CONTAINER_CONNECTION`
- **THEN** the wrapper warns that the name is skipped and the corresponding session setting is unchanged
- **AND** with delegation disabled the session still has `CONTAINER_HOST` unset

#### Scenario: Restricted mode reserves network variables
- **WHEN** offline or provider mode runs with `OPENCODE_CONTAINER_ENV_VARS="HTTPS_PROXY SSL_CERT_FILE OPENCODE_DISABLE_AUTOUPDATE"`
- **THEN** the wrapper warns that each name is skipped, and the session keeps the helper, CA and protected values

#### Scenario: Native variables from the Windows entry
- **WHEN** a session starts from `opencode-container.ps1` with `$env:OPENCODE_CONFIG_CONTENT` set in PowerShell
- **THEN** the session has no `OPENCODE_CONFIG_CONTENT` while `OPENCODE_CONTAINER_ENV_VARS` does not list it
- **AND** with `$env:OPENCODE_CONTAINER_ENV_VARS = 'OPENCODE_CONFIG_CONTENT'` the session receives it by name, as on Linux

### Requirement: Exposure controls are documented
Wrapper help and the README SHALL list `OPENCODE_CONTAINER_PROVIDER` with its accepted values, `OPENCODE_CONTAINER_ENV_VARS`, `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG`. The README SHALL give the provider-to-variable table, state that `~/.claude` is never mounted, state that from the Windows entry OpenCode's native variables and the variables of `OPENCODE_CONTAINER_PROVIDER` reach a session only when `OPENCODE_CONTAINER_ENV_VARS` lists them, and describe the migration for users who relied on the earlier mounts and forwarding. Help SHALL remain free of engine queries and state creation.

#### Scenario: Operator reads wrapper help
- **WHEN** the operator runs `--container-help`
- **THEN** the output names the four variables and the accepted provider values
- **AND** no engine query or state creation occurs

#### Scenario: Operator reads about variables from Windows
- **WHEN** the operator reads the README's Windows section
- **THEN** it states that `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`, `OPENCODE_SERVER_USERNAME`, `OPENCODE_SERVER_PASSWORD`, the `OPENCODE_DISABLE_*` controls and the provider variables need `OPENCODE_CONTAINER_ENV_VARS` there, and that path values must be distribution paths

### Requirement: Sessions have explicit resource budgets
Every OpenCode and shell container SHALL be created with a memory limit, a CPU limit and a process limit for each budget whose cgroup v2 controller (`memory`, `cpu`, `pids`) the verified rootless engine delegates. The defaults SHALL be 4 GiB memory, 2 CPUs and 512 processes. `OPENCODE_CONTAINER_MEMORY_LIMIT`, `OPENCODE_CONTAINER_CPU_LIMIT` and `OPENCODE_CONTAINER_PIDS_LIMIT` SHALL override them. Only an unset variable SHALL select its default; no value SHALL disable a budget, and only a missing controller SHALL leave it unenforced.

#### Scenario: Accepted formats
- **WHEN** the operator sets a budget variable
- **THEN** memory accepts a positive integer with unit `k`, `m` or `g`, CPU accepts a positive decimal with at most three fractional digits up to 1024, and the process limit accepts an integer from 1 to 4194304

#### Scenario: Default budgets
- **WHEN** a session starts with none of the budget variables set on an engine delegating the `cpu`, `memory` and `pids` controllers
- **THEN** the container is created with 4 GiB memory, 2 CPUs and 512 processes

#### Scenario: Operator overrides budgets
- **WHEN** the operator sets `OPENCODE_CONTAINER_MEMORY_LIMIT=8g`, `OPENCODE_CONTAINER_CPU_LIMIT=1.5` and `OPENCODE_CONTAINER_PIDS_LIMIT=1024` on an engine delegating all three controllers
- **THEN** the container is created with exactly those limits

#### Scenario: Invalid or unbounded budget value
- **WHEN** a budget variable is set but empty or whitespace, zero, negative, `-1`, `max`, non-numeric, out of range, or has an unsupported unit
- **THEN** the wrapper exits with status 1 and names the variable before any engine query, state creation or image operation

#### Scenario: Controller not delegated
- **WHEN** the verified engine does not delegate the `cpu` controller
- **THEN** the container is created without a CPU limit, while the memory and process limits are still applied when their controllers are delegated
- **AND** the session continues and prints a notice naming the unenforced CPU budget and why it is unenforced

#### Scenario: Process controller not delegated
- **WHEN** the verified engine does not delegate the `pids` controller
- **THEN** the container is created with an explicitly unlimited cgroup process setting, so no engine default requests the missing controller
- **AND** the process budget follows the process rlimit fallback

### Requirement: Resource budgets are verified, not assumed
Before starting the application, each launch SHALL inspect the created container and require each cgroup-enforced budget to equal its selected value and each budget whose controller is not delegated to have no cgroup limit. A mismatch or missing enforced limit SHALL stop startup with an actionable diagnostic, without a retry using weaker limits. Runtime verification SHALL measure the effective cgroup v2 limits inside the session in the same way.

#### Scenario: Engine ignores a budget
- **WHEN** the created container reports no limit or a different limit for a budget whose controller the engine delegates
- **THEN** the wrapper removes only its own container and exits non-zero before the application starts
- **AND** the diagnostic names rootless cgroup v2 controller delegation and the controllers the engine reported

#### Scenario: Unenforced budget unexpectedly present
- **WHEN** the created container reports a cgroup limit for a budget whose controller the engine does not delegate
- **THEN** the wrapper removes only its own container and exits non-zero before the application starts

#### Scenario: Effective limits are measured
- **WHEN** the real-engine runtime checks run a session with default and overridden budgets
- **THEN** the container's cgroup v2 `memory.max`, `pids.max` and `cpu.max` match the selected budgets for every delegated controller, and are absent or unlimited for the others
- **AND** on the process rlimit fallback, the session's soft and hard process rlimit equal the selected process budget
- **AND** a process count beyond the process limit fails inside the session, unless the process budget is unenforced

### Requirement: Isolated persistent state option
`OPENCODE_CONTAINER_STATE_DIR` SHALL select a private host directory mounted read/write as the persistent `/opencode-home`, replacing the shared state, or with `OPENCODE_CONTAINER_READONLY_STATE` read-only below an ephemeral home. The wrapper SHALL check it lexically (absolute, no colon, CR or LF) before engine queries, then create and validate it like shared state before image operations, without repairing permissions or importing credentials. Every child the launcher uses below it, and the CA mount parent, SHALL be resolved before creation, SHALL stay inside it and SHALL be private. It SHALL NOT overlap the workspace mount and SHALL conflict with a nonempty `OPENCODE_CONTAINER_CONFIG_DIR`; an empty value selects shared state.

#### Scenario: Isolated state selected
- **WHEN** `OPENCODE_CONTAINER_STATE_DIR` names a missing absolute directory
- **THEN** the directory and its `.config/opencode`, `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode` subdirectories are created privately and the directory is mounted at `/opencode-home`
- **AND** the host XDG OpenCode directories are not mounted

#### Scenario: Insecure or overlapping state directory
- **WHEN** the selected directory is relative, belongs to another user, has group or other permissions, or equals, contains or lies inside the workspace mount
- **THEN** the wrapper exits with status 1 before any image operation and changes nothing, naming the variable for a relative or overlapping value and the directory for an ownership or permission refusal
- **AND** a relative or overlapping path fails before any engine query

#### Scenario: Escaping or shared child
- **WHEN** `.config/opencode` or another child in the isolated home is a symlink leaving it, or grants group or other permissions
- **THEN** the wrapper exits with status 1 naming the path before any image operation

#### Scenario: State persists
- **WHEN** a file is written below `/opencode-home` in one session with the same state directory
- **THEN** the next session with that directory sees it

#### Scenario: Isolated state with a configuration override
- **WHEN** both `OPENCODE_CONTAINER_STATE_DIR` and a nonempty `OPENCODE_CONTAINER_CONFIG_DIR` are set
- **THEN** the wrapper exits with status 1 naming both variables, before any engine query or state creation

#### Scenario: Empty value selects shared state
- **WHEN** `OPENCODE_CONTAINER_STATE_DIR` is set to an empty value
- **THEN** the session uses the shared state layout, as with an unset variable

#### Scenario: Engine query fails
- **WHEN** a missing isolated state directory is selected and the engine query fails
- **THEN** the wrapper exits without creating the directory

### Requirement: Hardening controls are documented
Wrapper help and the README SHALL document the budget variables with defaults and accepted formats, the lifetime variable, the state directory option, the unsafe-workspace override with the refused directories, and that capabilities are dropped in every mode. They SHALL document the process rlimit fallback, its per-session scope, the condition under which it applies, and that memory and CPU have no fallback. They SHALL state that budgets and tmpfs sizes do not bound workspace or state storage growth. Help SHALL remain free of engine queries and state creation.

#### Scenario: Operator reads wrapper help
- **WHEN** the operator runs `--container-help`
- **THEN** the output lists `OPENCODE_CONTAINER_MEMORY_LIMIT`, `OPENCODE_CONTAINER_CPU_LIMIT`, `OPENCODE_CONTAINER_PIDS_LIMIT`, `OPENCODE_CONTAINER_RUN_TIMEOUT`, `OPENCODE_CONTAINER_STATE_DIR` and `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE` with their defaults
- **AND** it states that capabilities are dropped and budgets do not limit persistent storage
- **AND** no engine query or state creation occurs

#### Scenario: Operator reads about the process rlimit fallback
- **WHEN** the operator reads the README or wrapper help
- **THEN** it states that, without the `pids` controller, the process budget is enforced through the process rlimit per session when the host counts it per container
- **AND** it states that the usable process count is slightly below the budget because of container startup tasks

### Requirement: Engine default secrets mount is masked
Every OpenCode and shell container SHALL be created with an empty read-only tmpfs at `/run/secrets`, in every network mode and with or without a session container engine. An engine default mount there, such as RHEL subscription secrets from `mounts.conf`, SHALL then be neither visible nor writable. No host configuration change SHALL be required.

#### Scenario: Host with a default secrets mount
- **WHEN** the engine's `mounts.conf` maps `/usr/share/rhel/secrets` to `/run/secrets`
- **THEN** the session has exactly one mount at `/run/secrets`, an empty tmpfs mounted read-only
- **AND** no host subscription file is readable inside the session

#### Scenario: Host without a default secrets mount
- **WHEN** the engine adds no mount at `/run/secrets`
- **THEN** the session still has the empty read-only tmpfs there and behaves as before

### Requirement: Engine-provided device mounts allow pseudo-terminals
Every OpenCode and shell container SHALL keep automatic read-only tmpfs provisioning enabled and SHALL NOT mount its own `/dev` or `devpts`, so that the engine provides `/dev` and a `devpts` that allows pseudo-terminals. It SHALL mask `/dev/shm` with an empty read-only tmpfs. Automatic provisioning SHALL add no writable path beyond the explicit temporary mounts and the engine's `/dev`. When a session joins its container engine's network namespace, Podman's read-only bind-mount of host `/sys` SHALL be documented without weakening the network namespace boundary.

#### Scenario: Terminal attaches on an engine that mounts /dev read-only
- **WHEN** an interactive session starts with a terminal on Podman 5 with crun 1.27
- **THEN** the terminal attaches and OpenCode starts without any host configuration change
- **AND** `/dev/pts` is present and `/dev/shm` is read-only and empty

#### Scenario: Pseudo-terminals are available to tools
- **WHEN** a process inside the session opens a pseudo-terminal, as an interactive tool run by OpenCode or in the shell does
- **THEN** the allocation succeeds through `/dev/ptmx` and returns a terminal under `/dev/pts`

#### Scenario: Device masks stay empty and read-only
- **WHEN** a process inside the session lists or writes `/dev/shm` or `/run/secrets`
- **THEN** both are empty and the write fails

#### Scenario: Temporary mounts keep their OpenCode policy
- **WHEN** a session starts
- **THEN** `/tmp` keeps its executable 512 MiB policy for OpenTUI, `/var/tmp` its `noexec` 512 MiB policy and `/run` its `noexec` 32 MiB policy
- **AND** no writable `/var/log` tmpfs or writable `/dev/shm` is introduced by automatic provisioning

### Requirement: Read-only persistent state
With `OPENCODE_CONTAINER_READONLY_STATE` enabled (`1`, `true` or `yes`, any case), the configuration directory and the three shared OpenCode directories, shared or from the isolated home, SHALL be mounted read-only below the ephemeral home after physical-path, read and traverse checks. This mode SHALL NOT create state, require write permission or copy credentials. The isolated home itself SHALL NOT be mounted, and the read-only directories SHALL NOT be writable inputs of restricted preparation.

#### Scenario: Readable state without write access
- **WHEN** read-only state is enabled and every state source is readable and traversable
- **THEN** startup accepts them without writable-state ownership or privacy requirements, and session writes to each mount fail

#### Scenario: Missing read-only state
- **WHEN** read-only state is enabled but a state source is absent or unreadable
- **THEN** startup fails before image operations and does not create or modify the source

#### Scenario: Invalid switch value
- **WHEN** `OPENCODE_CONTAINER_READONLY_STATE` is set to a value such as `2`
- **THEN** the wrapper exits with status 1 naming the variable before engine queries

### Requirement: Only the systemd cgroup manager delegates controllers
A reported cgroup v2 controller SHALL count as delegated only when the verified rootless engine also reports the `systemd` cgroup manager. With `cgroupfs` or any other manager, no controller SHALL count as delegated, whatever the engine reports. An unverifiable cgroup manager response SHALL stop startup before image operations.

#### Scenario: cgroupfs engine reporting every controller
- **WHEN** a session starts on a rootless engine with the `cgroupfs` manager that reports `cpu`, `memory` and `pids`
- **THEN** the container is created without memory, CPU or cgroup process limits
- **AND** the session prints notices that the memory and CPU budgets are not enforced, naming the `cgroupfs` cgroup manager
- **AND** the process budget follows the process rlimit fallback

#### Scenario: systemd engine
- **WHEN** a session starts on a rootless engine with the `systemd` manager that reports `cpu`, `memory` and `pids`
- **THEN** the memory, CPU and cgroup process limits are applied as before

#### Scenario: Unverifiable cgroup manager
- **WHEN** the engine's cgroup manager response is empty, malformed or has more than one record
- **THEN** the wrapper exits non-zero before image operations or container creation

### Requirement: Process budget falls back to the process rlimit
When the verified engine does not delegate the `pids` controller and the engine host counts the process rlimit per container, the agent container's first process SHALL set its soft and hard process rlimit to the selected process budget before the container's program runs. The engine SHALL apply no process rlimit for the budget: one applied at creation counts every container of the user. Otherwise the process budget SHALL stay unenforced. Memory and CPU SHALL have no fallback.

#### Scenario: Process controller missing on a per-container host
- **WHEN** a session starts with the default budgets on an engine delegating `cpu` and `memory` but not `pids`, on a host that counts the process rlimit per container
- **THEN** the container's first process sets a soft and hard process rlimit of 512 before the application, or the guard in restricted modes, runs
- **AND** the container is created without a cgroup process limit and without a process rlimit requested from the engine
- **AND** the memory and CPU limits are applied as before

#### Scenario: Process controller delegated
- **WHEN** the engine delegates the `pids` controller
- **THEN** the process budget is enforced only by the cgroup process limit
- **AND** the wrapper sets no process rlimit

#### Scenario: Per-container counting not established
- **WHEN** the engine does not delegate `pids` and the host is not known to count the process rlimit per container
- **THEN** the wrapper requests neither a cgroup process limit nor a process rlimit for the container
- **AND** the session continues with a notice that names the unenforced process budget and why the fallback was not applied

#### Scenario: Memory controller missing
- **WHEN** the engine does not delegate the `memory` controller
- **THEN** the memory budget stays unenforced and no substitute memory limit is set

#### Scenario: The session cannot raise its process rlimit
- **WHEN** a process in a session on the fallback tries to raise its soft or hard process rlimit above the selected budget
- **THEN** the attempt fails, because the session has no capabilities and no-new-privileges is set

#### Scenario: Concurrent sessions have independent limits
- **WHEN** two sessions on the fallback run at the same time and the first holds processes up to its limit
- **THEN** the second session can still create processes up to its own limit

#### Scenario: Other containers do not consume the session's budget
- **WHEN** other containers of the same user, such as proxies, engines or their nested containers, together hold more processes than the session's budget
- **THEN** the session starts, and can create processes up to its own budget

#### Scenario: The limit cannot be set
- **WHEN** the container's first process cannot set the process rlimit to the selected budget
- **THEN** the container stops before the application or the guard runs, and the launch exits non-zero

### Requirement: Process rlimit fallback is verified
When the process budget uses the rlimit fallback, each launch SHALL require the created agent container to start with the step that sets the selected budget, and to carry no process rlimit requested by the wrapper. Setup smoke and restricted qualification SHALL measure the effective limit inside the agent container. A mismatch SHALL stop startup or setup with an actionable diagnostic, without a retry using weaker limits.

#### Scenario: Engine drops the process rlimit
- **WHEN** the created container does not start with the step that sets the selected budget, for example because the engine dropped or replaced its entry command, or the step sets another value, or the container carries a process rlimit requested by the wrapper
- **THEN** the wrapper removes only its own container and exits non-zero before the application starts
- **AND** the diagnostic names the process rlimit fallback

#### Scenario: Effective rlimit is measured
- **WHEN** setup smoke or the restricted qualification probe runs inside an agent container on the fallback
- **THEN** it reads the effective soft and hard process rlimit and requires both to equal the selected budget
- **AND** it requires the cgroup process interface to be absent or unlimited

### Requirement: Sessions receive no Podman socket
No OpenCode or shell session container SHALL receive a host Podman socket mount or private `/var/lib/containers` / `/run/containers` delegation mounts in any network mode. When no session container engine is started, both `CONTAINER_HOST` and `DOCKER_HOST` SHALL be absent from the session environment.

#### Scenario: Unrestricted session without library images
- **WHEN** an unrestricted session starts with no image toolchains in the library
- **THEN** `/run/podman/podman.sock` is absent and neither `CONTAINER_HOST` nor `DOCKER_HOST` is set
