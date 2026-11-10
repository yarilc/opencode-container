## MODIFIED Requirements

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
