## ADDED Requirements

### Requirement: Session name and init process
Each create attempt SHALL set `CONTAINER_NAME` to the reserved container name and run with stdin from `/dev/null`. Unrestricted sessions SHALL run with `--init`. A failed create whose name holds this session's own container SHALL never count as a collision: that container SHALL be removed, or reported as unresolved.

#### Scenario: Session name inside the container
- **WHEN** an unrestricted session starts as `<prefix>-3`
- **THEN** it runs with `--init` and `CONTAINER_NAME=<prefix>-3`

#### Scenario: Own container behind a failed create
- **WHEN** create fails without publishing an ID and the engine reports this session's ownership label for the name
- **THEN** the wrapper returns the create status without retrying and removes that container

### Requirement: Read-only engine queries are bounded
Every read-only engine query (`info`, `version`, `ps`, image and container existence and inspection, the delegation socket query) SHALL be bounded by a timeout. A response with a carriage return or extra records SHALL be refused. `create`, `start`, `build` and `pull` SHALL NOT be bounded.

#### Scenario: Stalled engine query
- **WHEN** a read-only engine query does not answer
- **THEN** the wrapper stops after the query timeout with the query's diagnostic and creates no container

### Requirement: First-user setup guidance
README, wrapper help and setup guidance SHALL name `--container-setup` as the first step for new users. They SHALL explain the managed launcher and the explicit operator alternative. They SHALL state that provider is the default mode, and that offline sessions cannot reach any model provider.

#### Scenario: User follows first-run guidance
- **WHEN** a new user reads the help or the README
- **THEN** they find how to run setup and then use its managed launcher
- **AND** they learn that offline cannot reach any model provider and that no unrestricted fallback is automatic

#### Scenario: Operator chooses a mode explicitly
- **WHEN** an operator reads the guidance
- **THEN** it explains that `OPENCODE_CONTAINER_NETWORK` selects offline, provider or unrestricted, that builds need `OPENCODE_CONTAINER_MAINTENANCE=1`, and that selecting a mode does not prove restricted readiness

## REMOVED Requirements

### Requirement: First-user setup and migration guidance
**Reason**: The project has no release, so the migration path from versions without network modes no longer applies, and a missing mode now selects provider.
**Migration**: Use "First-user setup guidance".

## MODIFIED Requirements

### Requirement: Common label namespace
Session containers SHALL carry the ownership label `io.opencode-container.session=<private session token>`, and ownership recovery and removal SHALL use only that label. They SHALL carry no other `io.opencode-container.*` label. Containers labeled under the earlier `io.opencode.` prefix SHALL never be removed or adopted by the wrapper.

#### Scenario: Label set
- **WHEN** a session container is created
- **THEN** it carries `io.opencode-container.session=<private session token>`
- **AND** it carries none of `io.opencode-container.managed`, `io.opencode-container.workspace`, `io.opencode-container.workspace-name` and `io.opencode-container.instance`

#### Scenario: Labels on a new session
- **WHEN** a session is created
- **THEN** its container carries the `io.opencode-container.session` label and no `io.opencode.*` label

#### Scenario: Pre-existing session with old labels
- **WHEN** a container labeled `io.opencode.managed=true` named `project-0` exists and a new session starts in `project`
- **THEN** the new session reserves `project-1` and leaves the old container untouched

### Requirement: Explicit network mode admission
Ordinary OpenCode and shell launches SHALL use the effective `OPENCODE_CONTAINER_NETWORK`, explicit or from the managed launcher. An unset or empty mode SHALL select `provider`. A provider launch without its protected installation or provider settings SHALL exit with status 1 and a `setup required:` message. The message SHALL name `--container-setup` and the explicit-mode alternative. The refusal SHALL come before engine queries, state creation or image operations. It SHALL NOT prompt, run setup or start an application. Help, setup and `--container-qualify` keep their own checks.

#### Scenario: Existing invocation without a mode
- **WHEN** a user runs `opencode-container.sh` with no `OPENCODE_CONTAINER_NETWORK` and no provider settings, interactively or with redirected input
- **THEN** it exits with status 1 and the setup-required message before any engine call, without application output, state or runtime resources
- **AND** the message names `bash <wrapper> --container-setup` and states that an operator can set `OPENCODE_CONTAINER_NETWORK` explicitly

#### Scenario: Empty mode with provider settings
- **WHEN** `OPENCODE_CONTAINER_NETWORK` is empty and the provider settings select a protected installation
- **THEN** the launch runs in provider mode

#### Scenario: Help without a mode
- **WHEN** `--container-help` runs with no mode
- **THEN** help succeeds without engine calls or state side effects

#### Scenario: Options and other settings do not imply setup
- **WHEN** an unconfigured launch uses shell, build, worktree or YOLO, `OPENCODE_CONTAINER_MAINTENANCE=1`, or state, image, endpoint, policy or delegation settings
- **THEN** it receives the same setup-required refusal
- **AND** files in the current directory never admit the launch

### Requirement: Restricted launches require current local qualification
Before ordinary offline or provider execution, the wrapper SHALL validate a protected successful qualification report matching the current host, engine and enforcement inputs. The check SHALL use the mode the launcher resolved, including the provider default. Missing or mismatched evidence SHALL stop startup with requalification guidance. A report SHALL NOT replace per-launch engine, protected-path, guard, policy or readiness checks. Unrestricted launches and help SHALL NOT require it.

#### Scenario: Changed environment or artifacts
- **WHEN** boot, engine version, backend or endpoint, effective security policy, guard or code, launcher core or agent part, runtime or proxy image identity, hardening, gate revision or selected mode, profile or policy differs from the report
- **THEN** ordinary restricted startup fails before application execution and requests `--container-qualify`
- **AND** changing environment variables never suppresses that failure

#### Scenario: Default mode is qualified as provider
- **WHEN** `OPENCODE_CONTAINER_NETWORK` is unset and the provider settings are present
- **THEN** the launcher and every Python helper check the provider report

#### Scenario: Matching evidence
- **WHEN** a trusted complete report matches the effective restricted workflow and all per-launch checks pass
- **THEN** OpenCode starts with its existing argument, stdin, terminal and exit-status semantics
- **AND** a locally qualified combination without release acceptance is visibly identified as not release-measured

#### Scenario: Explicit qualification operation
- **WHEN** the operator runs `--container-qualify` without a current report
- **THEN** only the protected gate fixtures run through normal confinement and resource preparation
- **AND** no supplied application command or writable fixture can execute through the report-check exception
