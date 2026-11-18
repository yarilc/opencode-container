# Tasks

## 1. Adopt `sandbox-ref-25`

- [x] 1.1 Commit this change directory on `main`. Save the current `opencode-container.sh` and `tests/test_wrapper.py` outside the repository as the old-test baseline. From `sandbox-container`, run `python3 -I tools/propagate.py ../opencode-container sandbox-ref-21 sandbox-ref-25` (dry run), then `--apply`. Add `launcher` to `CLOSED_DIRECTORIES` in `tests/test_reference_copy.py`. Verify that:
  - the plan lists exactly the files in design "Context";
  - the tool switched to `adopt-sandbox-ref-25`.
- [x] 1.2 Fix the parity table in `docs/network-contract.md` by hand (design decision 7). Verify that the reference, Claude, Codex, Antigravity and Pi rows equal those in their repositories.

## 2. Launcher on the shared core

- [x] 2.1 Add `native.exec_tmp: true` to `agent/profile.json`, write `agent/launcher.sh` (design decision 2), replace `opencode-container.sh` with the reference entry script and delete `opencode-wrapper`. Verify that:
  - `python3 -m unittest tests.test_alignment tests.test_agent_profile tests.test_launcher` passes in the disposable test container;
  - `bash opencode-container.sh --container-help` prints the provider disclosure with the hosts of the four profiles and the `OPENCODE_CONTAINER_YOLO`, `OPENCODE_CONTAINER_PROVIDER`, `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG` entries;
  - `diff <(sed s/sandbox-container/opencode-container/g ../sandbox-container/sandbox-container.sh) opencode-container.sh` is empty;
  - ShellCheck at warning level reports nothing for `opencode-container.sh` and `agent/launcher.sh`.
- [x] 2.2 Run the saved `tests/test_wrapper.py`, with its embedded fake engine, against the new entry script and core in the disposable test container. Adapt only its harness (design decision 4). Classify every failing case as (a) visible change, (b) lost behavior or (c) OpenCode-only behavior, and resolve the 26 "to verify at adoption" cases by name. Record the table in a scratch note for task 4.2. Verify that every failing case has exactly one outcome.
- [x] 2.3 If task 2.2 found any (b), pause this change and ask the user. Fix each behavior with a shared case in `sandbox-container` through its own reference change and tag, then propagate to that tag and rerun task 2.2. Update this change's artifacts to name that tag. Verify that a rerun of task 2.2 finds no (b). If task 2.2 found none, mark this task done with the note "no lost behavior".
  - Done: no lost behavior. Two candidates (the create warning and the create umask) were classified as visible changes by the user (2026-11-18).

## 3. OpenCode tests, scripts and documentation

- [x] 3.1 Rewrite `tests/test_wrapper.py` with the shared `tests/fake_podman.py` and the real agent part (design decision 5). Verify that `python3 -m unittest tests.test_wrapper` passes in the disposable test container.
- [x] 3.2 Update the wrapper-owned tests and scripts (design decision 6): `tests/run-runtime.sh`, `tests/test_runtime.py`, `tests/image-smoke.sh`, `tests/test_network_runtime.py`, `tests/test_setup_runtime.py` and `tests/test_setup_wrapper.py`. Verify that `python3 -m unittest tests.test_setup_wrapper` passes in the disposable test container and that `bash -n` succeeds on `tests/run-runtime.sh` and `tests/image-smoke.sh`.
- [x] 3.3 Update the README, `AGENTS.md`, `docs/setup.md` and `docs/network-contract.md` (design decision 7). Verify that `grep -rn "opencode-wrapper\|OPENCODE_VERSION\|OPENCODE_CONTAINER_VERSION\|io.opencode-container.managed\|previous networking\|required for every launch" --exclude-dir=openspec --exclude-dir=.git --exclude=validation.md .` finds nothing stale.

## 4. Integration

- [x] 4.1 Rebuild the OpenCode test image with `--container-build`. Then run:
  - the unit discovery in the disposable test container;
  - `bash tests/run-runtime.sh` with `--wrapper`, `--shared`, `--setup`, `--setup-runtime`, `--qualification`, `--network` and `--guard`, and the default mode;
  - `git diff --check`.

  Verify that all pass. A real-runtime failure that the old-test gate did not show is classified as in task 2.2, asking the user for any case not already covered by a contract decision.
- [ ] 4.2 Add the `sandbox-ref-25` adoption section to `docs/validation.md`, starting from the tool's template. It holds every result and the old-test classification table from task 2.2. Commit with the tool's message and merge into `main`. Verify that `tests/test_reference_copy.py` passes on `main` with host Python next to the `sandbox-container` checkout, with the sibling check not skipped.
- [ ] 4.3 Copy the OpenCode parity row into `sandbox-container`, `claude-container`, `codex-container`, `antigravity-container` and `pi-container` and commit each on `main`. Verify that the six rows are identical in the six repositories.

## Workflow follow-up

- The operator pushes `main` in the six repositories and runs `--container-setup` for OpenCode on this host, the Rocky Linux 9 lab host and the newer WSL host, then checks an OpenCode session in provider mode.
- Archive this change with spec sync. This creates `openspec/specs/shared-launcher/spec.md` in this repository.
- Every wrapper then runs on the shared launcher core.
