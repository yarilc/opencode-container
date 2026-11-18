## ADDED Requirements

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

## REMOVED Requirements

### Requirement: Migration notice for no longer forwarded credentials
**Reason**: The notice describes forwarding by releases that were never published, like the legacy names the shared core removes (launcher contract U2).
**Migration**: None; unrestricted sessions forward provider variables only through `OPENCODE_CONTAINER_PROVIDER` or `OPENCODE_CONTAINER_ENV_VARS`, as before.

## MODIFIED Requirements

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
