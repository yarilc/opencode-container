## ADDED Requirements

### Requirement: Common entry point with deprecated shim
The wrapper SHALL be `opencode-container.sh` at the repository root. `opencode-wrapper` SHALL remain as a deprecated shim: it prints one stderr warning naming the new script, then replaces itself with it, passing all arguments unchanged and preserving stdin, the exit status and signal handling. The shim SHALL work when invoked through a symlink or alias. Wrapper diagnostics SHALL use the `opencode-container:` prefix.

#### Scenario: Invocation through the old name
- **WHEN** the operator runs `opencode-wrapper run "hello world" --help`, directly or through a symlink
- **THEN** stderr contains one deprecation warning naming `opencode-container.sh`
- **AND** the session behaves exactly as if `opencode-container.sh run "hello world" --help` had been run, including its exit status

#### Scenario: Help through the new name
- **WHEN** the operator runs `opencode-container.sh --container-help`
- **THEN** help is printed without the deprecation warning and without engine queries or state creation

### Requirement: YOLO switch
`OPENCODE_CONTAINER_YOLO` SHALL enable the OpenCode permission bypass with the common boolean words: `1`, `true`, `yes` enable it and unset, empty, `0`, `false`, `no` disable it, case-insensitively. Any other value SHALL stop with status 1 naming the variable before engine queries or state creation. When enabled, the session SHALL receive `OPENCODE_PERMISSION={"*":"allow"}`. The switch SHALL NOT change mounts, environment forwarding, delegation or hardening.

#### Scenario: Bypass scope
- **WHEN** YOLO is enabled and the OpenCode configuration contains `ask` or `deny` rules
- **THEN** OpenCode auto-approves every permission request, including those rules, as the native bypass flags of the other wrappers do

#### Scenario: YOLO enabled
- **WHEN** `OPENCODE_CONTAINER_YOLO=TRUE` is set
- **THEN** the session's resolved OpenCode configuration has permission `{"*":"allow"}` as its last rule
- **AND** the mounts, forwarded names and delegation settings equal those of the same launch without YOLO

#### Scenario: YOLO disabled
- **WHEN** `OPENCODE_CONTAINER_YOLO` is unset, empty, `0`, `false` or `no`
- **THEN** the wrapper adds no permission setting, and configured OpenCode permissions apply unchanged

#### Scenario: Invalid value
- **WHEN** `OPENCODE_CONTAINER_YOLO=maybe` is set
- **THEN** the wrapper exits with status 1 naming the variable before any engine query

#### Scenario: Conflicting permission input
- **WHEN** YOLO is enabled and a nonempty `OPENCODE_PERMISSION` is set on the host
- **THEN** the wrapper exits with status 1 explaining that the two cannot be combined, before any engine query

### Requirement: Image name override
`OPENCODE_CONTAINER_IMAGE` SHALL select the image used for inspection, build and session creation. When it is unset or empty, the wrapper SHALL use the per-user versioned tag. A value containing whitespace or control characters SHALL stop with status 1 before engine queries.

#### Scenario: Custom image name
- **WHEN** `OPENCODE_CONTAINER_IMAGE=localhost/opencode-custom:test` is set and the image is missing
- **THEN** the wrapper inspects, builds and runs exactly that name

## MODIFIED Requirements

### Requirement: Per-user versioned image identity
Default image tags SHALL retain OpenCode version, username, UID, and GID. The default version MUST remain `1.18.3` and equal the recipe's default `OPENCODE_VERSION` build argument. `OPENCODE_CONTAINER_VERSION` SHALL override the version, and the deprecated `OPENCODE_VERSION` SHALL remain a warned fallback. Invalid versions SHALL stop before engine queries. The image MUST provide the host user's username and numeric identity.

#### Scenario: Default and overridden versions
- **WHEN** the version is unset or explicitly overridden with `OPENCODE_CONTAINER_VERSION`
- **THEN** the selected tag and build arguments use the corresponding version and host username/UID/GID without changing the default

#### Scenario: Deprecated version variable
- **WHEN** only `OPENCODE_VERSION=1.18.3` is set
- **THEN** the wrapper prints a stderr deprecation warning and uses that version
- **AND** when both variables are set, `OPENCODE_CONTAINER_VERSION` wins

#### Scenario: Invalid version
- **WHEN** the selected version is empty or does not match `[A-Za-z0-9][A-Za-z0-9._-]*`, for example because it contains `/`, `:` or whitespace
- **THEN** the wrapper exits with status 1 naming the variable before any engine query

### Requirement: Default-deny build context
The effective Podman build context MUST allow only the root `Containerfile`, root `opencode-entrypoint`, and root `.containerignore`. Unknown files, nested lookalikes, repository metadata, local state, and credentials MUST be excluded while the required COPY input remains available.

#### Scenario: Probe context contents
- **WHEN** a disposable build context includes the required entrypoint plus unknown root files, nested recipe/helper names, and synthetic credentials
- **THEN** the entrypoint COPY succeeds and attempts to consume any unlisted input fail
