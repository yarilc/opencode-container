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
Session containers SHALL carry their management and ownership labels under the `io.opencode-container.` prefix. Ownership recovery and removal SHALL use only `io.opencode-container.session`. Containers labeled under the earlier `io.opencode.` prefix SHALL never be removed or adopted by the wrapper.

#### Scenario: Label set
- **WHEN** a session container is created
- **THEN** it carries `io.opencode-container.managed=true`, `io.opencode-container.workspace=<physical workspace>`, `io.opencode-container.workspace-name=<sanitized basename>`, `io.opencode-container.instance=<index>` and `io.opencode-container.session=<private session token>`

#### Scenario: Labels on a new session
- **WHEN** a session is created
- **THEN** its container carries the five `io.opencode-container.*` labels and no `io.opencode.*` label

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
Ordinary OpenCode and shell launches SHALL require a nonempty `OPENCODE_CONTAINER_NETWORK`. An unset or empty mode SHALL stop before engine queries, state creation or image operations, with a message naming the variable and its values. Wrapper help and `--container-qualify` SHALL keep their own checks. The check SHALL apply equally to OpenCode, shell, build, worktree and YOLO invocations.

#### Scenario: Existing invocation without a mode
- **WHEN** a user runs `opencode-container.sh` with no `OPENCODE_CONTAINER_NETWORK`
- **THEN** it exits nonzero before any engine call, naming `offline`, `provider` and `unrestricted` and stating that `unrestricted` keeps the previous behavior

#### Scenario: Help without a mode
- **WHEN** `--container-help` runs with no mode
- **THEN** help succeeds without engine calls or state side effects

### Requirement: Restricted launches require current local qualification
Before ordinary offline or provider execution, the wrapper SHALL validate a protected successful qualification report matching the current host, engine and enforcement inputs. Missing or mismatched evidence SHALL stop startup with requalification guidance. A report SHALL NOT replace per-launch engine, protected-path, guard, policy or readiness checks. Unrestricted launches and help SHALL NOT require it.

#### Scenario: Changed environment or artifacts
- **WHEN** boot, engine version, backend or endpoint, effective security policy, guard or code, runtime or proxy image identity, hardening, gate revision or selected mode, profile or policy differs from the report
- **THEN** ordinary restricted startup fails before application execution and requests `--container-qualify`
- **AND** changing environment variables never suppresses that failure

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
The qualification identity of a restricted installation SHALL include the agent capability and no-new-privileges settings, the selected memory, CPU and process budgets, and the session lifetime setting. A launch whose effective settings differ from the qualified identity SHALL stop with requalification guidance.

#### Scenario: Budget changed after qualification
- **WHEN** an installation was qualified with default budgets and the operator launches with `OPENCODE_CONTAINER_PIDS_LIMIT=1024`
- **THEN** the qualification check reports mismatched evidence and OpenCode does not start

#### Scenario: Matching settings
- **WHEN** the operator qualifies and launches with the same budgets and lifetime
- **THEN** the qualification check accepts the report
