## MODIFIED Requirements

### Requirement: Explicit image refresh and error handling
`--container-build` SHALL build or refresh the selected image before starting the selected session. Ordinary startup SHALL build only when image inspection returns missing-image status 1 and MUST stop on every other inspection error. All modes except help MUST apply engine, enabled delegation, and state preflights before image operations.

#### Scenario: Unexpected inspection failure
- **WHEN** image inspection fails with an engine/storage status other than 1
- **THEN** no automatic build or container creation occurs and the failure is reported

#### Scenario: Missing image and explicit refresh
- **WHEN** the image is missing or `--container-build` is requested
- **THEN** a successful preflight is followed by a build from the wrapper's physical recipe directory and then the requested OpenCode or shell session
- **AND** build failure prevents session creation

### Requirement: Image name override
`OPENCODE_CONTAINER_IMAGE` SHALL select the image used for inspection, build and session creation. When it is unset or empty, the wrapper SHALL use `localhost/opencode-cli:latest`. A value containing whitespace or control characters SHALL stop with status 1 before engine queries.

#### Scenario: Default image
- **WHEN** `OPENCODE_CONTAINER_IMAGE` is unset
- **THEN** the wrapper inspects, builds when missing and runs `localhost/opencode-cli:latest`, passing no user identity build arguments

#### Scenario: Custom image name
- **WHEN** `OPENCODE_CONTAINER_IMAGE=localhost/opencode-custom:test` is set and the image is missing
- **THEN** the wrapper inspects, builds and runs exactly that name

## REMOVED Requirements

### Requirement: Per-user versioned image identity
**Reason**: The image is generic and its OpenCode version is pinned in `Containerfile`; the user identity is set at launch.
**Migration**: Remove old `localhost/opencode-sandbox:*` images when no longer needed. `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION` are ignored with a warning; version changes follow the `runtime-image` maintenance procedure.

### Requirement: Default-deny build context
**Reason**: Moved to the `runtime-image` capability, where the context now contains only `Containerfile` and `.containerignore`.
**Migration**: None; the policy is stricter.

## ADDED Requirements

### Requirement: Ignored version variables
When `OPENCODE_CONTAINER_VERSION` or `OPENCODE_VERSION` is set, the wrapper SHALL print one stderr warning that the variable is ignored and that the version is pinned in `Containerfile`, and SHALL continue with the selected image.

#### Scenario: Legacy version variable set
- **WHEN** `OPENCODE_VERSION=1.17.0` is set
- **THEN** stderr contains one warning naming the variable, the build passes no version argument, and the session starts normally
