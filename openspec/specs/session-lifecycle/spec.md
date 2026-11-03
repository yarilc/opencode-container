# session-lifecycle Specification

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
