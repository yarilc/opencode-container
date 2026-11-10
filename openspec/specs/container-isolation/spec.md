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
The root filesystem SHALL remain read-only with automatic read-only tmpfs provisioning disabled. `/tmp`, `/var/tmp`, and `/run` MUST have explicit ephemeral tmpfs mounts with capacity limits, nosuid/nodev, and modes permitting the mapped user to use them. `/tmp` MUST remain executable for OpenTUI.

#### Scenario: Effective mount flags
- **WHEN** a real session inspects its mounts
- **THEN** `/tmp` is executable, nosuid/nodev, mode 1777, and limited to 512 MiB
- **AND** `/var/tmp` is noexec, nosuid/nodev, mode 1777, and limited to 512 MiB
- **AND** `/run` is noexec, nosuid/nodev, mode 1777, and limited to 32 MiB

#### Scenario: Temporary lifetime and renderer startup
- **WHEN** files are written to temporary mounts and the session ends
- **THEN** a subsequent session does not retain those files
- **AND** interactive OpenTUI startup can extract and load its shared library from `/tmp`

### Requirement: Explicit environment allowlist without credential arguments
The wrapper MUST forward only nonempty inherited values from the base allowlist (terminal, locale, proxy and OpenCode configuration variables), the selected provider profile and `OPENCODE_CONTAINER_ENV_VARS`. Values MUST be forwarded by name and kept out of engine-client arguments. Nonsecret identity/path assignments SHALL remain explicit. Forwarded and image-default settings MUST NOT override disabled delegation. Offline and provider modes SHALL forward no inherited proxy or CA variable.

#### Scenario: Credential forwarding
- **WHEN** a key of the selected provider, `OPENCODE_SERVER_PASSWORD`, a key of another provider and an unlisted variable are set
- **THEN** the selected key and the password reach the session through `--env VARIABLE` and are absent from wrapper-generated Podman arguments
- **AND** the other provider's key and the unlisted value are not forwarded
- **AND** documentation states that container processes and engine inspection can still observe forwarded credentials

#### Scenario: Host proxy settings in a restricted mode
- **WHEN** the host sets `HTTPS_PROXY`, `no_proxy` and `NODE_EXTRA_CA_CERTS`, and the mode is offline or provider
- **THEN** none of these host values reaches the session, and provider sessions see only the relay values and `NO_PROXY=localhost,127.0.0.1,::1`
- **AND** in unrestricted mode the base allowlist forwards the proxy variables as before

### Requirement: Preserve sandbox identity and hardening
Sessions SHALL run with `--userns=keep-id --user <uid>:<gid>` set at launch, so that processes have the caller's numeric identity without an identity baked into the image. Every OpenCode and shell session SHALL drop all capabilities and enable no-new-privileges, with or without delegation and YOLO. The wrapper SHALL NOT add a capability back to resolve an incompatibility.

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
`OPENCODE_CONTAINER_PROVIDER` SHALL select the single provider profile whose variables are forwarded; accepted values are `anthropic`, `openai`, `google`, `openrouter`, `amazon-bedrock`, `azure`, `opencode` and `none`, the default when unset. Other profiles' variables, `GH_TOKEN` and `GITHUB_TOKEN` SHALL NOT be forwarded unless listed explicitly. Offline mode SHALL forward no provider variable; provider mode SHALL forward only the network profile's credential.

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
- **THEN** no provider variable, `GH_TOKEN` or `GITHUB_TOKEN` reaches the session
- **AND** credentials stored by `opencode auth login` in the mounted OpenCode data directory remain usable

#### Scenario: Unsupported provider value
- **WHEN** `OPENCODE_CONTAINER_PROVIDER` is empty, differs in case, or names an unsupported provider
- **THEN** the wrapper exits with status 1 naming the variable and listing the accepted values, before any engine query or state creation

#### Scenario: Restricted modes select the credential from the network profile
- **WHEN** provider mode uses profile `openrouter-api` with `OPENCODE_CONTAINER_PROVIDER` unset, and `OPENROUTER_API_KEY` and `OPENAI_API_KEY` are set
- **THEN** only `OPENROUTER_API_KEY` reaches the session, by name
- **AND** `OPENAI_BASE_URL` is not forwarded in restricted modes
- **AND** the same launch with `OPENCODE_CONTAINER_PROVIDER=openai` fails before engine queries, naming both settings

### Requirement: Migration notice for no longer forwarded credentials
When `OPENCODE_CONTAINER_PROVIDER` is unset and a credential variable that earlier releases forwarded is nonempty on the host, the wrapper SHALL print one stderr notice before the session starts. The notice SHALL name those variables without values and point to `OPENCODE_CONTAINER_PROVIDER` and `OPENCODE_CONTAINER_ENV_VARS`. Any accepted provider value SHALL suppress it.

#### Scenario: Covered variables
- **WHEN** the wrapper decides which variables the notice names
- **THEN** it considers every provider profile variable plus `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `GH_TOKEN` and `GITHUB_TOKEN`
- **AND** it omits variables listed in `OPENCODE_CONTAINER_ENV_VARS`

#### Scenario: Previously forwarded key present
- **WHEN** `OPENCODE_CONTAINER_PROVIDER` is unset and `OPENAI_API_KEY` and `GITHUB_TOKEN` are set
- **THEN** stderr contains one notice naming `OPENAI_API_KEY` and `GITHUB_TOKEN` and the two control variables
- **AND** neither value appears in stderr or engine arguments, and the session starts

#### Scenario: Explicit choice silences the notice
- **WHEN** `OPENCODE_CONTAINER_PROVIDER=none` is set and the same variables are set
- **THEN** no notice is printed

### Requirement: Operator-listed extra variables
`OPENCODE_CONTAINER_ENV_VARS` SHALL accept a whitespace-separated list of variable names, and each nonempty listed variable SHALL be forwarded by name. A token that is not a valid name (`[A-Za-z_][A-Za-z0-9_]*`) SHALL stop with status 1 naming the token before any engine query or state creation. Names the wrapper sets authoritatively SHALL be skipped with a stderr warning. In offline and provider modes the proxy, CA and protected optional-traffic variables SHALL also be treated as authoritative.

#### Scenario: Extra names forwarded
- **WHEN** `OPENCODE_CONTAINER_ENV_VARS="GH_TOKEN DATABASE_URL"` is set and both variables are nonempty
- **THEN** both reach the session by name and their values are absent from engine arguments

#### Scenario: Invalid name
- **WHEN** the list contains `BAD-NAME` or `X=1`
- **THEN** the wrapper exits with status 1 naming the token before any engine query

#### Scenario: Reserved name
- **WHEN** the list contains `HOME`, `USER`, `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `CONTAINER_HOST` or `CONTAINER_CONNECTION`
- **THEN** the wrapper warns that the name is skipped and the corresponding session setting is unchanged
- **AND** with delegation disabled the session still has `CONTAINER_HOST` unset

#### Scenario: Restricted mode reserves network variables
- **WHEN** offline or provider mode runs with `OPENCODE_CONTAINER_ENV_VARS="HTTPS_PROXY SSL_CERT_FILE OPENCODE_DISABLE_AUTOUPDATE"`
- **THEN** the wrapper warns that each name is skipped, and the session keeps the helper, CA and protected values

### Requirement: Exposure controls are documented
Wrapper help and the README SHALL list `OPENCODE_CONTAINER_PROVIDER` with its accepted values, `OPENCODE_CONTAINER_ENV_VARS`, `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG`. The README SHALL give the provider-to-variable table, state that `~/.claude` is never mounted, and describe the migration for users who relied on the earlier mounts and forwarding. Help SHALL remain free of engine queries and state creation.

#### Scenario: Operator reads wrapper help
- **WHEN** the operator runs `--container-help`
- **THEN** the output names the four variables and the accepted provider values
- **AND** no engine query or state creation occurs

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
`OPENCODE_CONTAINER_STATE_DIR` SHALL select a private host directory mounted read/write as the persistent `/opencode-home`, replacing the shared state for that session. The wrapper SHALL create and validate it with the same rules as the shared state before any engine query, without repairing permissions or importing credentials. It SHALL NOT overlap the workspace mount. It SHALL conflict with a nonempty `OPENCODE_CONTAINER_CONFIG_DIR`. An empty value SHALL select shared state, like an unset one.

#### Scenario: Isolated state selected
- **WHEN** `OPENCODE_CONTAINER_STATE_DIR` names a missing absolute directory
- **THEN** the directory and its `.config/opencode`, `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode` subdirectories are created privately and the directory is mounted at `/opencode-home`
- **AND** the host XDG OpenCode directories are not mounted

#### Scenario: Insecure or overlapping state directory
- **WHEN** the selected directory is relative, belongs to another user, has group or other permissions, or equals, contains or lies inside the workspace mount
- **THEN** the wrapper exits with status 1 naming the variable and path, before any engine query, and changes nothing

#### Scenario: State persists
- **WHEN** a file is written below `/opencode-home` in one session with the same state directory
- **THEN** the next session with that directory sees it

#### Scenario: Isolated state with a configuration override
- **WHEN** both `OPENCODE_CONTAINER_STATE_DIR` and a nonempty `OPENCODE_CONTAINER_CONFIG_DIR` are set
- **THEN** the wrapper exits with status 1 naming both variables, before any engine query or state creation

#### Scenario: Empty value selects shared state
- **WHEN** `OPENCODE_CONTAINER_STATE_DIR` is set to an empty value
- **THEN** the session uses the shared state layout, as with an unset variable

### Requirement: Hardening controls are documented
Wrapper help and the README SHALL document the budget variables with defaults and accepted formats, the lifetime variable, the state directory option, the unsafe-workspace override with the refused directories, and that capabilities are dropped in every mode. They SHALL state that budgets and tmpfs sizes do not bound workspace or state storage growth. Help SHALL remain free of engine queries and state creation.

#### Scenario: Operator reads wrapper help
- **WHEN** the operator runs `--container-help`
- **THEN** the output lists `OPENCODE_CONTAINER_MEMORY_LIMIT`, `OPENCODE_CONTAINER_CPU_LIMIT`, `OPENCODE_CONTAINER_PIDS_LIMIT`, `OPENCODE_CONTAINER_RUN_TIMEOUT`, `OPENCODE_CONTAINER_STATE_DIR` and `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE` with their defaults
- **AND** it states that capabilities are dropped and budgets do not limit persistent storage
- **AND** no engine query or state creation occurs
