# Spec Delta

## ADDED Requirements

### Requirement: OpenCode variables are protected from toolchains
The launcher SHALL leave out of every session a default toolchain variable whose name starts with `OPENCODE_` or is one of the provider variables the launcher knows, and SHALL print one warning naming the variable. Toolchain variables SHALL never take precedence over forwarded variables or the wrapper's protected values.

#### Scenario: Toolchain grants approvals without YOLO
- **WHEN** a default toolchain in the index sets `OPENCODE_PERMISSION` or `OPENCODE_CONFIG_CONTENT`, and YOLO is off
- **THEN** the session does not receive the variable, and the launcher prints one warning naming it

#### Scenario: Toolchain redirects a provider
- **WHEN** a default toolchain sets `OPENAI_BASE_URL` or another provider variable
- **THEN** the session does not receive the toolchain's value, and the launcher prints one warning naming the variable

#### Scenario: Other toolchain variables kept
- **WHEN** a default toolchain sets `JAVA_HOME` and an `OPENCODE_` variable
- **THEN** the session receives `JAVA_HOME` and the toolchain's `PATH` entries

#### Scenario: Forwarded value wins over a toolchain
- **WHEN** a default toolchain sets a variable that the operator also forwards with `OPENCODE_CONTAINER_ENV_VARS`
- **THEN** the session receives the operator's value
