# Design

## Context

OpenCode adopted `sandbox-ref-25` on 2026-11-18 and pinned OpenCode 1.19.5
and OpenSpec 2.0.0 the same day. Its runtime and egress images are its own and
stay as they are. The tag changes no OpenCode build input. The operator fixed
the executable bit of `opencode-container.sh` on 2026-11-22.

**Dry run.** `tools/propagate.py ../opencode-container sandbox-ref-25
sandbox-ref-28` (2026-11-23) gave this plan:

- **Update:**
  - `launcher/core.sh`;
  - `network/README.md`, `agent_budgets.py`, `control.py`, `guard.c`,
    `proxy_hardening.py`, `qualification_probe.py`,
    `qualification_records.py` and `session.py`;
  - `setup/common.py`, `launch.py`, `setup.py` and `smoke.py`;
  - `tests/fake_podman.py` and both fixture `launcher.sh`;
  - `tests/test_alignment.py`, `test_guard.py`, `test_launcher.py`,
    `test_qualification.py`, `test_session.py` and `test_setup.py`.
- **Add:**
  - the five `launcher/windows/` files;
  - `tests/test_windows_bootstrap.py` and `tests/test_windows_enter.py`;
  - `tests/windows/shim_tests.ps1`.
- **Rewrite:** 2 references in `README.md`, 1 each in `AGENTS.md` and
  `docs/setup.md`, and 4 in `docs/network-contract.md`. The 4 include the
  "Adopted `sandbox-ref-25`" cell of the Pi row.
- **Move:** the manifest to `ba1ef14`.
- **Runner modes listed:** `--shared`, `--setup`, `--setup-runtime`,
  `--qualification`, `--guard` and `--network`.

**ShellCheck today.** `tools/shellcheck.sh ../opencode-container` reports
findings only in `launcher/core.sh` (14) and both fixtures (32 and 25), which
the tag replaces. OpenCode's agent part already starts with
`# shellcheck shell=bash disable=SC2034,SC2154`, since the shared launcher
core adoption.

**OpenCode's own tests.**
- `tests/test_setup_wrapper.py` is byte for byte the file Codex had before its
  adoption. Claude, Codex and Antigravity now share one adapted version.
- In `tests/test_runtime.py`, the `cgroup()` helper and
  `test_effective_hardening_and_budgets` assert cgroup limits for all three
  budgets. `test_process_limit_enforced` starts 80 children under a process
  budget of 32.
- `test_build_context` copies only `.containerignore` and checks file
  presence, not modes, so the defect fixed in Antigravity does not apply.

**OpenCode specifics on Windows.** The shim reads every wrapper-specific
value from `agent/profile.json`:
- `native.command` is `opencode`, so `tools/windows-validate.ps1` runs its
  cases with `--container-shell`.
- The four methods (`anthropic`, `openai`, `openrouter`, `opencode-zen`) are
  API key methods. The shim forwards their keys by name, and setup started
  from Windows names `$env:<KEY>`. A key stored with `opencode auth login`
  stays in OpenCode's data directory in the machine.
- The shim forwards `OPENCODE_CONTAINER_*`, the method keys and the names in
  `OPENCODE_CONTAINER_ENV_VARS`, and nothing else. On Linux,
  `agent_environment` also forwards OpenCode's native variables
  (`OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`,
  `OPENCODE_PERMISSION`, `OPENCODE_SERVER_*`, and in unrestricted mode the
  `OPENCODE_DISABLE_*` controls and the variables of
  `OPENCODE_CONTAINER_PROVIDER`). From Windows those reach the distribution
  only when `OPENCODE_CONTAINER_ENV_VARS` lists them. A listed name is then
  forwarded into the session by `agent_environment` and by the list, with the
  same value, and the list's reserved-name rules apply.
- `native.config_dir_env` is `OPENCODE_CONTAINER_CONFIG_DIR`, forwarded only
  with a distribution path. Shared state is the machine user's
  `~/.config/opencode` and the private shared directories under
  `~/.local/share/opencode`, `~/.cache/opencode` and `~/.local/state/opencode`.
- On 2026-11-12 the operator ran OpenCode sessions on this host with the
  `opencode-zen` profile, and on 2026-11-11 with `anthropic-api`.

**Images.** The runner's engine has no `localhost/opencode-cli:latest`. Its
only `setup-*` image, `cb50f94ee11b`, has `build-inputs-hash` `b6c2cfc8…`,
the hash of the OpenCode 1.18.3 image. The 1.19.5 pin record gives
`5a57734a…`. The guard toolchain exists only under a `setup-*` tag.

## Goals / Non-Goals

**Goals:**

- OpenCode runs on the `sandbox-ref-28` shared files. Beyond the two adapted
  tests, no OpenCode-specific code changes.
- OpenCode works from Windows on a Podman machine, in provider mode with an
  API key method, with the installer.
- The README states how OpenCode's native variables reach a session from
  Windows.
- The parity tables of the reference and the five wrappers state the same rows.

**Non-Goals:**

- Pi, which adopts the tag in its own change.
- Forwarding OpenCode's native variables from Windows without
  `OPENCODE_CONTAINER_ENV_VARS`. That would need a profile field read by the
  shared shim, which is a reference change.
- Delegation on Windows and macOS.
- The three provider profiles still pending on Linux.

## Decisions

1. **Adopt with the tool, from `sandbox-ref-25` directly.** Commit this change
   directory on `main`, then run the dry run and `--apply`. `--apply` creates
   `adopt-sandbox-ref-28`. This repeats the other adoptions.
2. **Hand-copied files on the same branch.**
   - `sandbox-container.ps1` becomes `opencode-container.ps1`, byte for byte.
   - `.gitattributes` is copied. Then, on a clean tree,
     `git rm -r -q --cached . && git reset --hard` rewrites the working files.
     The adoption's uncommitted files are set aside with a named stash first.
   - The shared alignment tests then check the entry, ASCII and line endings.
3. **OpenCode's agent part stays as it is.** It already has the reference
   header and passes ShellCheck.
4. **OpenCode's own tests.**
   - `tests/test_setup_wrapper.py` takes the shared adapted file byte for
     byte, because the files matched before.
   - `tests/test_runtime.py` follows the same rule in its own structure:
     - an `engine_budgets()` helper reads the delegated controllers and the
       process mechanism through `network/agent_budgets.py`;
     - `cgroup()` also reports the process rlimit and tolerates a missing
       controller file, and `test_effective_hardening_and_budgets` asserts
       each budget by its mechanism, plus the launch notices;
     - `test_process_limit_enforced` uses a budget of 128 with 200 children,
       and is skipped when no mechanism applies.
   - Any other failure caused by a shared behavior change is fixed in
     OpenCode's test on the same branch. A failure in shared code pauses the
     change for a reference fix and a new tag.
5. **Parity rows after `--apply`.**
   - The tool rewrites every `sandbox-ref-25` in `docs/network-contract.md`,
     including the Pi row.
   - After `--apply`, restore the Pi row from `main`. Check that the
     reference, Claude, Codex and Antigravity rows equal `sandbox-container`'s.
   - Task 4.1 sets OpenCode's own row.
6. **Docs adapted, not copied.** The Codex text for the shared behavior moves
   into OpenCode's layout, which matches Codex's.
   - **`README.md`:**
     - a new `## Windows with Podman machine` section before
       `## Mounts and security`, with `### Trusting a host CA on Windows` and
       `### Install as a command`. It covers:
       - the provider default and the four API key methods with
         `$env:<KEY>`, or a key stored with
         `opencode-container.ps1 auth login` in the machine;
       - `opencode-container.ps1` and the `OPENCODE_CONTAINER_*` variables;
       - the native and provider variables through
         `OPENCODE_CONTAINER_ENV_VARS`, with distribution paths for
         `OPENCODE_CONFIG` and `OPENCODE_CONFIG_DIR`;
       - `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG`,
         which mount the machine's `~/.agents` and `/etc/opencode`;
       - the Windows limits, with Bitdefender;
     - the unsupported-connection sentence points to the Windows section;
     - `### Host CA trust` gets the Podman machine note;
     - the guard as the confined init, next to the `--init` of unrestricted
       sessions;
     - in `### Session hardening, budgets and lifetime`:
       - the `systemd` and `cgroupfs` managers;
       - the process rlimit fallback, with its risk;
       - the Windows sensitive folders.
   - **`docs/setup.md`:**
     - the Windows setup and the authentication steps from Windows;
     - setup without a launch service;
     - the carriage-return check;
     - candidate tags;
     - the service endpoint for restricted modes;
     - the budget plan, replacing the stale statement that the controllers
       must be delegated.
   - **`AGENTS.md`:** `opencode-container.ps1`, the Windows files, the
     ShellCheck and PowerShell checks, the Windows sensitive roots, and the
     cgroup manager and rlimit rule.
7. **Validation on this runner,** in OpenCode's checkout:
   - `python3 -m unittest tests.test_reference_copy tests.test_alignment` next
     to the `sandbox-container` checkout, with the sibling check not skipped;
   - the unit discovery in the disposable test container;
   - `bash tests/run-runtime.sh` in each of these modes:
     - `--wrapper`, `--shared`, `--setup` and `--setup-runtime`;
     - `--qualification`, `--guard` and `--network`;
     - the default runtime run;
   - from `sandbox-container`, `bash tools/shellcheck.sh ../opencode-container`
     and `bash tools/powershell.sh ../opencode-container`;
   - `git diff --check`.

   The runner's image is stale, so rebuild it first with
   `OPENCODE_CONTAINER_NETWORK=unrestricted OPENCODE_CONTAINER_MAINTENANCE=1
   opencode-container.sh --container-build`, with host CA trust and the
   session's CA bundle behind the runner's TLS interception. For `--guard`,
   tag the guard toolchain as `development`. Record the image and the
   toolchain. The suites run one at a time, because the timing-sensitive
   shared tests failed under load in the Antigravity adoption.
8. **Validation on Windows.** The operator gets a bundle with snapshots of
   `opencode-container` and `sandbox-container`, and these steps:
   1. `.\opencode-container.ps1 --container-setup` with provider networking
      and the method of a key the operator has: `opencode-zen`, as on this
      host on 2026-11-12, or `anthropic`. Check that setup names
      `$env:<KEY>` and `opencode-container.ps1`, with no distribution path.
      The first setup builds the OpenCode images in the machine.
   2. A session from a project folder, with `$env:<KEY>` set: one prompt that
      reads a file of the folder, which runs a tool, then exit. Note the exit
      status. `podman ps -a` must list no container of the session. Without
      any real key, a dummy key must end with the provider's authentication
      error instead, not a proxy or certificate error.
   3. The native variables: with `$env:OPENCODE_CONFIG_CONTENT` set,
      `--container-shell -c 'echo "${OPENCODE_CONFIG_CONTENT-unset}"'` prints
      `unset`, then prints the value once
      `$env:OPENCODE_CONTAINER_ENV_VARS = 'OPENCODE_CONFIG_CONTENT'` is set.
   4. `sandbox-container\tools\windows-validate.ps1 -Checkout
      C:\Work\opencode-container`:
      - on Windows PowerShell 5.1 with `-Install -StopMachine`;
      - on PowerShell 7 without them.

   Each summary is copied after its run. A failed step pauses the change for a
   decision between a documented Windows limit and a fix.
9. **Parity rows across repositories.**
   - OpenCode's row names "Adopted `sandbox-ref-28`", with this adoption's
     results.
   - After the merge, OpenCode's row is copied into `sandbox-container` and
     the four other wrappers, one commit on `main` each.
   - The Pi row stays as it is.

## Risks / Trade-offs

- [Three tags at once widen the validation surface.] → Every runner mode that
  the tool lists runs, including `--guard`, plus `--wrapper` and the default
  runtime run.
- [The native variables need an extra step on Windows.] → The README says so,
  Windows step 3 checks it, and a later reference change can add a profile
  field if operators need more.
- [An earlier OpenCode configuration in the machine, such as plugins, can
  stall a provider session, as on Linux on 2026-11-11.] → The README's
  "Plugins and network modes" applies in the machine. A stall caused by
  configuration is recorded, not fixed here.
- [The first build in the machine downloads OpenCode through the TLS
  interception.] → The bundle README requires
  `podman machine set --import-native-ca` and the host CA answer.
- [Installed qualification reports no longer match.] → After the merge, the
  operator reruns `--container-setup` on the Linux hosts and on Windows.
- [The tool rewrites rows of wrappers it does not adopt.] → Decision 5 restores
  them before the commit. Task 4.2 checks them in every repository.
