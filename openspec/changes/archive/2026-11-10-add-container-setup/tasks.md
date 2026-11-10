# Tasks

## 1. Shared setup test fix and reference `sandbox-ref-5`

- [x] 1.1 In `claude-container`, on a dedicated branch, change `tests/test_setup.py`:
  - `PROVIDER_METHOD` is the first login method, or otherwise the first API-key method;
  - `LOGIN_METHOD` becomes optional;
  - the generic uses switch to `PROVIDER_METHOD`;
  - only the login-argument execution check is skipped without a login method.

  Verify with `bash tests/run-runtime.sh --setup` and `--shared` in Claude: same results as before. Also verify with a scratch profile that has only API-key methods: the module imports, and the suite runs with only the login check skipped. Record in Claude `docs/validation.md`, merge, and create the annotated tag `sandbox-ref-5`.
- [x] 1.2 In `codex-container`, on a dedicated branch:
  - copy the fixed `tests/test_setup.py` from `sandbox-ref-5`;
  - update the manifest, tag and commit in `tests/test_reference_copy.py`, and the current-state references.

  Verify with `test_reference_copy`, `bash tests/run-runtime.sh --shared` and `--setup`. Record, commit and merge.
- [x] 1.3 In this repository, create branch `add-container-setup` from `main`. Unpack `setup/`, `tests/test_setup.py` and `tests/test_alignment.py` from `sandbox-ref-5`. Verify with `diff -r` against the tag: no differences in `network/`, `setup/` or any shared test.
- [x] 1.4 Extend the `tests/test_reference_copy.py` manifest to the new files and move it to `sandbox-ref-5`. Verify that it passes, and that it fails on an injected byte change in `setup/common.py`.

## 2. Wrapper entry points

- [x] 2.1 Add `--container-setup` to `opencode-container.sh`. It must be used alone, needs an interactive terminal and host Python 3, and runs `exec python3 -I setup/setup.py`. Help keeps precedence. Replace the missing-mode message with the `setup required:` form that names the absolute wrapper path. Verify with new `test_wrapper.py` cases and the help text.
- [x] 2.2 Pass the attached client's stderr through `setup/diagnostics.py` over a FIFO in the private session directory, when the filter and host Python exist. Reap the filter after the client within a one-second drain, inside the `shutdown` budget. Verify with `test_wrapper.py` cases:
  - the restart line is reclassified and real errors pass through;
  - the existing signal, TTY, pipe and exit-status cases still pass.
- [x] 2.3 Add `--setup` (shared `test_setup.py`) and `test_alignment` to `tests/run-runtime.sh`, and run both. They must pass without edits to shared files. Align the wrapper messages that the shared tests check literally, such as `cannot query Podman`. If a failure comes from shared code, stop and fix it in `claude-container` first.

## 3. Setup runtime acceptance

- [x] 3.1 Port `tests/test_setup_runtime.py` from Codex with OpenCode names (`OPENCODE_CONTAINER_IMAGE`, `localhost/opencode-cli:latest`, `opencode-container`, `--version` printing `1.18.3`), and add the `--setup-runtime` runner mode. Verify with `bash tests/run-runtime.sh --setup-runtime`:
  - offline, provider and unrestricted installations;
  - the managed launcher from another workspace;
  - qualification and the smoke check;
  - no credentials and no systemd changes.
- [x] 3.2 Run the setup once on the WSL target through a pseudo-terminal, with a disposable `HOME`, in provider mode with the `openrouter` method and no key set. Confirm:
  - the residual exfiltration acknowledgement naming the four profile hosts;
  - the maintenance review;
  - `Sandbox: ready`;
  - authentication pending naming `OPENROUTER_API_KEY`.

  Record the transcript summary in `docs/validation.md`.

## 4. Documentation and parity

- [x] 4.1 Add `docs/setup.md`, adapted from Codex: guided installation, maintenance consent, managed launcher, rollback and API-key authentication. Update:
  - the README: first-run section, setup-required migration, direct-launch section, verification modes;
  - the wrapper help;
  - `AGENTS.md`: the shared-file list with `setup/`, `test_setup.py` and `test_alignment.py`, the setup command and `sandbox-ref-5`;
  - `docs/network-contract.md`: references to `sandbox-ref-5`.

  Verify with markdownlint on the changed files and `git diff --check`.
- [x] 4.2 Add the five-wrapper parity table with the OpenCode row to `docs/network-contract.md`. Replace the OpenCode row in `claude-container/docs/network-contract.md` and `codex-container/docs/network-contract.md`, documentation only, in those working trees. Verify that the three rows are identical and that the links resolve.
- [x] 4.3 Final verification:
  - `bash -n` and ShellCheck;
  - `bash tests/run-runtime.sh` with `--wrapper`, `--shared`, `--setup`, `--setup-runtime`, `--network`, `--qualification` and the default mode;
  - `openspec validate add-container-setup --strict`;
  - `git diff --check`.

  Record the results in `docs/validation.md`, and update the `todo.md` items C10 and C12.

## Workflow follow-up

- `/opsx:archive`, then commit and merge into `main` here. Commit the parity-row edits in `claude-container` and `codex-container`. The user pushes, including the tag `sandbox-ref-5`.
- The operator-run authenticated checks remain pending for the four profiles.
- Next Wave 3 port: Pi (`add-network-egress`).
