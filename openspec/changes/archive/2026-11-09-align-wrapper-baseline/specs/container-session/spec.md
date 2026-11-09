## ADDED Requirements

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
