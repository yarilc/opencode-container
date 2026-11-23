# Tasks

## 1. Adopt `sandbox-ref-28`

- [x] 1.1 Commit this change directory on `main`. Then, from `sandbox-container`, run `python3 -I tools/propagate.py ../opencode-container sandbox-ref-25 sandbox-ref-28` (dry run), then the same command with `--apply`. Verify:
  - the plan lists the files in design "Context";
  - the checklist includes `--guard`;
  - the tool switched to `adopt-sandbox-ref-28`.
- [x] 1.2 Restore the Pi row of `docs/network-contract.md` from `main` (design decision 5). Verify:
  - the Pi row equals the one on `main`;
  - the reference, Claude, Codex and Antigravity rows equal the ones in `sandbox-container`.
- [x] 1.3 Copy `sandbox-container.ps1` to `opencode-container.ps1` byte for byte, and copy `.gitattributes`. Commit both, then rewrite the working files with LF (design decision 2). Verify:
  - `git status` is clean after the renormalization, before the adoption's files are restored;
  - with host Python next to the `sandbox-container` checkout, and the sibling check not skipped, `python3 -m unittest tests.test_reference_copy tests.test_alignment` passes, including the entry, ASCII and line-ending tests.
- [x] 1.4 Run the reference lint tools (design decision 3). Verify, from `sandbox-container`:
  - `bash tools/shellcheck.sh ../opencode-container` reports no finding;
  - `bash tools/powershell.sh ../opencode-container` passes the shim cases with no finding.

## 2. OpenCode's tests and documentation

- [x] 2.1 Rebuild the runner's stale image with the maintenance build and host CA trust, and tag the guard toolchain as `development` (design decision 7). Verify: `localhost/opencode-cli:latest` carries the current `build-inputs-hash`, and reports OpenCode 1.19.5 and OpenSpec 2.0.0.
- [x] 2.2 Adapt OpenCode's own tests (design decision 4):
  - copy the shared adapted `tests/test_setup_wrapper.py` byte for byte;
  - in `tests/test_runtime.py`, add `engine_budgets()`, make `cgroup()` and `test_effective_hardening_and_budgets` follow it, with the notices, and change `test_process_limit_enforced` to a budget of 128 with 200 children, skipped when no mechanism applies.

  Verify: `bash tests/run-runtime.sh --wrapper` passes, and the default `bash tests/run-runtime.sh` passes `test_effective_hardening_and_budgets`, `test_process_limit_enforced` and `test_tools_without_capabilities`.
- [x] 2.3 Run the unit discovery in the disposable test container, then `bash tests/run-runtime.sh` in each of these modes, one at a time:
  - `--shared`, `--setup` and `--setup-runtime`;
  - `--qualification`, `--guard` and `--network`;
  - no mode.

  Record the image and the guard toolchain used. Fix in OpenCode's own tests any failure that a shared behavior change causes. Verify: every mode passes, apart from failures already recorded for this runner. A failure in shared code pauses the change.
- [x] 2.4 Adapt the documentation (design decision 6):
  - `README.md`:
    - the `## Windows with Podman machine` section, with the API key methods, `opencode auth login`, the native variables through `OPENCODE_CONTAINER_ENV_VARS`, host CA trust on Windows and the install as a command;
    - the Windows limits, including Bitdefender;
    - the unsupported-connection sentence, the Podman machine note in `### Host CA trust` and the guard as the confined init;
    - the cgroup managers and the rlimit fallback in `### Session hardening, budgets and lifetime`;
    - the Windows sensitive folders;
  - `docs/setup.md`:
    - the Windows setup and the authentication steps from Windows;
    - setup without a launch service;
    - the carriage-return check;
    - candidate tags;
    - the service endpoint for restricted modes;
    - the budget plan;
  - `AGENTS.md`: `opencode-container.ps1`, the Windows files, the ShellCheck and PowerShell checks, the Windows sensitive roots, and the cgroup manager and rlimit rule.

  Verify:
  - the README names `opencode-container.ps1`, `$env:ANTHROPIC_API_KEY`, `OPENCODE_CONTAINER_ENV_VARS` in the Windows section, and `podman machine set --import-native-ca`;
  - no `SANDBOX_CONTAINER_`, `CLAUDE_`, `CODEX_` or `ANTIGRAVITY_` name, and no statement specific to another wrapper, appears in the new text;
  - `git diff --check` passes.

## 3. Validation on Windows

- [x] 3.1 Prepare the operator bundle: snapshots of `opencode-container` and `sandbox-container`, and a README with the steps of design decision 8. Verify:
  - the README lists each step, the summary copies and the data to send back;
  - the checksums match.
- [x] 3.2 Have the operator run design decision 8. Verify that `docs/validation.md` records:
  - the setup with the API key method and its Windows next step;
  - the OpenCode session with tool use and its exit, or the authentication error with a dummy key;
  - the native variable before and after `OPENCODE_CONTAINER_ENV_VARS`;
  - `windows-validate` on both editions, once with `-Install -StopMachine`.

  No case may fail. If one does, the change pauses for a decision between a documented limit in the README's Windows limits and a fix.

## 4. Record, merge and parity

- [ ] 4.1 Add the `sandbox-ref-28` adoption section to `docs/validation.md`, from the tool's template, with every result of tasks 2.1 to 2.3 and 3.2. Set OpenCode's parity row to "Adopted `sandbox-ref-28`". Commit with the tool's message and merge into `main`. Verify: `tests/test_reference_copy.py` passes on `main`.
- [ ] 4.2 Copy OpenCode's parity row into `sandbox-container`, `claude-container`, `codex-container`, `antigravity-container` and `pi-container`, with one commit on `main` in each. Verify: the reference, Claude, Codex, Antigravity and OpenCode rows are identical in the six repositories.

## Workflow follow-up

- The operator pushes `main` in every touched repository. They also push `adopt-sandbox-ref-28` in `opencode-container`.
- The operator reruns `--container-setup` for OpenCode on the Linux hosts and on Windows.
- Archive this change with spec sync.
