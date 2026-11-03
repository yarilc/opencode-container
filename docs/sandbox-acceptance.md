# Sandbox Alignment Acceptance

Change: `align-sandboxing-contracts` (2026-11-03).

## Environment and isolation

Checks ran from a containerized caller using an explicit same-host Unix endpoint.
The launch service reported `true linux true`; its rootless host socket path was
remapped into the caller. The image identity was `node`, UID/GID `1000:1000`,
with tag `localhost/opencode-sandbox:1.18.3-node-1000-1000`.
The production Dockerfile and default OpenCode version remain unchanged.

Synthetic checks use an isolated environment, fake engine, temporary HOME/XDG,
and dummy credentials. Real checks use disposable projects, native Linux state
volumes, explicit test-owned container IDs/labels, and credential-free state.
The runner uses the already available `localhost/claude-code:latest` solely for
Python/Bash/GNU timeout/Podman test tooling. Production OpenCode remains independent
of that image. No user service was started, no host policy weakened, and no
real provider credentials or authentication sessions were imported.

## Commands and results

Static checks (run before suites):

```bash
bash -n opencode-wrapper
bash -n opencode-entrypoint
bash -n tests/run-runtime.sh
bash -n tests/image-smoke.sh
```

ShellCheck is supplied through rootless Podman:

```bash
podman run --rm --volume "$PWD:$PWD:ro" --workdir "$PWD" \
  docker.io/koalaman/shellcheck:stable \
  opencode-wrapper opencode-entrypoint tests/run-runtime.sh tests/image-smoke.sh
```

The current-user production image was built with:

```bash
podman build \
  --tag localhost/opencode-sandbox:1.18.3-$(id -un)-$(id -u)-$(id -g) \
  --build-arg OPENCODE_VERSION=1.18.3 \
  --build-arg USER_NAME=$(id -un) \
  --build-arg USER_ID=$(id -u) \
  --build-arg GROUP_ID=$(id -g) .
```

Synthetic and real evidence are separate:

```bash
python3 -m unittest discover -s tests -p test_wrapper.py -v
./tests/run-runtime.sh
```

| Verification | Result |
| --- | --- |
| Bash syntax (wrapper, entrypoint, runner, smoke script) | PASS |
| ShellCheck via rootless Podman | PASS, no diagnostics |
| Production per-user image build | PASS |
| Synthetic suite | PASS: 19 test methods, 80.176 seconds (with parameterized subtests) |
| Real rootless suite | PASS: 11 test methods, 64.020 seconds |
| Version via normal wrapper entrypoint | PASS: exact `1.18.3` |
| Targeted OpenTUI welcome/terminal-quit recheck | PASS: 21.264 seconds, terminal quit status 130 |
| Wrapper/test-owned container and volume inspection | PASS: no remaining resources |

Built production image ID:
`36a4ca9178074ad28b90e2c67b599604679753776be262693961810a5bd7fce8`.
The renderer transcript was inspected independently and contained the welcome
prompt `Ask anything`, agent/command controls, and version `1.18.3`; it contained
no permission or shared-library load errors. A targeted renderer recheck also
requires successful terminal quit (no forced-cleanup fallback) and confirms the
stronger welcome-prompt assertions.

## Checklist coverage

This table maps the pre-implementation `todo.md` review to independent evidence.
Test names are methods in `tests/test_wrapper.py` and `tests/test_runtime.py`.
Synthetic subtests cover multiple malformed values, modes and signal cases.

| Original checklist item | Synthetic evidence | Real-engine evidence |
| --- | --- | --- |
| Complete launch-engine contract | `test_launch_validation` | Explicit Unix Linux/rootless launch throughout the suite |
| Complete engine responses/status | `test_launch_validation`, `test_socket_validation_and_precedence` | Valid launch and exact selected-service queries |
| Exact disabled-by-default delegation | `test_exact_delegation_and_remapping` | `test_image_default_host_is_removed`, smoke with disabled service access |
| Socket selection/remapping | `test_socket_validation_and_precedence` | `test_containerized_caller_with_remapped_socket`, `test_child_container_host_bind` |
| Preserve host security policy | Hardening assertions in `test_exact_delegation_and_remapping` | Standard-policy startup and socket delegation; actual image smoke verifies capabilities and no-new-privileges |
| Private persistent XDG and HOME | `test_private_xdg_and_umask`, `test_state_files_broken_links_and_resolution`, `test_entrypoint_home` | `test_mounts_state_identity_and_entrypoint`: nonstandard HOME, real entrypoint, four persistent directories |
| Explicit temporary filesystems | `test_tmpfs_and_named_environment` | Image smoke verifies root ro, capacities, modes, nosuid/nodev, executable `/tmp`, noexec `/run` and `/var/tmp`, and fresh mounts next session |
| By-name allowed credentials | `test_tmpfs_and_named_environment` | Allowed synthetic key arrives while unlisted variable remains absent |
| Comma/space physical bind paths | `test_mount_paths_and_boundaries`, socket remapping cases | Workspace path contains spaces/commas; real child binds and remapped sources |
| Bounded atomic reservation | `test_names_failures_and_owned_records` | `test_concurrent_reservation_with_stopped_container`: existing `08`, concurrent `9`/`10`, stopped container preserved |
| Signals and owned cleanup | `test_creation_signals`, attached signal matrix, stalled-create/control tests, application-status cleanup tests | `test_signal_delivery_owned_cleanup_and_stubborn_process`: TERM/INT/HUP, stubborn application, unrelated stopped container survives |
| Stdin independent of TTY | Baseline input and `test_tty_and_mixed_streams` | `test_nonterminal_input_exit_status_and_pty`: pipe/file/EOF/PTY and application 125 |
| Unexpected image-inspection failures | `test_image_inspection_and_build` | Current-user image build and reuse; synthetic failures distinguish status 1 from engine errors |
| Explicit wrapper modes/help | `test_help_and_arguments`, `test_modes` | Shell sessions, PTY, version forwarding, `test_real_worktrees` metadata outside the current directory |
| Default-deny build context | Policy inspected alongside recipe inputs | `test_build_context`: only three root inputs visible, required entrypoint COPY succeeds, forbidden COPY fails |
| Acceptance/documentation | Complete synthetic suite and static checks | Complete real suite, independent version and interactive OpenTUI tests, resource inspection |

## Renderer evidence

`test_version` invokes the wrapper normally and requires exact output `1.18.3`.
`test_opentui_renderer` separately starts the actual OpenTUI in a 110x30 PTY,
responds to terminal queries, observes its rendered welcome interface, sends
terminal interruption to quit, waits for owned cleanup, and checks for no
remaining session container. It uses disposable credential-free HOME/XDG and
explicit auto-update/plugin/model-fetch controls. The ignored local transcript
is `.test-state/renderer-last.txt`. Version output is not used as renderer proof.

## Limits retained

An enforcing SELinux host was not available; tests verify no label disabling or
relabel flags and use the current host's standard policy. Malformed engines,
failed control calls and indefinite stalls are intentionally synthetic probes.
Real acceptance does not claim an engine remains reachable during host failure.
SIGKILL/engine loss can leave resources; diagnostics identify the owned session
for manual inspection. The previously documented Alpine existing-GID collision
is outside this change. Socket access still delegates the service user's full
Podman authority, and by-name forwarding does not hide secrets from engine
inspection or container processes.
