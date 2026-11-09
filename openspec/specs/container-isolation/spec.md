# container-isolation Specification

## Purpose

Define the persistent and ephemeral filesystem boundaries and environment inputs available to an OpenCode sandbox session.

## Requirements

### Requirement: Private persistent state preflight
Before image operations the wrapper SHALL privately create missing OpenCode config/data/cache/state directories, physically resolve each, and verify caller ownership, read/write/traverse access, and no group/other permission bits. It MUST reject insecure existing paths without chmod/chown or credential copying. Creation MUST NOT change the caller's umask.

#### Scenario: Missing directories
- **WHEN** one or more writable OpenCode XDG directories do not exist
- **THEN** they are created with private permissions under a scoped creation umask and validated before image inspection or building

#### Scenario: Existing state fails validation
- **WHEN** a resolved directory is inaccessible, belongs to another user, has group/other permissions, is a broken symlink, or is not a directory
- **THEN** startup stops before image operations with a path-specific diagnostic
- **AND** existing permissions, ownership, and credentials remain unchanged

### Requirement: Consistent effective HOME and XDG layout
The session SHALL use the host HOME, including nonstandard absolute homes, and effective XDG bases consistently across wrapper mounts and the OpenCode entrypoint. Each OpenCode state directory MUST resolve to its validated physical mount destination; other host HOME content MUST NOT become writable or be mounted implicitly.

#### Scenario: Nonstandard HOME and symlinked XDG base
- **WHEN** HOME differs from `/home/<username>` and an XDG base resolves through a symlink
- **THEN** OpenCode observes that HOME and XDG paths that lead to the validated physical config/data/cache/state mounts
- **AND** no entrypoint reset redirects OpenCode toward an unmounted home

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
The wrapper MUST forward only nonempty inherited values from three sources:
- the base allowlist of terminal, locale, proxy and OpenCode configuration variables;
- the selected provider profile;
- the names listed in `OPENCODE_CONTAINER_ENV_VARS`.

Values MUST be forwarded by variable name and kept out of engine-client arguments. Deliberate nonsecret identity/path assignments SHALL remain explicit. No forwarded or image-default environment setting MUST override disabled delegation.

#### Scenario: Credential forwarding
- **WHEN** a key of the selected provider, `OPENCODE_SERVER_PASSWORD`, a key of another provider and an unlisted variable are set
- **THEN** the selected key and the password reach the session through `--env VARIABLE` and are absent from wrapper-generated Podman arguments
- **AND** the other provider's key and the unlisted value are not forwarded
- **AND** documentation states that container processes and engine inspection can still observe forwarded credentials

### Requirement: Preserve sandbox identity and hardening
The sandbox SHALL retain keep-id, the host username and numeric UID/GID, capability dropping, no-new-privileges, and the existing 512-process limit.

#### Scenario: Session identity
- **WHEN** the image is built and a session starts
- **THEN** the process has the host username and numeric identity and the existing hardening settings remain active

### Requirement: Other agents' state is never mounted
The wrapper SHALL NOT mount `~/.claude`, or any path below it, into an OpenCode session. No setting SHALL change this.

#### Scenario: Claude Code state exists on the host
- **WHEN** `$HOME/.claude` exists, with or without credential files, and a session starts
- **THEN** the generated engine arguments contain no mount whose source or destination is `$HOME/.claude` or a path below it
- **AND** inside the session `$HOME/.claude` does not exist

### Requirement: Optional integrations require exact opt-in
`$HOME/.agents` SHALL be mounted read-only at the same path only when `OPENCODE_CONTAINER_AGENTS_DIR` is exactly `1`. `/etc/opencode` SHALL be mounted read-only at the same path only when `OPENCODE_CONTAINER_SYSTEM_CONFIG` is exactly `1`. Any other value, including empty, `true` or `yes`, SHALL leave the directory unmounted. An opt-in whose directory does not exist SHALL stop with status 1 and name the variable and the path, before any engine query or state creation.

#### Scenario: Integration directories exist without opt-in
- **WHEN** `$HOME/.agents` and `/etc/opencode` exist and neither variable is set
- **THEN** neither directory is mounted

#### Scenario: Exact opt-in
- **WHEN** `OPENCODE_CONTAINER_AGENTS_DIR=1` and `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` are set and both directories exist
- **THEN** both are mounted read-only from their physical sources at their original paths
- **AND** a write attempt inside the session fails

#### Scenario: Non-exact opt-in value
- **WHEN** either variable is set to a value other than `1`
- **THEN** the corresponding directory is not mounted and startup continues

#### Scenario: Opt-in for a missing directory
- **WHEN** `OPENCODE_CONTAINER_AGENTS_DIR=1` is set and `$HOME/.agents` does not exist
- **THEN** the wrapper exits with status 1 naming the variable and the path
- **AND** no engine query, state directory or image operation occurs

### Requirement: Provider credentials follow the selected provider
`OPENCODE_CONTAINER_PROVIDER` SHALL select the single provider profile whose variables are forwarded. Accepted values are exactly `anthropic`, `openai`, `google`, `openrouter`, `amazon-bedrock`, `azure`, `opencode` and `none`. An unset value SHALL behave as `none`. Variables of unselected profiles, `GH_TOKEN` and `GITHUB_TOKEN` SHALL NOT be forwarded unless the operator lists them explicitly.

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
`OPENCODE_CONTAINER_ENV_VARS` SHALL accept a whitespace-separated list of variable names, and each nonempty listed variable SHALL be forwarded by name. A token that is not a valid name (`[A-Za-z_][A-Za-z0-9_]*`) SHALL stop with status 1 naming the token before any engine query or state creation. Names the wrapper sets authoritatively SHALL be skipped with a stderr warning.

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

### Requirement: Exposure controls are documented
Wrapper help and the README SHALL list `OPENCODE_CONTAINER_PROVIDER` with its accepted values, `OPENCODE_CONTAINER_ENV_VARS`, `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG`. The README SHALL give the provider-to-variable table, state that `~/.claude` is never mounted, and describe the migration for users who relied on the earlier mounts and forwarding. Help SHALL remain free of engine queries and state creation.

#### Scenario: Operator reads wrapper help
- **WHEN** the operator runs `--container-help`
- **THEN** the output names the four variables and the accepted provider values
- **AND** no engine query or state creation occurs
