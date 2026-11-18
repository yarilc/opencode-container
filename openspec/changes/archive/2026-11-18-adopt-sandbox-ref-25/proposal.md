# Proposal

## Why

`sandbox-ref-22` added the shared Bash launcher core (`launcher/core.sh`). The tags up to `sandbox-ref-25` fixed it while the reference, Claude, Codex, Antigravity and Pi adopted it. OpenCode is the last wrapper still on `sandbox-ref-21`, with its own 1254-line `opencode-container.sh`. Its default mode, build path, labels, temporary storage, environment and shell mode differ from the core's. Until OpenCode adopts the core, its launcher keeps diverging, and the 26 OpenCode cases marked "to verify at adoption" in the reference test map stay open.

## What Changes

- Adopt `sandbox-ref-25` directly from `sandbox-ref-21` with `tools/propagate.py`.
  - It adds `launcher/core.sh`, `tests/test_launcher.py`, the shared `tests/fake_podman.py` and the launcher fixtures.
  - It updates the changed shared files (`network/*`, `setup/*`, `tests/test_alignment.py`, `tests/test_setup.py`, ...) and moves the manifest and the current-state references to the tag.
  - `tests/test_reference_copy.py` treats `launcher/` as a closed directory.
- Replace `opencode-container.sh` with the thin entry script, identical to the reference's apart from its name. Delete the `opencode-wrapper` shim.
- Add `agent/launcher.sh` with the OpenCode profile data and five hooks:
  - `agent_validate` checks the OpenCode-only settings before any engine or state operation:
    - `OPENCODE_CONTAINER_PROVIDER` (accepted values; in provider mode unset, `none` or the network profile's provider);
    - the exact `OPENCODE_CONTAINER_AGENTS_DIR=1` and `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` opt-ins with existing directories;
    - the refusal of an enabled `OPENCODE_CONTAINER_YOLO` together with a host `OPENCODE_PERMISSION`;
  - `agent_mounts` adds the opted-in read-only `~/.agents` and `/etc/opencode`;
  - `agent_environment` forwards by name the OpenCode native variables (`OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`, `OPENCODE_SERVER_USERNAME`, `OPENCODE_SERVER_PASSWORD`, and outside restricted modes the `OPENCODE_DISABLE_*` switches) and, in unrestricted mode, the variables of the selected `OPENCODE_CONTAINER_PROVIDER`;
  - `agent_approval_bypass` sets `OPENCODE_PERMISSION={"*":"allow"}`;
  - `agent_help` documents these variables, the provider credentials and the variable sets.

  The data declares:
  - the fixed XDG bases below `/opencode-home` for every session (reserved for `OPENCODE_CONTAINER_ENV_VARS`);
  - the five `OPENCODE_DISABLE_*=1` switches for restricted sessions;
  - one credential per policy profile (`anthropic-api`, `openai-api`, `openrouter-api`, `opencode-zen`);
  - executable temporary storage for OpenTUI.
- `agent/profile.json` declares `native.exec_tmp: true`. OpenCode keeps the default `native.exec` (`/usr/local/bin/opencode`).
- Before the old launcher is deleted, run OpenCode's current `tests/test_wrapper.py` against the new core. Classify each failing case as one of:
  - a visible change;
  - a lost behavior, fixed in the reference first, with a new tag;
  - OpenCode-only behavior, kept in the reduced `tests/test_wrapper.py`.
- Reduce `tests/test_wrapper.py` to OpenCode's hook and data tests on the shared fake engine. Update the wrapper-owned runtime tests, `tests/image-smoke.sh` and `tests/run-runtime.sh`.
- Visible changes for OpenCode users, all from the contract's "Visible changes" list. Breaking changes are allowed: the project has no release.
  - **BREAKING**: a missing `OPENCODE_CONTAINER_NETWORK` selects `provider`. Without the provider settings, the launch still stops with setup guidance.
  - **BREAKING**: legacy names are removed with no notice (U2):
    - the `opencode-wrapper` shim;
    - the `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION` notices;
    - the migration notice for credentials earlier releases forwarded.
  - **BREAKING**: `--container-build` without OpenCode arguments builds and exits (U3, U16). It validates every launch setting first.
  - **BREAKING**: images carry a `build-inputs-hash` label. An image built without it, including every image prepared before this change, is refused as stale until rebuilt (U8). Builds pull the exact base first and use the docker format.
  - **BREAKING**: `--container-shell` passes its arguments to Bash in every mode (U14), and never applies `OPENCODE_CONTAINER_YOLO`.
  - **BREAKING**: `/run` is no longer writable by the session user (L7). `/tmp` and the shared-state home stay executable 512 MiB tmpfs mounts; `/var/tmp` stays `noexec`.
  - **BREAKING**: `EDITOR` and `VISUAL` are `nano` in every session (U15).
  - **BREAKING**: the `io.opencode-container.managed`, `.workspace`, `.workspace-name` and `.instance` labels are dropped; only the session ownership label remains.
  - **BREAKING**: in provider mode `OPENCODE_CONTAINER_ENV_VARS` cannot forward another method's credential (U13). Isolated-home children must be contained and private (M4).
  - `OPENCODE_CONTAINER_READONLY_STATE` mounts the existing state read-only (U6).
  - Unrestricted sessions also forward `ALL_PROXY` and its lowercase form, run with `--init` and see `CONTAINER_NAME`. Delegated sessions get private nested-Podman tmpfs mounts (U11, U12).
  - Every read-only engine query is bounded by a timeout. A missing `podman` exits 1 instead of 127.
- Update the README, `AGENTS.md`, `docs/setup.md`, `docs/network-contract.md` and `docs/validation.md`. The help text now comes from the core.

## Capabilities

### New Capabilities

- `shared-launcher`: OpenCode's launcher is the shared core with a thin entry script and the OpenCode agent part. The agent part stays consistent with the profile, and OpenCode's own tests cover its hooks and data.

### Modified Capabilities

- `container-launcher`:
  - help from the core;
  - the build-only operation and stale images;
  - shell arguments;
  - YOLO outside shell mode;
  - removal of the deprecated shim and the ignored version variables.
- `container-isolation`:
  - temporary storage with a read-only `/run`;
  - the fixed session environment (`USER`, `TERM`, `EDITOR`, the XDG bases);
  - credentials and the provider hook;
  - extra variables with the provider-mode reservations;
  - read-only state;
  - isolated-home children;
  - removal of the migration notice.
- `container-session`:
  - provider default;
  - qualification with the resolved mode;
  - the ownership label only;
  - session name and `--init`;
  - bounded engine queries;
  - first-user guidance without the migration history.
- `container-podman-access`:
  - the `sandbox-ref-25` checks on the reported host socket path;
  - private nested-Podman tmpfs mounts;
  - bounded engine queries.
- `container-setup`:
  - the installation contains the core and the agent part;
  - the runtime image is built through the wrapper's build-only operation;
  - an empty network override selects provider.
- `network-egress`:
  - provider default, which qualification also uses;
  - launcher files as protected restricted inputs;
  - the profile with `native.exec_tmp`;
  - the shared `launcher/` component.

## Impact

- **Code:** `opencode-container.sh` shrinks to the thin entry script. Other code changes:
  - new `agent/launcher.sh`;
  - `agent/profile.json` gains `native.exec_tmp`;
  - `opencode-wrapper` is deleted;
  - shared files are copied from the tag;
  - wrapper-owned tests and docs are updated.

  The `Containerfile` is unchanged.
- **Qualification:** the qualification identity now includes the core and the agent part. Every installation needs `--container-setup` again, which also rebuilds the runtime image with its `build-inputs-hash` label. The operator runs it on the three reference hosts.
- **Users:**
  - scripts calling `opencode-wrapper` switch to `opencode-container.sh`;
  - scripts using `--container-build` to refresh and then start add OpenCode arguments, or run the session separately.
- **Other wrappers:** none. After this adoption every wrapper runs on the shared core. If this adoption finds a lost behavior, a reference fix and a new tag come first.
