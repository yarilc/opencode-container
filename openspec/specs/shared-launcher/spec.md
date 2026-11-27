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
OpenCode's launcher behavior (including leftover delegation refusal, session container engine wiring, and budgets) SHALL be tested by the shared `tests/test_launcher.py` and `tests/fake_podman.py`, copied unchanged from `sandbox-ref-36`. `tests/test_wrapper.py` SHALL test only OpenCode's hooks, agent data, credential rules per policy profile, shipped policy inventories, and OpenCode-specific option handling. An OpenCode launcher case that the shared tests do not cover SHALL be added to the reference first, not kept as a wrapper copy.

#### Scenario: Wrapper runtime tests
- **WHEN** `bash tests/run-runtime.sh --wrapper` runs
- **THEN** it runs both `tests/test_launcher.py` and `tests/test_wrapper.py` against this checkout

### Requirement: Launcher files pass ShellCheck
`launcher/core.sh`, `launcher/windows/bootstrap.sh`, the launcher fixtures and every `agent/launcher.sh` SHALL each pass ShellCheck alone, at warning level. Each SHALL declare its shell with a `shell=bash` directive. A suppressed finding SHALL concern only data and state the core shares with the agent part, or an indirectly assigned variable, and SHALL carry a comment naming the reason. The reference SHALL provide a check with a pinned ShellCheck version that runs on any checkout.

#### Scenario: Shared files checked alone
- **WHEN** the reference check runs on a reference or wrapper checkout at warning level
- **THEN** it reports no finding for `launcher/core.sh`, `launcher/windows/bootstrap.sh`, `tests/fixtures/agent/launcher.sh`, `tests/fixtures/shell-agent/launcher.sh` or `agent/launcher.sh`

#### Scenario: New finding in the core
- **WHEN** a change to `launcher/core.sh` introduces a ShellCheck warning
- **THEN** the reference check fails naming the file and line

#### Scenario: Lint-only edits keep behavior
- **WHEN** the directives and quoting are added
- **THEN** the shared launcher tests pass unchanged

### Requirement: Shared Windows shim and bootstrap
The shared launcher SHALL include the Windows shim `launcher/windows/core.ps1`, the installer scripts under `launcher/windows/` and the bootstrap `launcher/windows/bootstrap.sh`, copied byte for byte from the reference tag like the other shared files. None SHALL contain agent identifiers: the shim and the installer SHALL read the wrapper name, file name and variable prefix from `agent/profile.json`. Setup SHALL install the bootstrap in every release.

#### Scenario: Shim edited in a wrapper
- **WHEN** a wrapper's `launcher/windows/core.ps1` differs from the reference tag
- **THEN** the reference-copy test fails naming the file

#### Scenario: Agent-neutral shim
- **WHEN** the alignment test scans the shim and the bootstrap
- **THEN** neither contains the reference's name, prefix or other profile identifiers

#### Scenario: Agent-neutral installer
- **WHEN** the alignment test scans the installer scripts
- **THEN** none contains the reference's name, prefix or other profile identifiers, and each is ASCII

### Requirement: Thin PowerShell entry script
Each wrapper SHALL provide `<wrapper>-container.ps1` next to its Bash entry. It SHALL only set strict error handling and run the shared shim with its own directory, its arguments and whether it received pipeline input. The PowerShell entries of all wrappers SHALL be identical. Because propagation copies only shared directories, the adoption steps SHALL name the entry and the repository's `.gitattributes`.

#### Scenario: Comparing two wrappers
- **WHEN** the PowerShell entries of two wrappers are compared
- **THEN** they are byte-identical and contain no agent identifier

#### Scenario: Adopting the Windows entry
- **WHEN** a wrapper adopts the reference tag that introduces the shim
- **THEN** the propagation guide tells the operator to copy `<wrapper>-container.ps1` and `.gitattributes` from the reference

### Requirement: Scripts keep LF line endings in every repository
The reference and every wrapper SHALL carry a `.gitattributes` that checks out text files with LF line endings regardless of the user's `core.autocrlf` setting. A shared test SHALL fail when a tracked text file contains a carriage return.

#### Scenario: Clone with Git for Windows defaults
- **WHEN** a repository is cloned on Windows with `core.autocrlf=true`
- **THEN** the checked-out `.sh`, `.py` and `.ps1` files contain no carriage return

#### Scenario: Carriage return committed
- **WHEN** a tracked text file contains a carriage return
- **THEN** the shared test fails naming the file

### Requirement: PowerShell files pass PSScriptAnalyzer and logic tests
The shim and the PowerShell entry SHALL pass PSScriptAnalyzer at warning level with a pinned analyzer version, and the shim's logic tests SHALL pass on PowerShell 7. The reference SHALL provide one check that runs both, in a digest-pinned PowerShell container without network, on any reference or wrapper checkout. Windows PowerShell 5.1 SHALL be validated on a Windows host and recorded in the validation log.

#### Scenario: New analyzer finding
- **WHEN** a change to the shim introduces a PSScriptAnalyzer warning
- **THEN** the reference check fails naming the file and line

#### Scenario: Shim logic regression
- **WHEN** a change breaks argument encoding, environment selection or a refusal rule
- **THEN** the shim logic tests fail without a Windows host

#### Scenario: Windows PowerShell 5.1 validation
- **WHEN** a reference tag changes the shim, the bootstrap or the Windows entry
- **THEN** the validation log records the Windows host check of that tag on Windows PowerShell 5.1

### Requirement: Shared bootstrap tests
The bootstrap SHALL be tested by shared Linux tests that run it with a fake `wslpath` and a fake managed command. They SHALL cover argument decoding, working-directory translation and refusals, the missing installation and the entry-directory overlap.

#### Scenario: Bootstrap regression
- **WHEN** a change to the bootstrap drops empty arguments
- **THEN** the shared bootstrap tests fail on Linux without Windows
