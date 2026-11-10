## MODIFIED Requirements

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

### Requirement: Isolated persistent state option
`OPENCODE_CONTAINER_STATE_DIR` SHALL select a private host directory mounted read/write as the persistent `/opencode-home`, replacing the shared state. The wrapper SHALL check it lexically before engine queries, then create and validate it like shared state before image operations, without repairing permissions or importing credentials. It SHALL NOT overlap the workspace mount and SHALL conflict with a nonempty `OPENCODE_CONTAINER_CONFIG_DIR`; an empty value selects shared state.

#### Scenario: Isolated state selected
- **WHEN** `OPENCODE_CONTAINER_STATE_DIR` names a missing absolute directory
- **THEN** the directory and its `.config/opencode`, `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode` subdirectories are created privately and the directory is mounted at `/opencode-home`
- **AND** the host XDG OpenCode directories are not mounted

#### Scenario: Insecure or overlapping state directory
- **WHEN** the selected directory is relative, belongs to another user, has group or other permissions, or equals, contains or lies inside the workspace mount
- **THEN** the wrapper exits with status 1 naming the variable and path, before any image operation, and changes nothing
- **AND** a relative or overlapping path fails before any engine query

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
