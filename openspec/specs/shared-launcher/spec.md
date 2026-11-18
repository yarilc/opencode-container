# shared-launcher Specification

## Purpose

Defines how OpenCode's launcher is built from the shared Bash core of the `sandbox-container` reference and OpenCode's own agent part, so launcher behavior is specified, fixed and tested once for all wrappers.

## Requirements

### Requirement: Launcher runs on the shared core
`opencode-container.sh` SHALL be the thin entry script of the reference. It SHALL be identical to the reference's `sandbox-container.sh` after the wrapper name is replaced, and SHALL only source `launcher/core.sh` with `agent/launcher.sh` and its arguments. `launcher/core.sh` SHALL be a byte-identical copy from the adopted reference tag, recorded in the reference-copy manifest. OpenCode SHALL NOT keep launcher logic outside the core and its agent part.

#### Scenario: Core edited in this wrapper
- **WHEN** `launcher/core.sh` differs from the adopted reference tag
- **THEN** the reference-copy test fails naming the file

#### Scenario: Entry script compared with the reference
- **WHEN** `opencode-container.sh` is compared with the reference entry script after replacing the wrapper name
- **THEN** they are identical

### Requirement: OpenCode agent launcher part
`agent/launcher.sh` SHALL hold OpenCode's profile data for the core, consistent with `agent/profile.json` and `agent/policies/default.json`, including a credential entry for each policy profile of the default policy and executable temporary storage. OpenCode's hooks SHALL be `agent_validate`, `agent_mounts`, `agent_environment`, `agent_approval_bypass` and `agent_help`. Every other hook SHALL use the core default.

#### Scenario: Profile and launcher part disagree
- **WHEN** `agent/launcher.sh` and `agent/profile.json` or the default policy declare different values for the same property
- **THEN** the shared alignment test fails naming the property

#### Scenario: Credential entries
- **WHEN** the alignment test reads `AGENT_CREDENTIALS`
- **THEN** it lists `anthropic-api=ANTHROPIC_API_KEY`, `openai-api=OPENAI_API_KEY`, `openrouter-api=OPENROUTER_API_KEY` and `opencode-zen=OPENCODE_API_KEY`

#### Scenario: Help documents the agent variables
- **WHEN** `--container-help` runs without Podman
- **THEN** after the common variables it lists `OPENCODE_CONTAINER_YOLO`, `OPENCODE_CONTAINER_PROVIDER` with its accepted values, `OPENCODE_CONTAINER_AGENTS_DIR`, `OPENCODE_CONTAINER_SYSTEM_CONFIG` and each profile's credential with its forwarding rule

### Requirement: OpenCode XDG bases from the agent part
Every session SHALL receive `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` and `XDG_STATE_HOME` at `/opencode-home/.config`, `/opencode-home/.local/share`, `/opencode-home/.cache` and `/opencode-home/.local/state`. These names SHALL be reserved for `OPENCODE_CONTAINER_ENV_VARS`.

#### Scenario: Fixed XDG bases
- **WHEN** a session starts with `XDG_CONFIG_HOME=/srv/config` on the host, or with `XDG_DATA_HOME` listed in `OPENCODE_CONTAINER_ENV_VARS`
- **THEN** the session has the four XDG bases below `/opencode-home`
- **AND** the forwarding list skips `XDG_DATA_HOME` with a notice

### Requirement: OpenCode restricted settings from the agent part
Offline and provider sessions SHALL receive `OPENCODE_DISABLE_AUTOUPDATE=1`, `OPENCODE_DISABLE_DEFAULT_PLUGINS=1`, `OPENCODE_DISABLE_LSP_DOWNLOAD=1`, `OPENCODE_DISABLE_MODELS_FETCH=1` and `OPENCODE_DISABLE_SHARE=1` after toolchain and forwarded variables.

#### Scenario: Restricted settings win
- **WHEN** a toolchain sets `OPENCODE_DISABLE_AUTOUPDATE=0` or `OPENCODE_CONTAINER_ENV_VARS` lists `OPENCODE_DISABLE_SHARE` in an offline or provider session
- **THEN** the session has `OPENCODE_DISABLE_AUTOUPDATE=1` and `OPENCODE_DISABLE_SHARE=1`
- **AND** the forwarding list skips `OPENCODE_DISABLE_SHARE` with a notice

### Requirement: OpenCode native variables from the agent part
Every session SHALL receive, by name and only when set on the host, `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`, `OPENCODE_SERVER_USERNAME` and `OPENCODE_SERVER_PASSWORD`. Unrestricted sessions SHALL also receive `OPENCODE_DISABLE_AUTOUPDATE`, `OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_DISABLE_LSP_DOWNLOAD` and `OPENCODE_DISABLE_MODELS_FETCH` by name. No value SHALL appear in engine arguments.

#### Scenario: Native variables by name
- **WHEN** an unrestricted session starts with `OPENCODE_CONFIG_CONTENT` and `OPENCODE_DISABLE_LSP_DOWNLOAD` set on the host
- **THEN** both reach the session by name and their values are absent from engine arguments
- **AND** in offline or provider mode `OPENCODE_DISABLE_LSP_DOWNLOAD` has the protected value `1`

### Requirement: OpenCode launcher tests cover only OpenCode's part
OpenCode's launcher behavior SHALL be tested by the shared `tests/test_launcher.py` and `tests/fake_podman.py`, copied unchanged from the reference tag. `tests/test_wrapper.py` SHALL test only OpenCode's hooks, agent data, credential rules per policy profile and shipped policy inventories. An OpenCode launcher case that the shared tests do not cover SHALL be added to the reference first, not kept as a wrapper copy.

#### Scenario: Wrapper runtime tests
- **WHEN** `bash tests/run-runtime.sh --wrapper` runs
- **THEN** it runs both `tests/test_launcher.py` and `tests/test_wrapper.py` against this checkout
