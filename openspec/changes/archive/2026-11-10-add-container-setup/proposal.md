# Proposal

## Why

`add-network-egress` gave OpenCode restricted modes, but preparing them is still a manual operator procedure, and a missing mode only names `OPENCODE_CONTAINER_NETWORK`. This second Wave 3 change completes the OpenCode port of the Claude reference sandbox. It adds guided setup with a managed launcher, the unchanged shared setup and alignment tests, and the OpenCode row of the five-wrapper parity table.

## What Changes

- **Shared-test fix first (operator decision of 2026-11-10).** The shared `tests/test_setup.py` (tag `sandbox-ref-3`) requires at least one authentication method with `login_args`. OpenCode's four methods are API-key methods only, so the test fails at import.
  - Fix it in `claude-container`: use a login method when the profile has one, otherwise an API-key method, and skip only the login-specific checks.
  - Tag `sandbox-ref-5`.
  - Recopy the fixed test into `codex-container` (manifest and tests) and into this repository.
- Copy the rest of `setup/` unchanged from `sandbox-ref-5`: `common.py`, `setup.py`, `launch.py` and `smoke.py`. Also copy the shared tests `tests/test_setup.py` and `tests/test_alignment.py`.
- Add `--container-setup`, used alone in an interactive terminal. It runs the shared setup, which:
  - asks for the mode, the authentication method (`anthropic`, `openai`, `openrouter` or `opencode-zen`), state, endpoint, delegation, CA trust, YOLO, budgets and lifetime;
  - discloses the residual exfiltration risk of provider mode and requires its acknowledgement;
  - prepares the images and the guard under maintenance consent;
  - installs a protected release with a managed launcher at `~/.local/bin/opencode-container`;
  - runs qualification and a credential-free smoke check;
  - reports authentication as pending, naming the API-key variable of the selected method.
- **BREAKING (message only)**: an ordinary launch with an unset or empty `OPENCODE_CONTAINER_NETWORK` now stops with `setup required:` guidance pointing to `--container-setup`, instead of only naming the variable. Explicit operator modes keep working unchanged.
- The wrapper passes the application's stderr through the shared `setup/diagnostics.py` filter, as the Claude and Codex wrappers do.
- Align the wrapper messages that the shared tests check. For example, the engine-query failure becomes the Claude wording `cannot query Podman ...`, as was done for Codex.
- Replace the temporary per-agent alignment check with the unchanged `tests/test_alignment.py`. Keep `tests/test_reference_copy.py` as the byte-identity check, extended to the new shared files.
- Add the per-agent `tests/test_setup_runtime.py` and the `--setup` and `--setup-runtime` runner modes.
- Add `docs/setup.md`, and update the README, help, AGENTS.md and `docs/validation.md`.
- Add the five-wrapper parity table to `docs/network-contract.md` with the OpenCode row. Replace the "Pending" OpenCode row in `claude-container` and `codex-container` with the same row, in documentation-only commits.

## Capabilities

### New Capabilities

- `container-setup`: interactive host-side setup, covering:
  - the questionnaire and its prerequisites;
  - reviewed mutations and maintenance consent;
  - the protected installation and managed launch preferences;
  - API-key authentication assistance;
  - qualification and smoke readiness;
  - repeatable activation with rollback;
  - the provider acknowledgement;
  - saved budgets.

### Modified Capabilities

- `container-isolation`: the isolated state directory is created and validated after engine verification (lexical checks stay before it), as in the reference order.
- `container-session`: missing-mode admission points to setup; first-user setup and migration guidance is added.
- `network-egress`:
  - the missing-mode scenario directs to setup;
  - the managed launcher can supply the mode;
  - the alignment check uses the shared `test_alignment.py` across `network/` and `setup/`;
  - the contract documentation includes the parity table.

## Impact

- **Code:**
  - `opencode-container.sh`: the `--container-setup` entry point, the setup-required message, the diagnostics filter and the aligned messages;
  - new copied files: `setup/common.py`, `setup/setup.py`, `setup/launch.py`, `setup/smoke.py`.
- **Tests:**
  - shared `test_setup.py` and `test_alignment.py`;
  - per-agent `test_setup_runtime.py`;
  - updates to `test_wrapper.py`, `test_reference_copy.py` and `run-runtime.sh`.
- **Users:**
  - new users run `bash ./opencode-container.sh --container-setup` once and then use the managed launcher;
  - direct operator launches still work with an explicit mode.
- **Other repositories:**
  - `claude-container`: the shared-test fix, tag `sandbox-ref-5` and the OpenCode parity row;
  - `codex-container`: adoption of `sandbox-ref-5` and the OpenCode parity row.
- **Out of scope:**
  - authenticated provider verification, which stays operator-run;
  - interactive login methods for OpenCode.
