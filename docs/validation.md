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

## Common specification names: 2026-11-09

The OpenSpec capabilities were renamed to the scheme shared by the five wrappers (Wave 1, `sandbox-ref-2`). Requirements and scenarios are unchanged; only directory names and spec titles changed. Earlier sections and archived changes keep the names that were current at the time.

| Previous name | Current name |
| --- | --- |
| `wrapper-interface` | `container-launcher` |
| `session-lifecycle` | `container-session` |
| `engine-authority` | `container-podman-access` |
| `sandbox-storage` | `container-isolation` |

The evidence file was renamed from `docs/sandbox-acceptance.md` to `docs/validation.md`, the common name across the five wrappers; its earlier content is unchanged.

`openspec validate --specs` passed: 4 specs, 0 failures.

## Narrowed exposed state (A06, A07): 2026-11-09

Change `narrow-exposed-state` (Wave 2). Host: rootless Podman 4.9.3 server.
Images: session image `localhost/opencode-sandbox:1.18.3-node-1000-1000`
(`36a4ca917807`, unchanged by this change), runner `localhost/claude-code:latest`
(`7cd81e8ccd06`). No credentials, provider login or model requests were used;
every credential value was synthetic.

Behavior changes:

- `~/.claude` is never mounted. `~/.agents` and `/etc/opencode` are mounted
  read-only only with exact `OPENCODE_CONTAINER_AGENTS_DIR=1` and
  `OPENCODE_CONTAINER_SYSTEM_CONFIG=1`. An opt-in for a missing directory
  stops before engine queries.
- Provider variables are forwarded only for `OPENCODE_CONTAINER_PROVIDER`.
  GitHub tokens and other providers' keys are no longer forwarded by default.
  Extra names come from `OPENCODE_CONTAINER_ENV_VARS`. When no provider is
  selected, a one-line notice names formerly forwarded variables that are set,
  without their values.

Provider metadata source: the `env:[...]` provider entries embedded in
`/usr/local/bin/opencode` of `ghcr.io/anomalyco/opencode:1.18.3`, read on
2026-11-09 with the network disabled. `AWS_SESSION_TOKEN` and `OPENAI_BASE_URL`
are read by the same binary and were already forwarded, so they remain in their
profiles. OpenCode's `azure` provider reads `AZURE_RESOURCE_NAME` and
`AZURE_API_KEY`; the previously forwarded `AZURE_OPENAI_*` names are covered only
by the migration notice. Google Vertex needs a host credentials file that is not
mounted and is unsupported.

| Check | Result |
| --- | --- |
| Baseline wrapper suite before the change | 19 tests, OK |
| `tests/test_wrapper.py` after the change (runner container) | 26 tests, OK |
| Full unit discovery (`test_*.py`; runtime tests skipped without opt-in) | 37 tests, OK (11 skipped) |
| `bash tests/run-runtime.sh` (real rootless engine) | 11 tests, OK; OpenTUI welcome prompt observed |
| `bash -n`, ShellCheck (`koalaman/shellcheck:stable`), `git diff --check` | Passed |
| Test-owned managed containers after the runs | None |

New wrapper cases:
- `~/.claude` containing `.credentials.json` is never in the create arguments;
- integrations require exact `1`, and a missing opted-in directory fails with no
  engine call or state;
- the matrix over all eight provider values;
- unsupported values (empty, `Anthropic`, `vertex`, a list, `google-vertex`);
- the notice: present, single, value-free, suppressed by `none` or a provider,
  and excluding listed names;
- extra names with deduplication, invalid tokens and reserved names that leave
  `CONTAINER_HOST` unset;
- help listing the controls.

The real-engine check confirmed:
- `$HOME/.claude` and `$HOME/.agents` are absent by default, and `.agents` is
  read-only with the opt-in;
- with `openai` only the synthetic `OPENAI_API_KEY` and the listed
  `DATABASE_URL` arrive, while `ANTHROPIC_API_KEY`, `GH_TOKEN` and an unlisted
  variable do not;
- with no provider the notice names `OPENAI_API_KEY` without its value.

Initial failures and reruns (all in the tests, not the wrapper):
- the new assertions expected only `LANG` among base names, but the runner
  environment also supplies `TERM`, which is in the unchanged base allowlist,
  so the helper now ignores both;
- refusal subtests reused the log and home of an earlier successful run and
  now use fresh ones.

Unit suites run in a runner container with an executable tmpfs `/tmp`, because
the agent sandbox mounts `/tmp` `noexec` and cannot bind Unix sockets on its
workspace filesystem.

## Common wrapper baseline (A01, A02, A08, A09): 2026-11-09

Change `align-wrapper-baseline` (Wave 2). Host: rootless Podman 4.9.3 server.
Session image `localhost/opencode-sandbox:1.18.3-node-1000-1000` (`36a4ca917807`)
rebuilt from the renamed `Containerfile` with an identical ID, runner
`localhost/claude-code:latest` (`7cd81e8ccd06`). No credentials, provider login
or model requests were used.

User-facing changes:
- `opencode-container.sh` is the entry point, and `opencode-wrapper` is a
  deprecated shim that warns once and execs it;
- `Containerfile`/`.containerignore` replace `Dockerfile`/`.dockerignore`;
- `OPENCODE_CONTAINER_IMAGE` is new;
- `OPENCODE_CONTAINER_VERSION` replaces `OPENCODE_VERSION`, which is still read
  with a warning;
- `OPENCODE_CONTAINER_YOLO` is new;
- labels move to `io.opencode-container.*`.

Measured OpenCode 1.18.3 facts, on `ghcr.io/anomalyco/opencode:1.18.3` with
the network disabled:
- `opencode --auto debug paths` and an unknown flag before a subcommand fail.
  `--auto`, `--yolo` and `--dangerously-skip-permissions` exist only on the
  default interface and `run`.
- `OPENCODE_PERMISSION` is parsed as JSON and merged after the configuration
  files. With a configuration containing `bash: {"rm *": "deny"}` and
  `edit: "ask"`, `opencode debug agent build` lists
  `{"permission":"*","action":"allow"}` after the user rules. YOLO therefore
  overrides configured `ask`/`deny` rules, as the other wrappers' native bypass
  flags do.

| Check | Result |
| --- | --- |
| `tests/test_wrapper.py` (runner container) | 30 tests, OK (4 new: shim, labels, version/image, YOLO) |
| Full unit discovery (runtime tests skipped without opt-in) | 43 tests, OK (13 skipped) |
| `bash tests/run-runtime.sh` (real rootless engine) | 13 tests, OK; OpenTUI welcome prompt observed |
| `bash -n` (wrapper, shim, entrypoint), ShellCheck on all shell files, `git diff --check` | Passed |
| `AGENTS.md` build command | Succeeded with the renamed recipe |
| Managed containers after the runs (old and new labels) | None |

New real-engine checks:
- `opencode debug config` in a real session reports permission
  `{"*":"allow"}` with YOLO, and not without it;
- a session started through the `opencode-wrapper` shim carries only
  `io.opencode-container.*` labels, exits with the shell status, prints one
  deprecation warning and leaves no container;
- the build-context probe passes with `Containerfile` and `.containerignore`.

Initial failures and reruns:
- An earlier editing attempt failed before changing any file, because a nested
  heredoc ended the outer one.
- The first shim runtime check could not find the session: Podman label
  filters cannot express the test workspace path, which contains a comma. The
  check now filters on `io.opencode-container.managed=true` and compares the
  workspace label in Python.

README and `AGENTS.md` were reorganized into the common section structure. Every
statement of the previous files was checked against the new text with a
sentence-level comparison. The remaining differences are retitled sections,
statements moved into tables, and the intended renames.
