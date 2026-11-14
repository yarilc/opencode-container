# Tasks

## 1. Adopt sandbox-ref-16

- [x] 1.1 Discard the paused `sandbox-ref-15` apply: stash the change
  directory, discard the tool's changes, switch to `main`, delete the branch
  `adopt-sandbox-ref-15`, and keep the stash. Then, from claude-container, run
  `python3 -I tools/propagate.py ../opencode-container sandbox-ref-12
  sandbox-ref-16` (dry run). Verify that:
  - `git status` is clean on `main`;
  - the dry run lists six modified and two added shared files, nothing
    removed or "not adopted", and commit `1fa091e`.
- [x] 1.2 Run `--apply` and restore the stash on branch
  `adopt-sandbox-ref-16`. Verify that:
  - the stash list is empty;
  - `git diff --name-only` lists only the shared files,
    `tests/test_reference_copy.py` and the four documents;
  - `python3 -m unittest tests.test_reference_copy tests.test_toolchains`
    passes on private temporary storage, including the agent-identifier
    scans.

  `test_alignment` may fail only on the profile variables, until the launcher
  port (2.2).

## 2. Launcher, test first

- [x] 2.1 In `tests/test_wrapper.py`, port the reference cases with the fake
  engine (design decision 3):
  - `--container-toolchain` dispatch: first argument only, before the
    network mode, `launch-env` refused, no engine call;
  - private creation and the `ro,nosuid,nodev` mount at `/toolchains`;
  - an unsafe library rejected before any image or container operation:
    group mode, and overlap with the workspace, the installation, a shared
    state directory and `OPENCODE_CONTAINER_STATE_DIR`;
  - `OPENCODE_CONTAINER_TOOLCHAINS` `0`/`false`/`no`, and an invalid value;
  - the default environment appended after the image `PATH`, and the single
    stale-base warning;
  - `--mount-target /toolchains` in offline and provider modes;
  - an unsafe-workspace launch from the home stopping on the overlap, and
    passing with `OPENCODE_CONTAINER_TOOLCHAINS=0`.

  Verify that the new cases fail on the current launcher.
- [x] 2.2 Port design decision 2 to `opencode-container.sh`, including the
  help text for `--container-toolchain`, `OPENCODE_CONTAINER_TOOLCHAINS` and
  `OPENCODE_CONTAINER_TOOLCHAINS_DIR`. Verify that `bash -n
  opencode-container.sh`, `tests/test_wrapper.py` and `tests/test_alignment.py`
  pass on private temporary storage. Record each existing fixture that needs
  an adaptation.
- [x] 2.3 Give `tests/run-runtime.sh` the private tmpfs and
  `SANDBOX_TEST_TMPDIR`, and create the `tests/test_wrapper.py` base there
  (design decision 4). Verify that `bash tests/run-runtime.sh --wrapper`
  passes.

## 3. Real-engine checks

- [x] 3.1 Port the reference runtime cases to `tests/test_runtime.py` and the
  live add to `tests/test_network_runtime.py`, whose installation gains
  `setup/common.py`, `setup/toolchains.py` and `Containerfile` (design
  decision 3). With the current setup image temporarily tagged
  `localhost/opencode-cli:latest` (design decision 5), verify that
  `bash tests/run-runtime.sh` and `bash tests/run-runtime.sh --network -k
  toolchain` pass.

## 4. Documentation

- [x] 4.1 Add the README "Toolchains" section (design decision 6) and update
  the help-related README part, `AGENTS.md` (the shared module) and
  `docs/setup.md` (requalification). Verify that every
  `OPENCODE_CONTAINER_TOOLCHAINS*` variable and every `--container-toolchain`
  operation appears in both the help text and the README.

## 5. Validation and publication

- [x] 5.1 Run the full unit discovery on executable, private, native
  temporary storage. Verify that there are no failures, apart from known
  timing-sensitive tests that pass on a rerun, which are recorded as such.
- [x] 5.2 Run `bash tests/run-runtime.sh` with every mode the tool listed and
  the default mode, with the temporary `latest` tag. Then remove only that
  tag. Verify that each mode passes, or record it as unavailable, and that
  the setup image keeps its own tag.
- [x] 5.3 Fill in the tool's validation-record template in
  `docs/validation.md` with the results of 1.2–5.2, the fixture adaptations,
  the requalification note and the operator checks as pending. Verify that:
  - the parity table rows match claude-container's;
  - `git diff --check` is clean;
  - `openspec validate adopt-sandbox-ref-16 --strict` passes.
- [x] 5.4 Commit on `adopt-sandbox-ref-16` with the co-author trailer (the
  tool's message, extended with the launcher port), merge it into `main` with
  `--no-ff`, and verify that `git log --oneline -3` shows the merge.

## Workflow follow-up

- The operator pushes OpenCode `main` and reruns `--container-setup` on this
  host, the Rocky Linux 9 lab host and the newer WSL host. They check
  `java -version` in an OpenCode session with the Temurin 21 toolchain and
  run `--container-toolchain verify java21`. The results are added to
  `docs/validation.md`.
- Sync the delta spec and archive this change.
