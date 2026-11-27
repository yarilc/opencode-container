# Design

## Context

See `proposal.md` for motivation and scope. `opencode-container`'s reference manifest pins `sandbox-ref-28` (`ba1ef1428a57625b70bb45d55cade5f08f46eecc`). Its shared launcher still admits host Podman socket delegation in unrestricted mode, and OpenCode's own wrapper, runtime, setup, and network tests exercise `OPENCODE_CONTAINER_PODMAN=1`, `OPENCODE_CONTAINER_PODMAN_SOCKET`, the old delegation prompt, and schema 2 setup preferences.

A dry run of `python3 -I tools/propagate.py ../opencode-container sandbox-ref-28 sandbox-ref-36` from `sandbox-container` reported 29 modified shared files, 17 added shared files (`launcher/engine/*`, `setup/engine.py`, `setup/toolchain-catalog/*.json`, `tests/guard_terminal_probe.py`, `tests/test_engine.py`), 0 removals, 0 unadopted files, current-state version updates in `README.md`, `AGENTS.md`, `docs/setup.md`, and `docs/network-contract.md`, and 19 review lines in OpenCode-owned files. `opencode-container.ps1` and `.gitattributes` are already byte-identical between `sandbox-ref-28` and `sandbox-ref-36`.

## Goals / Non-Goals

**Goals:**
- Make all 92 shared files in `launcher/`, `network/`, `setup/`, and shared tests byte-identical to `sandbox-container` tag `sandbox-ref-36` (`ce2c9d28873838a4ac541da34edaf7d8b5264be4`).
- Adapt OpenCode's own test runner, wrapper/setup/runtime/network suites, documentation, and OpenSpec capability boundaries to replace host Podman delegation with the private session container engine and new toolchain/budget/terminal-probe contracts.
- Preserve OpenCode's pinned runtime image (`localhost/opencode-cli:latest`, OpenCode `1.19.5`, OpenSpec `2.0.0`), `agent/profile.json`, `agent/launcher.sh`, `agent/policies/default.json` (`anthropic-api`, `openai-api`, `openrouter-api`, `opencode-zen`), `OPENCODE_CONTAINER_YOLO`, `OPENCODE_CONTAINER_PROVIDER`, and optional read-only integrations (`OPENCODE_CONTAINER_AGENTS_DIR`, `OPENCODE_CONTAINER_SYSTEM_CONFIG`).

**Non-Goals:**
- Adopting `add-read-only-dependency-mirror` (landed on `sandbox-container/main` after `sandbox-ref-36`) or changing reference tooling in `sandbox-container`.
- Modifying OpenCode's pinned CLI/OpenSpec versions, base image digest, provider policy hosts, or `agent/launcher.sh` behavior (beyond removing stale delegation prose in docs/comments if needed).
- Running cross-repo parity updates or out-of-session WSL/Linux/Windows production checks inside this change (handled as follow-up after closure per `AGENTS.md`).

## Decisions

1. **Propagate mechanically from `sandbox-ref-36` via `tools/propagate.py`.**
   Run `tools/propagate.py` against a clean target worktree (preserving this change's planning artifacts) first as a dry run and then with `--apply` so the tool owns the 46 shared file updates/additions, the 92-file `tests/test_reference_copy.py` manifest, and current-state version tags. Then inspect all 19 review lines in OpenCode-owned files (`AGENTS.md`, `README.md`, `agent/launcher.sh`, `docs/network-contract.md`, `docs/setup.md`, `tests/test_network_runtime.py`, `tests/test_setup_runtime.py`, `tests/test_setup_wrapper.py`, `tests/test_wrapper.py`).
   *Alternative considered:* Manually cherry-picking commits from `sandbox-container`. Rejected because `tests/test_reference_copy.py` enforces exact byte identity with the tag and `tools/propagate.py` avoids missed files or manifest drift. Any shared defect belongs in `sandbox-container` under a new tag.

2. **Keep session-engine policy entirely in shared code.**
   Guided setup builds `localhost/opencode-cli-engine:latest` (derived automatically from `agent/profile.json`'s `localhost/opencode-cli:latest` runtime image name via shared naming rules), writes the derived seccomp profile, and persists schema 3 preferences. The launcher starts a per-session rootless engine on `tcp://127.0.0.1:2375` inside the session network namespace only when the enabled toolchain library contains at least one image entry; it mounts only the workspace and the read-only `.images` store, declares `SETUID,SETGID,SYS_CHROOT,CHOWN` in `io.containers.capabilities`, and drops to the unprivileged `podman` user after startup. See `specs/session-container-engine/spec.md` for full requirements.
   *Alternative considered:* Adding OpenCode-specific engine overrides or keeping a fallback host-socket switch. Rejected because security boundaries and engine lifecycle must stay uniform across all wrappers and host delegation is intentionally removed in every mode.

3. **Preserve OpenCode's hooks and keep `tests/test_wrapper.py` OpenCode-scoped.**
   `agent/launcher.sh` and `agent/profile.json` keep fixed XDG bases under `/opencode-home`, `native.exec_tmp: true` for OpenTUI, the five restricted `OPENCODE_DISABLE_*` switches, the provider variable allowlists, read-only `.agents` and `/etc/opencode` opt-ins, and `OPENCODE_CONTAINER_YOLO` (`OPENCODE_PERMISSION={"*":"allow"}`). In `tests/test_wrapper.py`, remove the synthetic `OPENCODE_CONTAINER_PODMAN_SOCKET` setup and stale `OPENCODE_CONTAINER_PODMAN` fixture key; rely on the shared `tests/test_launcher.py` for the full legacy delegation refusal grid while verifying OpenCode's own hooks and qualification probe remain intact.
   *Alternative considered:* Duplicating the delegation refusal grid inside `tests/test_wrapper.py`. Rejected because `specs/shared-launcher/spec.md` scopes `tests/test_wrapper.py` to OpenCode-only behavior.

4. **Adapt `tests/run-runtime.sh` and OpenCode's runtime, setup, and network suites.**
   - `tests/run-runtime.sh`: drop `OPENCODE_CONTAINER_PODMAN_SOCKET` lookup (use `CONTAINER_HOST` or default runtime socket) and align the `--shared` module list with `tests/test_alignment.py` (including `test_engine`, `test_toolchains`, `test_windows_bootstrap`, `test_windows_enter`).
   - `tests/test_runtime.py`: remove `test_child_container_host_bind`, legacy `OPENCODE_CONTAINER_PODMAN=1` branches in `test_effective_hardening_and_budgets` and `test_tools_without_capabilities`, and delegated socket assertions in `test_containerized_caller_with_remapped_socket`; add session-engine acceptance using `localhost/opencode-cli-engine:latest` (workspace bind with caller-owned output, no-engine check clearing both `CONTAINER_HOST` and `DOCKER_HOST`, concurrent session isolation, engine/agent per-container process rlimit checks, and cgroup delegation/nested-systemd checks matching the reference patterns) while preserving OpenCode's `1.19.5` version, `test_yolo_resolved_permission`, `test_opentui_renderer`, and `test_mounts_state_identity_and_entrypoint`.
   - `tests/test_network_runtime.py`: copy `setup/engine.py` and `engine.INPUTS` (plus prepared seccomp profile when exercising the engine) into `self.install`; replace restricted-only delegation checks with exact `OPENCODE_CONTAINER_PODMAN=1` refusal in all modes and ignored non-enabling values; add `test_offline_session_engine_has_no_external_path`, `test_image_recipe_check_runs_without_network`, controller-aware agent/proxy budget and rlimit assertions, and `tests/guard_terminal_probe.py` for guarded terminal cases (`test_guarded_arguments_stdin_status_and_tty_both_state_modes` TTY sub-step and `test_opentui_starts_and_quits_under_the_guard`) while keeping pipe cases independently runnable and keeping OpenCode's synthetic chat-API tool call and four provider profile TLS binding checks.
   - `tests/test_setup_wrapper.py` and `tests/test_setup_runtime.py`: remove the delegation prompt/answers, isolate `XDG_RUNTIME_DIR` in synthetic setup tests, assert schema 3 saved preferences (including engine image), route prepared engine image lookups in the real setup shim without mutating operator images, pass a host-visible CA fixture in native storage, and track disposable engine image tags for cleanup.
   *Alternative considered:* Keeping hardcoded file lists in `tests/test_network_runtime.py`. Rejected because importing `setup/engine.py`'s `INPUTS` prevents drift whenever engine build inputs change.

5. **Retire `container-podman-access` cleanly while preserving launch-engine contracts.**
   Preserve the two non-delegation launch-engine verification requirements (`Verified launch engine` and `Complete launch verification responses`) plus `Leftover delegation opt-in is refused` in `container-launcher`, add the 20-requirement `session-container-engine` capability, and remove all six requirements of `container-podman-access` with `retire_capabilities: true` in `.openspec.yaml`. During implementation, refresh `openspec/specs/toolchain-library/spec.md`'s `## Purpose` paragraph so it describes image toolchains and the private session engine instead of host Podman access. (`openspec/specs/workspace-mounts/spec.md` already has no delegation references.)
   *Alternative considered:* Leaving `container-podman-access` as an empty capability. Rejected because OpenSpec supports capability retirement and keeping an empty Podman-access spec would misstate the security model.

6. **Follow the session-scoped verification model in `AGENTS.md`.**
   Run all checks supported in the development session (`test_reference_copy`, `test_alignment`, host unit suites against private native executable storage, Bash/Python syntax checks, `git diff --check`, `openspec validate`, and a disposable spec-merge preview). Record real-engine, ShellCheck, and PowerShell checks that are unavailable in the session (no `localhost/opencode-cli:latest`, `localhost/opencode-guard-toolchain:development`, `shellcheck`, or `pwsh`) in `docs/validation.md` with their exact reasons and list `tools/adoption-run.sh` and `tools/windows-validate.ps1` under `Follow-up after closure` in `tasks.md`.
   *Alternative considered:* Blocking change closure on host WSL/Windows execution. Rejected because `AGENTS.md` explicitly prohibits tasks from waiting on external environments.

## Risks / Trade-offs

- **[Legacy scripts setting `OPENCODE_CONTAINER_PODMAN=1` fail on upgrade]** → Shared launcher fails early before engine access with an actionable migration message naming `OPENCODE_CONTAINER_PODMAN=1` and image toolchains; `--container-setup` migrates saved schema 2 preferences to schema 3 automatically.
- **[Host cgroup controller delegation and guarded-terminal runtime differences]** → Runtime and network tests query actual controller delegation and process budget mechanism (`cgroup`/`rlimit`/`none`) and gate guarded terminal tests with `guard_terminal_probe.py` so pipe tests still run and host-specific terminal skips record the exact engine error.
- **[Windows bootstrap and engine path changes cannot execute in a Linux session]** → Keep `opencode-container.ps1` and `launcher/windows/*` byte-identical to `sandbox-ref-36`, verify shared Windows unit suites (`test_windows_bootstrap`, `test_windows_enter`) in-session, and run `tools/windows-validate.ps1` on Windows PowerShell 5.1 as post-closure follow-up.
- **[Stale prepared engine images or qualification records on existing installations]** → Document rerunning `--container-setup` after adoption and use `tools/adoption-run.sh` in post-closure validation to verify the tagged engine image ID and `io.containers.capabilities` label.

## Migration Plan

1. Apply the shared files from `sandbox-ref-36`, adapt OpenCode's tests and docs, run all checks supported in the working session, and update `docs/validation.md` and OpenCode's parity row in `docs/network-contract.md`.
2. Archive and merge the change, then run the post-closure Linux/WSL (`tools/adoption-run.sh`) and Windows PowerShell 5.1 (`tools/windows-validate.ps1`) validation checks and propagate the updated parity row across sibling repositories in a separate parity step.
3. On existing managed installations, rerun `--container-setup` (from PowerShell on Windows) to migrate saved preferences to schema 3, build `localhost/opencode-cli-engine:latest`, and refresh qualification records; remove `OPENCODE_CONTAINER_PODMAN=1` from caller scripts and register needed container images via `--container-toolchain add`.
4. To roll back, check out or select the previous trusted `opencode-container` release (`sandbox-ref-28`) and rerun its `--container-setup` to restore compatible managed launch and qualification records.
