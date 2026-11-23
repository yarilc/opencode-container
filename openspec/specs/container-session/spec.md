# container-session Specification

## Purpose

Provide predictable concurrent sandbox sessions, preserve application input and results, and bound cleanup without touching unrelated containers.

## Requirements

### Requirement: Checked bounded name reservation
The wrapper SHALL enumerate running and stopped names through a checked command and atomically reserve `<sanitized-workspace-basename>-N` using create. N MUST start above the highest existing valid suffix, with bounded base-ten parsing of one to nine digits including `08`. Reservation MUST stop after at most 20 confirmed collisions and never replace existing containers.

#### Scenario: Existing suffixes and concurrency
- **WHEN** names include `project-08`, stopped `project-12`, malformed suffixes, and oversized numeric suffixes
- **THEN** the first candidate is `project-13`, invalid suffixes are ignored safely, and concurrent collisions advance through atomic create attempts

#### Scenario: Listing or collision check fails
- **WHEN** enumeration fails or a failed create cannot be confirmed as a naming collision
- **THEN** the wrapper stops with a diagnostic instead of treating the error as an empty list or retrying indefinitely

### Requirement: Owned identity and creation diagnostics
The wrapper MUST track the full 64-character owned container ID using private creation records and keep create stdout separate from stderr diagnostics. It SHALL preserve actual creation failures, including 125, and clean up only IDs verified as belonging to the invocation; names alone MUST NOT authorize removal.

#### Scenario: Warning on successful create
- **WHEN** create emits a valid owned ID and a warning on stderr
- **THEN** the warning does not corrupt the identity and attachment selects that owned ID

#### Scenario: Create fails without ownership
- **WHEN** create exits 125 without a verified owned ID and no collision is confirmed
- **THEN** the wrapper exits 125, reports creation diagnostics, and removes no unrelated container

### Requirement: Input and terminal attachment
The wrapper SHALL keep container stdin open independently of TTY allocation, allocate a TTY only when both stdin and stdout are terminals, and preserve attached stdin and EOF even when tracking background clients.

#### Scenario: Redirected stdin
- **WHEN** stdin comes from a pipe or file
- **THEN** the attached process receives the complete input and EOF without a TTY

#### Scenario: Terminal session
- **WHEN** both stdin and stdout are terminals
- **THEN** interactive stdin and a TTY are available for OpenTUI

### Requirement: Application and interruption statuses
The wrapper SHALL preserve application exit codes including 125 and explicitly forward TERM, INT, and HUP to its owned running session. Interruption statuses MUST be 143, 130, and 129 respectively. Cleanup errors and repeated signals MUST NOT replace the first interruption status or extend shutdown deadlines.

#### Scenario: Application exits 125
- **WHEN** an attached application exits 125
- **THEN** cleanup runs for the owned container and the wrapper returns 125 without retrying creation

#### Scenario: Repeated signals
- **WHEN** TERM is followed by INT or HUP during shutdown
- **THEN** TERM is forwarded to the owned session, the wrapper returns 143, and the original shutdown deadline remains in effect

### Requirement: Bounded owned shutdown and reconciliation
Shutdown MUST finish within 20 seconds, including at most five seconds of application grace, bounded engine control calls, create reconciliation, and create/attach client termination. The wrapper SHALL recover delayed owned IDs within that budget, report unresolved creation/removal outcomes, and never infer that cancelling a local client cancelled the engine request.

#### Scenario: Stalled create and control calls
- **WHEN** interruption arrives during a stalled create or kill/remove control call
- **THEN** reconciliation and client cancellation finish within the shutdown budget
- **AND** any recovered verified owned container is removed within that budget or its unresolved outcome is reported

#### Scenario: Unrelated session survives
- **WHEN** one session shuts down normally, receives a signal, or cannot reconcile its creation
- **THEN** existing containers and other sessions remain untouched
- **AND** diagnostics identify unresolved owned IDs or the session marker for manual engine inspection

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

### Requirement: Optional session lifetime limit
`OPENCODE_CONTAINER_RUN_TIMEOUT` SHALL set the native engine lifetime of the session container in whole seconds. When it is unset, empty or `0`, no lifetime limit SHALL apply. Any other value that is not a positive decimal integer of at most ten digits SHALL fail with status 1 before engine queries. The limit SHALL be independent of the wrapper's interruption and cleanup deadlines.

#### Scenario: Lifetime disabled by default
- **WHEN** `OPENCODE_CONTAINER_RUN_TIMEOUT` is unset
- **THEN** the session container is created without a lifetime limit

#### Scenario: Lifetime expires
- **WHEN** `OPENCODE_CONTAINER_RUN_TIMEOUT=60` is set and the application is still running after 60 seconds
- **THEN** the engine stops the session container
- **AND** the wrapper prints a stderr notice that the session lifetime limit was reached
- **AND** the wrapper exits with the engine client's status and removes only its owned container

#### Scenario: Session ends before the limit
- **WHEN** the application exits before the limit
- **THEN** the wrapper propagates the application exit status unchanged and prints no lifetime notice

#### Scenario: Invalid lifetime value
- **WHEN** `OPENCODE_CONTAINER_RUN_TIMEOUT` is negative, fractional or non-numeric
- **THEN** the wrapper exits with status 1 and names the variable before any engine query or state creation

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

### Requirement: Consistent restricted prerequisite decisions
Restricted startup and qualification SHALL use the same protected platform eligibility rules and diagnostic categories. Malformed or unavailable engine or platform evidence SHALL fail closed. The rules SHALL keep launch endpoint verification and SHALL NOT reject SELinux or AppArmor merely for being enabled.

#### Scenario: Qualification and startup receive the same evidence
- **WHEN** qualification and direct restricted startup inspect equivalent host and engine evidence
- **THEN** they agree on eligibility and identify the same failed prerequisite

### Requirement: Qualification binds agent hardening settings
The qualification identity of a restricted installation SHALL include:
- the agent capability and no-new-privileges settings;
- the selected memory, CPU and process budgets;
- the set of agent and proxy budgets actually enforced, as determined by the controllers the engine delegates;
- the mechanism enforcing each agent and proxy process budget: cgroup controller, process rlimit, or none;
- the session lifetime setting.

A launch whose effective settings differ from the qualified identity SHALL stop with requalification guidance.

#### Scenario: Budget changed after qualification
- **WHEN** an installation was qualified with default budgets and the operator launches with `OPENCODE_CONTAINER_PIDS_LIMIT=1024`
- **THEN** the qualification check reports mismatched evidence and OpenCode does not start

#### Scenario: Matching settings
- **WHEN** the operator qualifies and launches with the same budgets and lifetime
- **THEN** the qualification check accepts the report

#### Scenario: Controller delegation changed after qualification
- **WHEN** an installation was qualified while `cpu` was not delegated and the engine later delegates `cpu`
- **THEN** the qualification check reports mismatched evidence and requires requalification

#### Scenario: Process budget mechanism changed after qualification
- **WHEN** an installation was qualified with the agent process budget on the process rlimit fallback and the engine later delegates `pids`
- **THEN** the qualification check reports mismatched evidence and requires requalification

### Requirement: Unenforced budgets are announced
Each launch SHALL print one notice per unenforced agent or proxy budget, naming the budget, its container and the reason: the missing cgroup controller, or a cgroup manager that applies no cgroup limits. A process budget enforced through the process rlimit fallback SHALL get one notice naming the budget, its container and the rlimit mechanism instead. Notices SHALL NOT ask for confirmation. When every budget is enforced by its cgroup controller, no notice SHALL be printed.

#### Scenario: CPU controller missing
- **WHEN** a session starts on an engine delegating only `memory` and `pids`
- **THEN** stderr shows a notice that the agent CPU budget is not enforced because the `cpu` controller is not delegated to the rootless engine
- **AND** the session starts without waiting for input

#### Scenario: All controllers delegated
- **WHEN** the engine delegates `cpu`, `memory` and `pids`
- **THEN** no budget notice is printed

#### Scenario: Engine with the cgroupfs manager
- **WHEN** a session starts on a rootless engine with the `cgroupfs` cgroup manager that reports `cpu`, `memory` and `pids`
- **THEN** stderr shows notices that the agent memory and CPU budgets are not enforced because the rootless engine uses the `cgroupfs` cgroup manager, which applies no cgroup limits
- **AND** the process budget notice names the process rlimit fallback, or the reason it was not applied

#### Scenario: Process budget on the rlimit fallback
- **WHEN** a session starts on an engine delegating `cpu` and `memory` but not `pids`, on a host that counts the process rlimit per container
- **THEN** stderr shows a notice that the agent process budget is enforced through the process rlimit because the `pids` controller is not delegated
- **AND** the notice states that the limit counts the session user's tasks, threads included
- **AND** no notice reports the agent process budget as unenforced

#### Scenario: Process rlimit fallback not applied
- **WHEN** a session starts without the `pids` controller on a host where per-container counting is not established
- **THEN** stderr shows a notice that the agent process budget is not enforced, naming the missing `pids` controller and why the rlimit fallback was not applied

### Requirement: Name collisions are confirmed by ownership
When container creation fails without returning an ID and a container with the candidate name exists, the wrapper SHALL treat it as another session's container only when its session ownership label differs from this session's token. A container carrying this session's label SHALL be reconciled and removed as this session's own, never skipped.

#### Scenario: Another session holds the name
- **WHEN** creation fails, no ID was returned, and the existing container with that name carries another session's label
- **THEN** the wrapper retries the next numeric name without touching that container

#### Scenario: The engine created this session's container
- **WHEN** creation fails without returning an ID, and the container with that name carries this session's label
- **THEN** the wrapper reports the original creation failure, does not retry, and removes that container during bounded cleanup

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
