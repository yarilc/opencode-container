# Tasks

## 1. Launcher

- [x] 1.1 On branch `protect-session-env-from-toolchains`, filter
  `toolchain_env` in `opencode-container.sh`: drop names starting with
  `OPENCODE_` or listed in `ALL_PROFILE_NAMES`, with one warning per name on
  standard error. Verify with `bash -n opencode-container.sh` and
  `shellcheck opencode-container.sh` (through Podman if it is missing).
- [x] 1.2 Append the filtered `toolchain_env` before the forwarding loop, and
  keep only the `PATH` entry at the image-resolution step. Verify with
  `grep -n 'toolchain_env' opencode-container.sh` that the append precedes the
  forwarding loop and the protected literals.
- [x] 1.3 Add `test_toolchain_cannot_override_protected_variables` to
  `tests/test_wrapper.py`. A default toolchain sets `JAVA_HOME`,
  `OPENCODE_DISABLE_AUTOUPDATE=0`, `OPENCODE_PERMISSION`,
  `OPENCODE_CONFIG_CONTENT` and `OPENAI_BASE_URL`. Subtests:
  - restricted provider mode with YOLO off: the protected flags are `1`, and
    the session has no `OPENCODE_PERMISSION`, `OPENCODE_CONFIG_CONTENT` or
    toolchain `OPENAI_BASE_URL`;
  - restricted mode with YOLO on: `OPENCODE_PERMISSION` is the YOLO value;
  - unrestricted mode with `OPENCODE_CONTAINER_ENV_VARS=OPENAI_BASE_URL`: the
    host value wins;
  - every case: `JAVA_HOME` is present, and each dropped name is warned
    exactly once.

  Check the final value per name (last `--env` wins), not presence alone.
  Verify that the test fails on `main` and passes on the branch.

## 2. Documentation

- [x] 2.1 Extend the README "Protected variables" bullet: OpenCode leaves out
  toolchain variables that start with `OPENCODE_` or are provider variables,
  with a warning, and toolchain variables never override forwarded or
  protected values. Mention forwarding with `OPENCODE_CONTAINER_ENV_VARS` as
  the way to pass a provider variable on purpose. Verify with
  `grep -n 'OPENCODE_' README.md`.
- [x] 2.2 In `docs/network-contract.md`, add toolchain variables to the
  sources the protected `OPENCODE_DISABLE_*` values win over. Verify with
  `git diff --check`.

## 3. Validation and publication

- [x] 3.1 Run the full unit discovery on private executable temporary
  storage, then `bash tests/run-runtime.sh --wrapper` and the default mode.
  Verify that each passes; record a known timing-sensitive test that passes
  on a rerun as such.
- [x] 3.2 Add a validation record to `docs/validation.md` with review finding
  H1, the results and "no requalification needed". Verify that
  `openspec validate protect-session-env-from-toolchains --strict` passes.
- [x] 3.3 Commit with the co-author trailer, merge into `main` with `--no-ff`,
  and verify that `git log --oneline -3` shows the merge.

## Workflow follow-up

- The operator pushes OpenCode `main`; no `--container-setup` rerun is needed.
- Sync the delta specs and archive this change.
- Adopt the reference change `harden-shared-session-boundaries` with its tag
  in a separate change.
