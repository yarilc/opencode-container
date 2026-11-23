# Proposal

## Why

OpenCode runs on `sandbox-ref-25`. Claude, Codex and Antigravity adopted
`sandbox-ref-28` on 2026-11-22 and 2026-11-23. The three tags since
`sandbox-ref-25` bring:

- **`sandbox-ref-26`:** the budgets rule.
  - Only the `systemd` cgroup manager delegates controllers.
  - Without the `pids` controller, the process budget falls back to the
    process rlimit.
  - The shared launcher files pass ShellCheck.
- **`sandbox-ref-27`:** Windows support on a Podman machine.
  - The PowerShell entry, the shim, the bootstrap, the namespace helper and
    the installer.
  - Offline and provider networking in the machine, with the guard as the
    confined init of restricted sessions.
  - Setup changes for the machine, and API key variables forwarded from
    Windows.
- **`sandbox-ref-28`:** setup started from Windows names the API key steps for
  PowerShell.

Without these tags, OpenCode has two gaps:

- On a `cgroupfs` engine, which applies no budget, OpenCode reports the budgets
  as enforced.
- OpenCode cannot run from Windows.

## What Changes

- **Adopt the tag.** `tools/propagate.py` adopts `sandbox-ref-28` from
  `sandbox-ref-25`. The dry run of 2026-11-23 gave this plan:
  - update 22 shared files;
  - add 8: the `launcher/windows/` files and the Windows tests;
  - rewrite 8 tag references: 4 in `docs/network-contract.md`, 2 in
    `README.md`, 1 each in `AGENTS.md` and `docs/setup.md`;
  - move the manifest.
- **Files outside the copied directories,** handled as in the other wrappers:
  - `opencode-container.ps1`, the thin Windows entry, copied byte for byte
    from `sandbox-container.ps1`;
  - `.gitattributes`, followed by an LF renormalization.
- **OpenCode's agent part** already carries the reference's ShellCheck header,
  so it does not change.
- **OpenCode's own tests** change only where the shared changes alter what
  they check:
  - `tests/test_setup_wrapper.py` is identical to Codex's file before Codex's
    adoption. It takes the adapted version that the other wrappers now share.
  - The budget checks of `tests/test_runtime.py` follow the engine's delegated
    controllers and process mechanism, as in the other wrappers.

  A failure caused by shared code pauses the change for a fix in the
  reference.
- **OpenCode's documentation** (`README.md`, `docs/setup.md`, `AGENTS.md`):
  - a Windows section adapted to OpenCode:
    - provider is the default, with the four API key methods;
    - `$env:<KEY>` supplies the selected method's key, or a key stored with
      `opencode auth login` in the machine;
    - OpenCode's native variables (`OPENCODE_CONFIG*`, `OPENCODE_PERMISSION`,
      `OPENCODE_SERVER_*`, `OPENCODE_DISABLE_*`) and the variables of
      `OPENCODE_CONTAINER_PROVIDER` reach a session from Windows only when
      `OPENCODE_CONTAINER_ENV_VARS` lists them;
    - the installer;
    - host CA trust with `--import-native-ca`;
    - the Windows limits, including Bitdefender;
  - the process rlimit fallback and the `cgroupfs` budgets;
  - the guard as the confined init;
  - the setup changes.
- **Parity tables:**
  - OpenCode's row names `sandbox-ref-28`, with this adoption's results;
  - the reference, Claude, Codex and Antigravity rows match
    `sandbox-container`;
  - OpenCode's row is copied into the reference and the other wrappers.
- **Validation on Windows** with OpenCode, by the operator:
  - setup in provider mode with an API key method;
  - an OpenCode session with tool use;
  - the native variables through `OPENCODE_CONTAINER_ENV_VARS`;
  - `windows-validate -Checkout` on both PowerShell editions, including
    `-Install` and `-StopMachine`.

## Capabilities

### New Capabilities

- `windows-launcher`: the reference capability, copied as is. It runs OpenCode
  from PowerShell in a Podman machine's WSL distribution.
- `windows-installation`: the reference capability, copied as is. It installs
  the Windows entry for one Windows user.

### Modified Capabilities

- `container-isolation`:
  - budgets follow the controllers the engine delegates;
  - the process budget falls back to the process rlimit;
  - the documented hardening controls include that fallback;
  - from the Windows entry, the variables that are neither `OPENCODE_CONTAINER_*`
    settings nor method credentials reach the session only through
    `OPENCODE_CONTAINER_ENV_VARS`, and the README says so.
- `container-session`: the budget notices name the reason or the rlimit
  mechanism, and the qualification identity includes the process budget
  mechanism.
- `container-setup`:
  - the questionnaire and saved budgets with the fallback;
  - recovery tags;
  - setup without a launch service;
  - carriage-return checks;
  - setup started by the Windows entry, with the PowerShell authentication
    steps;
  - the service endpoint proposed for restricted modes.
- `network-egress`: the proxy process budget falls back to the rlimit, and the
  guard runs restricted sessions as a confined init.
- `shared-launcher`:
  - ShellCheck;
  - the shared Windows shim and bootstrap;
  - the thin PowerShell entry;
  - LF line endings;
  - PSScriptAnalyzer;
  - the bootstrap tests.
- `workspace-mounts`: Windows system and profile folders are sensitive
  workspace roots.

## Impact

- **Code:** only these files change:
  - the shared files;
  - `opencode-container.ps1` and `.gitattributes`;
  - the two adapted tests.
- **Installations:** the installed core, setup and guard change, so every
  OpenCode installation reruns `--container-setup`.
- **Behavior on Linux:**
  - On a `cgroupfs` engine, the launch notices state that the memory and CPU
    budgets are not enforced and that the process budget uses the rlimit.
  - Restricted sessions run under the guard as init, so Ctrl+C reaches
    OpenCode at once.
- **Repositories:** the adoption is in `opencode-container`.
  `sandbox-container` and the other wrappers get only the parity row.
- **Dependency:** `sandbox-ref-28` already exists. The Claude, Codex and
  Antigravity adoptions give the pattern.
