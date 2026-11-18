# Design

## Context

OpenCode is on `sandbox-ref-21`. Its launcher, `opencode-container.sh` (1254 lines), differs from the shared core where the launcher contract (`docs/launcher-contract.md` in `sandbox-container`, column O) records:

- **Default mode (U1):** an unset `OPENCODE_CONTAINER_NETWORK` stops with setup guidance; the core selects `provider`.
- **Names (U2):**
  - the `opencode-wrapper` shim;
  - the notices for `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION`.
- **Build (U3, U8, U12, U16):**
  - `--container-build` alone builds and then starts a session;
  - images carry no `build-inputs-hash` label;
  - setup builds the runtime image itself;
  - no exact-base pull or docker format.
- **Temporary storage (U7, L7):** `/tmp` and the shared-state home are executable 512 MiB tmpfs mounts (kept: the profile declares executable temporary storage); `/run` has mode 1777.
- **Environment (U11, U15, phase 5):**
  - `EDITOR` and `VISUAL` are unset;
  - `ALL_PROXY` is not forwarded;
  - `USER` already is the host user name.
- **Session (U12, phase 6):**
  - no `--init` and no `CONTAINER_NAME`;
  - four extra labels (`io.opencode-container.managed`, `.workspace`, `.workspace-name`, `.instance`);
  - the name fallback is `workspace`.
- **Shell and approval (U14, phase 1-2):** shell mode drops its arguments and still applies `OPENCODE_CONTAINER_YOLO`.
- **Messages:** a missing `podman` exits 127.
- **OpenCode-only behavior:**
  - `OPENCODE_CONTAINER_PROVIDER` with seven variable sets, checked against the network profile in provider mode (`agent_validate`, `agent_environment`);
  - the native-variable allowlist (`agent_environment`, H-g);
  - the exact `OPENCODE_CONTAINER_AGENTS_DIR=1` and `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` read-only mounts (`agent_validate`, `agent_mounts`);
  - `OPENCODE_PERMISSION={"*":"allow"}` for YOLO and its conflict with a host `OPENCODE_PERMISSION` (`agent_approval_bypass`, `agent_validate`);
  - the fixed XDG bases and the five `OPENCODE_DISABLE_*` restricted switches (data);
  - the notice naming credentials that earlier releases forwarded.

OpenCode already shares its four state directories by default (U4), forwards names from `OPENCODE_CONTAINER_ENV_VARS` (U5), bounds its shutdown with one 20-second deadline (U9) and validates `OPENCODE_CONTAINER_IMAGE`.

The test map (`docs/launcher-test-map.md`) sorts OpenCode's 69 `tests/test_wrapper.py` cases into:

| Destination | Cases |
| --- | --- |
| Shared | 21 |
| Shared (rewrite) | 5 |
| Shared (duplicate) | 30 |
| Hook | 10 |
| Obsolete | 2 |
| Fake engine | 1 |

26 cases are marked "to verify at adoption". The hook cases are:
- `test_private_xdg_and_umask`;
- `test_host_xdg_variables_do_not_relocate_state`;
- `test_tmpfs_and_named_environment`;
- `test_claude_state_is_never_mounted`;
- `test_integrations_require_exact_opt_in`;
- `test_missing_opted_in_integration_fails_early`;
- `test_provider_profiles`;
- `test_unsupported_provider_fails_early`;
- `test_unselected_provider_forwards_nothing_and_notifies`;
- `test_yolo_switch`.

The obsolete cases are `test_deprecated_shim` and `test_labels_use_common_namespace`.

The `tools/propagate.py` dry run from `sandbox-ref-21` straight to `sandbox-ref-25` (2026-11-18) gives this plan:

- **Add:** `launcher/core.sh`, `tests/fake_podman.py`, `tests/fixtures/agent/launcher.sh`, `tests/fixtures/shell-agent/launcher.sh`, `tests/test_launcher.py`.
- **Update:** `network/README.md`, `network/agent_profile.py`, `network/control.py`, `network/qualification_records.py`, `network/qualify.py`, `setup/common.py`, `setup/launch.py`, `setup/setup.py`, `tests/fixtures/agent/profile.json`, `tests/sandbox_profile.py`, `tests/test_agent_profile.py`, `tests/test_alignment.py`, `tests/test_network_policy.py`, `tests/test_qualification.py`, `tests/test_setup.py`.
- **Rewrite:** one reference each in `README.md`, `AGENTS.md` and `docs/setup.md`, and eight in `docs/network-contract.md`.
- **Move:** the manifest to `sandbox-ref-25` (`6bed770`).

OpenCode's old `tests/test_wrapper.py` embeds its fake engine; the shared `tests/fake_podman.py` is new here. OpenCode has no `test.sh`, no CI workflow, no `SECURITY.md`, `CONTRIBUTING.md` or `CHANGELOG.md`; `tests/image-smoke.sh` runs inside the default runtime suite.

The Claude, Codex, Antigravity and Pi adoptions found what every adoption needs:
- `tests/test_reference_copy.py` lists `launcher` in `CLOSED_DIRECTORIES`.
- The old wrapper tests run against the core only with an adapted harness:
  - the fake answers the `build-inputs-hash` label and the core's one-line socket query;
  - synthetic installations copy the core and the agent part.
- The core prints no help for agent variables, so the agent part defines `agent_help`.
- `/run` is not writable by the session user under the core (L7).
- ShellCheck reports the agent part's data as unused; a `shell=bash` directive with `SC2034` and `SC2154` disabled keeps the file clean (Pi). The core and the launcher fixtures report warnings when checked alone; that is a reference matter.

## Goals / Non-Goals

**Goals:**
- OpenCode runs entirely on the shared core. Its own launcher code is the entry script and `agent/launcher.sh`.
- No OpenCode launcher behavior disappears without being either a recorded visible change or a shared test.

**Non-Goals:**
- Changing the OpenCode image contents, the OpenCode version, the policy inventories or the authentication methods.
- Changing reference files inside this repository. A defect found here is fixed in `sandbox-container` and arrives by a tag.

## Decisions

1. **Adopt with the tool, straight from `sandbox-ref-21` to `sandbox-ref-25`.**
   - Before running it, save the current `opencode-container.sh` and `tests/test_wrapper.py` outside the repository as the old-test baseline.
   - The dry run must list exactly the plan in "Context". `--apply` switches to the branch `adopt-sandbox-ref-25`.
   - Then add `launcher` to `CLOSED_DIRECTORIES` in `tests/test_reference_copy.py` and fix the parity rows by hand.

2. **Entry script, agent part and profile.**
   - `opencode-container.sh` is the reference `sandbox-container.sh`, with only the wrapper name changed. `opencode-wrapper` is deleted.
   - `agent/profile.json` adds `native.exec_tmp: true` and declares no `native.exec` (the default `/usr/local/bin/opencode` is where the image installs OpenCode).
   - `agent/launcher.sh` declares:
     - the profile values, with `AGENT_SHARED_DIRS=(.local/share/opencode .cache/opencode .local/state/opencode)`, `AGENT_PRIVATE_SHARED_DIRS=1`, `AGENT_EXEC=/usr/local/bin/opencode` and `AGENT_EXEC_TMP=1`;
     - `AGENT_INSTALL_FILES=()`;
     - `AGENT_CREDENTIALS=(anthropic-api=ANTHROPIC_API_KEY openai-api=OPENAI_API_KEY openrouter-api=OPENROUTER_API_KEY opencode-zen=OPENCODE_API_KEY)`;
     - `AGENT_POLICY_HOSTS` for the four base profiles;
     - `AGENT_SESSION_ENV` with the four XDG bases below `/opencode-home`, and the same four names in `AGENT_RESERVED_ENV`;
     - `AGENT_RESTRICTED_ENV` with `OPENCODE_DISABLE_AUTOUPDATE`, `_DEFAULT_PLUGINS`, `_LSP_DOWNLOAD`, `_MODELS_FETCH` and `_SHARE` set to `1`;
     - empty provider and unset arrays;
     - a ShellCheck directive as in Pi.
   - Hooks:
     - **`agent_validate`:** before any engine or state operation:
       - `OPENCODE_CONTAINER_PROVIDER`, when set, is one of the seven providers or `none`. In provider mode it must be unset, `none` or the provider of the selected `network_profile`.
       - With `OPENCODE_CONTAINER_AGENTS_DIR` or `OPENCODE_CONTAINER_SYSTEM_CONFIG` exactly `1`, it resolves `~/.agents` or `/etc/opencode` physically and requires a directory. Otherwise it stops, naming the variable and the path.
       - With `OPENCODE_CONTAINER_YOLO` enabled outside shell mode and a nonempty `OPENCODE_PERMISSION`, it stops.
     - **`agent_mounts`:** `ro:<physical ~/.agents>:<home>/.agents` and `ro:<physical /etc/opencode>:/etc/opencode` with the exact opt-ins.
     - **`agent_environment`:**
       - names `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`, `OPENCODE_SERVER_USERNAME` and `OPENCODE_SERVER_PASSWORD` in every mode;
       - adds the four forwarded `OPENCODE_DISABLE_*` switches in unrestricted mode only, because restricted modes reserve them;
       - in unrestricted mode, adds the variable set of the selected `OPENCODE_CONTAINER_PROVIDER`;
       - in restricted modes the core forwards the selected profile's credential, so the hook adds none.
     - **`agent_approval_bypass`:** `agent_bypass_env=('OPENCODE_PERMISSION={"*":"allow"}')`. The core never calls it in shell mode or the qualification probe, and the bypass value follows forwarded variables, so it wins.
     - **`agent_help`:**
       - documents `OPENCODE_CONTAINER_YOLO`, `OPENCODE_CONTAINER_PROVIDER` with its variable sets, `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG`;
       - documents the provider credential of each policy profile;
       - names the restricted OpenCode settings.

   Alternative rejected: keeping the notice that names credentials earlier releases forwarded. It describes a change from an unreleased version, like the version-variable notices U2 removes, so it goes with them, as Pi's gitconfig migration notice did. Keeping it would also need the hook to read the core's `OPENCODE_CONTAINER_ENV_VARS` setting, which the hook interface does not expose.

3. **State follows the core.**
   - The four shared OpenCode directories stay the default. `OPENCODE_CONTAINER_CONFIG_DIR` replaces `~/.config/opencode`, and a nonempty `OPENCODE_CONTAINER_STATE_DIR` selects an isolated home.
   - `OPENCODE_CONTAINER_READONLY_STATE` is new for OpenCode.
   - Isolated-home children must be contained and private (M4).

4. **Old tests gate the deletion.**
   - **Setup:** the saved `tests/test_wrapper.py`, with its embedded fake engine, runs against the new entry script and core. The 69 cases stay unchanged; only the harness is adapted, as in the earlier adoptions.
   - **Outcomes:** every failing case is resolved in exactly one way:
     - **(a) Visible change.** The failure matches a row of the contract's "Visible changes" list (U1, U2, U3, U6, U7, U8, U11, U12, U13, U14, U15, U16, U17, U18, M4, H-a, the phase 1-2 and phase 6 rows for OpenCode, the low findings, L7), or the dropped credential notice of decision 2. The case is dropped.
     - **(b) Lost behavior.** The work stops. The behavior and a shared case go into `sandbox-container` through a reference change and a new tag, and this change then adopts that tag.
     - **(c) OpenCode-only behavior.** The case stays in the reduced `tests/test_wrapper.py`.
   - **Record:** passing shared and duplicate cases are dropped. The 26 "to verify at adoption" cases are resolved by name, and the table goes into `docs/validation.md`.

5. **Reduced `tests/test_wrapper.py`.** It uses the shared `tests/fake_podman.py` and the real `agent/launcher.sh`. It covers:
   - help: the provider hosts of the four profiles and OpenCode's variables, without Podman;
   - `OPENCODE_CONTAINER_PROVIDER`:
     - each variable set in unrestricted mode;
     - `none` and unset forwarding nothing, with no notice;
     - invalid values stopping before engine queries;
     - the provider-mode match against the network profile;
   - the native variables by name in every mode, with the `OPENCODE_DISABLE_*` switches forwarded only in unrestricted mode;
   - the restricted switches winning over a toolchain and `OPENCODE_CONTAINER_ENV_VARS` in offline and provider mode;
   - the fixed XDG bases, also against host `XDG_*_HOME` and `OPENCODE_CONTAINER_ENV_VARS`;
   - the integrations:
     - no mount without the exact `1`;
     - the physical directories mounted read-only with it;
     - the refusal of a missing directory before any engine query or state creation;
     - `~/.claude` never mounted;
   - YOLO:
     - `OPENCODE_PERMISSION={"*":"allow"}` for enabled values only, with otherwise unchanged engine arguments;
     - none in shell mode or the qualification probe;
     - the refusal of invalid values and of a host `OPENCODE_PERMISSION`;
   - each policy profile's credential in provider mode, none in offline mode, and an `OPENCODE_CONTAINER_ENV_VARS` attempt to forward another profile's key;
   - every outcome (c) from decision 4.

6. **Wrapper-owned tests and scripts follow the earlier adoptions.**
   - **`tests/run-runtime.sh`:**
     - `--wrapper` runs `test_launcher.py` and `test_wrapper.py`;
     - `--shared` also runs `test_launcher`.
   - **`tests/test_runtime.py` and `tests/image-smoke.sh`:**
     - `/run` noexec, 32 MiB and not writable by the session user;
     - `/tmp` and the shared-state home executable 512 MiB, `/var/tmp` noexec;
     - the session listing uses the session ownership label instead of `io.opencode-container.managed`;
     - the `opencode-wrapper` case is removed;
     - `OPENCODE_CONTAINER_READONLY_STATE`.
   - **`tests/test_network_runtime.py`:**
     - it installs `agent/launcher.sh` and `launcher/core.sh`;
     - it supplies the provider settings to the delegation grid.
   - **`tests/test_setup_runtime.py`:** its shim answers only the `{{.Id}}` inspection; setup builds through the wrapper and the built image carries the label.
   - **`tests/test_setup_wrapper.py`:** covers the provider default.
   - OpenCode has no `test.sh` or CI workflow; none is added.

7. **Documentation.**
   - **README:**
     - help and first steps without migration history;
     - network modes and the provider default;
     - state, read-only state and the isolated home, and temporary storage;
     - the build-only operation and stale images;
     - environment, `OPENCODE_CONTAINER_PROVIDER` and credentials;
     - shell mode and YOLO;
     - the removed names in one sentence;
     - a shared components section naming the core.
   - **Other files:**
     - `AGENTS.md` describes the entry script and the agent part;
     - `docs/setup.md` follows the provider default and the wrapper build.
   - **Parity table:**
     - the reference, Claude, Codex, Antigravity and Pi rows are copied from their repositories;
     - the OpenCode row says it adopted `sandbox-ref-25`.

     After the merge, the OpenCode row is copied into `sandbox-container`, `claude-container`, `codex-container`, `antigravity-container` and `pi-container`.

8. **Validation scope.** The launcher, installation manifest, build label and qualification identity all change, so validation covers the full set:
   - the unit discovery in the disposable test container;
   - `bash tests/run-runtime.sh` with `--wrapper`, `--shared`, `--setup`, `--setup-runtime`, `--qualification`, `--network` and `--guard`;
   - the default runtime run against an image rebuilt with the build-only operation;
   - `git diff --check` and ShellCheck on the entry script and the agent part;
   - `tests/test_reference_copy.py` with host Python next to the `sandbox-container` checkout.

## Risks / Trade-offs

- **[Decision 4 finds a lost behavior]** → Implementation pauses for a reference change and a new tag. The most likely areas are the integration mounts with an isolated home and the native-variable forwarding order against `OPENCODE_CONTAINER_ENV_VARS`.
- **[Every prepared image lacks the build label]** → Intended (U8). Test images and installations are rebuilt with `--container-build` or `--container-setup`.
- **[Scripts calling `opencode-wrapper` or relying on `--container-build` starting a session stop working]** → Intended (U2, U3). The README lists the replacements.
- **[Installed qualification reports no longer match]** → The operator runs `--container-setup` on the three reference hosts after the merge.

## Migration Plan

1. Commit this change directory on `main`, save the old-test baseline, then dry-run and apply the propagation (branch `adopt-sandbox-ref-25`).
2. Write the entry script, the agent part and the profile change. Run the old tests (decision 4) and resolve every failure before touching `tests/test_wrapper.py`.
3. Reduce the wrapper tests, update the runtime tests, scripts and documentation, validate, and merge into `main`.
4. The operator pushes and runs `--container-setup` on the three hosts. The change is archived with spec sync.

Rollback: before the merge, delete the branch. After the merge, revert the merge commit.
