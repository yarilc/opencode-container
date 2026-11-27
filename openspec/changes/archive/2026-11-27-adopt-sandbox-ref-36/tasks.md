# Tasks

Verification for this change runs in the current development session. Record the
outcome of every check supported here and the reason for any unavailable or
environment-dependent check. Out-of-session Linux/WSL and Windows runs follow
closure.

## 1. Adopt the shared reference

- [x] 1.1 Run `python3 -I tools/propagate.py ../opencode-container sandbox-ref-28 sandbox-ref-36`
  from `sandbox-container` against a clean target worktree (preserving this
  change's planning artifacts under `openspec/changes/adopt-sandbox-ref-36/`),
  then rerun with `--apply`. Verify the applied file counts (29 modified, 17
  added, 0 removed) and the 19 review lines against `design.md`, confirm
  `tests/test_reference_copy.py` pins `sandbox-ref-36`
  (`ce2c9d28873838a4ac541da34edaf7d8b5264be4`) with all 92 entries, and verify
  `python3 -B -m unittest tests.test_reference_copy tests.test_alignment` passes.
- [x] 1.2 Update `tests/run-runtime.sh` to drop `OPENCODE_CONTAINER_PODMAN_SOCKET`
  and select the Unix socket from `CONTAINER_HOST` or the default runtime
  directory, and align the `--shared` module list with `tests/test_alignment.py`
  (including `test_engine`, `test_toolchains`, `test_windows_bootstrap`, and
  `test_windows_enter`) while preserving OpenCode's image-pin and guarded
  fixture runs. Verify with `bash -n tests/run-runtime.sh` and compare the
  selected modules against `tests/test_alignment.py`.

## 2. Update OpenCode launch, setup, and core documentation

- [x] 2.1 In `tests/test_wrapper.py`, remove the synthetic
  `OPENCODE_CONTAINER_PODMAN_SOCKET` setup and stale `OPENCODE_CONTAINER_PODMAN`
  fixture entry while retaining OpenCode's help, fixed XDG bases, provider
  variable allowlists, native variables, read-only `.agents` and
  `/etc/opencode` integrations, `OPENCODE_CONTAINER_YOLO` rules, four policy
  profiles, and fixed qualification probe checks (ensuring the synthetic
  `network/control.py` stub matches `sandbox-ref-36`). Review `agent/launcher.sh`
  for stale delegation comments. Verify with `python3 -B -m unittest tests.test_wrapper`
  against private native executable `SANDBOX_TEST_TMPDIR`.
- [x] 2.2 In `tests/test_setup_wrapper.py` and `tests/test_setup_runtime.py`,
  remove the host Podman delegation prompt/answer and `podman:` summary
  assertions, isolate `XDG_RUNTIME_DIR` in synthetic setup tests, and update
  assertions for schema 3 preferences (including the prepared engine image). In
  `tests/test_setup_runtime.py`, extend the Podman shim to route prepared
  `localhost/opencode-cli-engine:latest` lookups without mutating operator
  images, pass a host-visible CA fixture in native storage, and track
  disposable runtime, proxy, guard-toolchain, and engine tags for cleanup while
  preserving OpenCode's `1.19.5` version, failed-update rollback, and shell
  checks. Verify `python3 -B -m unittest tests.test_setup_wrapper` passes on
  private native storage and confirm `tests/test_setup_runtime.py` compiles and
  discovers cleanly.
- [x] 2.3 Update `README.md`, `AGENTS.md`, `docs/setup.md`, and current prose in
  `docs/network-contract.md` across all review lines to replace host Podman
  delegation guidance with the private session engine, legacy
  `OPENCODE_CONTAINER_PODMAN=1` refusal and migration flow, schema 3 setup,
  aligned shared test inventory, and updated Windows entry behavior, while
  preserving OpenCode's `1.19.5` / OpenSpec `2.0.0` pins, four provider
  profiles, native variables, and optional mounts. Verify no stale host-socket
  delegation instructions remain in current documentation and compare updated
  text against `--container-help` output and `tests/test_setup_wrapper.py`.

## 3. Update session engine, containment, budget, and toolchain acceptance

- [x] 3.1 In `tests/test_runtime.py`, remove `test_child_container_host_bind`,
  legacy `OPENCODE_CONTAINER_PODMAN=1` branches in
  `test_effective_hardening_and_budgets` and `test_tools_without_capabilities`,
  and host-socket delegation assertions in
  `test_containerized_caller_with_remapped_socket` (updating it or replacing it
  to assert no host socket and refusal of `OPENCODE_CONTAINER_PODMAN=1`). Extend
  `test_image_default_host_is_removed` to confirm both `CONTAINER_HOST` and
  `DOCKER_HOST` are cleared when no engine starts, add per-container process
  rlimit coverage, and port the reference `SessionEngineTests` patterns using
  `localhost/opencode-cli-engine:latest` (workspace bind with caller-owned
  files, no-engine mode without image toolchains, concurrent engine isolation,
  engine process rlimit, cgroup delegation, and nested systemd containers) while
  retaining OpenCode's `1.19.5` version, `test_yolo_resolved_permission`,
  `test_opentui_renderer`, and `test_mounts_state_identity_and_entrypoint`.
  Verify `tests/test_runtime.py` compiles and test discovery lists every new and
  retained case cleanly.
- [x] 3.2 In `tests/test_network_runtime.py`, update the fixture installation in
  `setUp()` to copy `setup/engine.py`, every entry of `engine.INPUTS`, and the
  prepared seccomp profile when exercising the engine. Replace restricted-only
  delegation checks with exact `OPENCODE_CONTAINER_PODMAN=1` refusal across
  `offline`, `provider`, and `unrestricted` modes plus ignored non-enabling
  values. Add `test_offline_session_engine_has_no_external_path` and
  `test_image_recipe_check_runs_without_network`, and retain OpenCode's four
  controlled provider TLS binding checks and synthetic chat-API tool call.
  Verify `tests/test_network_runtime.py` compiles and test discovery lists all
  cases cleanly.
- [x] 3.3 Align budget and guarded-terminal assertions in
  `tests/test_network_runtime.py` with `sandbox-ref-36`: evaluate agent and
  proxy budgets according to host cgroup controller delegation and effective
  rlimit fallback (including proxy startup beside containers exceeding its
  process budget), apply `tests/guard_terminal_probe.py` to guarded terminal
  cases (`test_guarded_arguments_stdin_status_and_tty_both_state_modes` TTY
  sub-step and `test_opentui_starts_and_quits_under_the_guard`) while keeping
  pipe cases independently runnable, and enforce bounded waits and owned cleanup
  on interrupted fixture processes. Verify with Python syntax check, unit
  discovery, and running all locally available budget, engine, and qualification
  unit suites.
- [x] 3.4 Document the container test workflow, shipped toolchain catalog,
  host-side HTTPS archive fetching, image recipes, read-only `.images` store,
  Windows drive-path translation, engine image preparation (`localhost/opencode-cli-engine:latest`),
  read-only `/sys`, and nested systemd prerequisites in `README.md` and
  `docs/setup.md`. Verify examples against `--container-toolchain` help output
  and the locally runnable `tests.test_toolchains` and `tests.test_engine` unit
  suites.

## 4. Verify and record the adoption

- [x] 4.1 Run all checks supported in the current session:
  `tests.test_reference_copy`, `tests.test_alignment`, full non-runtime unit
  discovery (`test_wrapper`, `test_setup_wrapper`, `test_launcher`,
  `test_setup`, `test_engine`, `test_toolchains`, `test_qualification`,
  `test_session`, `test_guard`, `test_platform`, `test_windows_bootstrap`,
  `test_windows_enter`, `test_image_pins`, and remaining shared modules) using
  private native executable storage, `bash -n` on all tracked shell scripts,
  `py_compile` on updated Python tests, `git diff --check`, and
  `openspec validate adopt-sandbox-ref-36 --strict`. Refresh the `## Purpose`
  paragraph of `openspec/specs/toolchain-library/spec.md` to refer to image
  toolchains and the private session engine instead of host Podman access, and
  preview the spec merge in a disposable copy to verify `container-podman-access`
  is retired, `session-container-engine` has all 20 requirements, and OpenCode's
  existing contracts survive. Record the status of unavailable `shellcheck` and
  `pwsh` tools.
- [x] 4.2 Generate the `sandbox-container` adoption checklist for
  `opencode-container`, record real-engine and image availability (noting any
  unavailable `localhost/opencode-cli:latest`,
  `localhost/opencode-guard-toolchain:development`, or host-service suites),
  and verify `tests/run-runtime.sh` preflight behavior as supported here.
- [x] 4.3 Record the adopted tag (`sandbox-ref-36`), in-session test results,
  environmental exclusions, and pending post-closure checks under a new
  `## Adoption of sandbox-ref-36` section in `docs/validation.md`, and update
  OpenCode's parity row in `docs/network-contract.md` while preserving all
  historical rows and other wrappers' rows verbatim. Verify that synthetic,
  real-engine, authenticated, and Windows check statuses are accurately
  distinguished.

## Workflow follow-up

- Sync specs, archive `adopt-sandbox-ref-36`, and commit on `main` once
  in-session tasks and verification are complete. Propagate the updated
  OpenCode (and Antigravity) parity rows to `sandbox-container` and sibling
  wrappers in a separate cross-repository parity step.
- After closure, run the full Linux/WSL adoption suite from `sandbox-container`:
  `bash tools/adoption-run.sh /mnt/d/Workspace/sandboxes/opencode-container sandbox-ref-28 sandbox-ref-36`,
  and record the built runtime/engine image IDs, `io.containers.capabilities`
  label, suite outcomes, and any host-specific skips in `docs/validation.md`.
- After closure, rerun managed `--container-setup` on Windows PowerShell 5.1
  and run `.\tools\windows-validate.ps1 -Checkout <the Windows checkout>` from
  `sandbox-container`, recording saved-delegation refusal, library-image
  session results, and interactive OpenTUI checks.
- Open a separate OpenSpec change for any production defect discovered during
  post-closure Linux/WSL or Windows validation.
