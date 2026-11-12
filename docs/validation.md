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

## Runtime image and session baseline (A03, A04, A05, A11): 2026-11-09

Change `align-runtime-image` (Wave 2). Host: rootless Podman 4.9.3 server.
The new image `localhost/opencode-cli:latest` (`e606ff13a67e`) was built with
`--no-cache` from `Containerfile`. The runner image is
`localhost/claude-code:latest` (`7cd81e8ccd06`). No credentials, provider login
or model requests were used.

Pinned inputs:
- base `docker.io/library/node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`;
- `opencode-ai@1.18.3`;
- `@fission-ai/openspec@1.16.0`.

npm channel facts:
- `npm view opencode-ai@1.18.3` reports a registry SHA-512 integrity and
  exact-version optional platform packages, such as `opencode-linux-x64`
  1.18.3.
- Its postinstall copies the matching binary and selects AVX2 or baseline from
  the build host's CPU.
- The installed binary links only against glibc.
- The build fails unless `opencode --version` and `openspec --version` equal the
  recorded versions.

Baseline before the change, measured in a real session through the runner with
native Linux state, on the per-user Alpine image `36a4ca917807`:
- all five capability sets were zero and `NoNewPrivs` was `1`;
- `memory.max=max`, `pids.max=512`, `cpu.max=max 100000`;
- `HOME` and the XDG bases were host paths;
- missing tools: `bwrap`, `file`, `gawk`, `nano`, `patch`, `python3`, `xz`,
  `zip` and `openspec`.

After the change, in a real session:
- `HOME=/opencode-home`, with the XDG bases below it;
- all capability sets are zero and `NoNewPrivs` is `1`;
- `memory.max=4294967296`, `pids.max=512`, `cpu.max=200000 100000`, and the
  overrides (`1g`, `1.5`, `256`) apply with and without delegation;
- every toolset command is present, OpenCode reports `1.18.3` and OpenSpec
  `1.16.0`.

| Check | Result |
| --- | --- |
| Unit discovery (`test_wrapper.py`, `test_image_pins.py`; runtime skipped without opt-in) | 56 tests, OK (19 skipped) |
| `bash tests/run-runtime.sh` (real rootless engine) | 19 tests, OK |
| Lifetime expiry (`OPENCODE_CONTAINER_RUN_TIMEOUT=3`, `sleep 30`) | Stopped; client status 255; notice printed |
| Process limit 32 | Process creation refused inside the session |
| `bwrap --unshare-all`, Git, OpenSpec, delegated child container | Work without capabilities |
| OpenTUI on glibc in a PTY | Welcome prompt observed; quit cleanly |
| Shared state, ephemeral home, isolated `OPENCODE_CONTAINER_STATE_DIR` persistence | Passed |
| Refused home workspace | Exit 1 before engine use |
| `bash -n`, ShellCheck, `git diff --check` | Passed |
| Test-owned managed containers after the runs | None |

Initial failures and reruns:
- **Build:** the first build failed because the version check created
  `/opencode-home` before the final `mkdir`. The recipe now removes it and
  recreates it with mode 1777.
- **First wrapper run:** after the code change, the existing assertions failed
  as expected, because the fake engine had no budget inspection and the layout
  expectations were stale. Both were updated.
- **Lifetime test:** it assumed that `0007` was accepted. The reference
  validation rejects leading zeros, so the case moved to the rejected set.
- **State inside the workspace:** shared state below the workspace was rejected
  in the old layout only because the mount destinations coincided. With fixed
  destinations below `/opencode-home` it no longer conflicts and is now
  allowed. This keeps the unsafe-workspace override usable from the home
  directory. Isolated state must still not overlap the workspace.
- **Process-limit test:** the first version used Bash background jobs, so a
  refused fork ended the script. It now uses the Python child-process probe
  from the Codex suite.
- **ShellCheck:** it reported SC2015 on two validation lines copied from the
  reference. They are annotated, because `die` must also run when the second
  test fails.

Known limitations:
- The lifetime notice compares whole seconds, so with a 1-second limit a fast
  non-zero exit can print it.
- With keep-id, a caller UID that already exists in the base image shows the
  image user name, for example `node` for UID 1000. `USER` is still the host
  name.
- An image built on an AVX2 host must not be copied to a host without AVX2.

## Network egress port (`add-network-egress`): 2026-11-10

Target: WSL2 kernel 6.6.87.2, Podman client 4.3.1 and server 4.9.3, Netavark.
Image `localhost/opencode-cli:latest` (`e606ff13a67e`), OpenCode 1.18.3; the
platform binary `opencode-linux-x64/bin/opencode` has SHA-256
`fdf58364c969a144fff0ae3a30f2fb6e705ada06864842613de1f9ecc70feb20`.

### Measured OpenCode endpoints (static inventory and logging proxy)

The inventory combines the URL strings in the 1.18.3 binary with credential-free
runs (`opencode models`, `opencode run`, `opencode upgrade`) inside
`--network=none` containers. `HTTPS_PROXY` pointed at a loopback proxy that
logged every request and answered 403. Each run used dummy keys.

| Use | Host | Notes |
| --- | --- | --- |
| Anthropic API | `api.anthropic.com` | `opencode run -m anthropic/...` |
| OpenAI API | `api.openai.com` | `opencode run -m openai/...` |
| OpenRouter | `openrouter.ai` | `opencode run -m openrouter/...` |
| OpenCode Zen | `opencode.ai` | Provider `opencode`, `https://opencode.ai/zen/v1`; OpenCode Go uses `https://opencode.ai/zen/go/v1` on the same host |
| Model catalog | `models.dev` | Fetched at startup unless `OPENCODE_DISABLE_MODELS_FETCH`; the binary carries a bundled snapshot that `opencode models` uses without network |
| Session sharing | `opncd.ai` | Contacted with `share: "auto"`; not the Zen host |
| Updates and `opencode upgrade` | `registry.npmjs.org` | `opencode-ai/latest` |
| Configuration dependency install | `registry.npmjs.org` | `@opencode-ai/plugin` is installed in the background into every configuration directory, unconditionally; failure only logs a WARN |
| Other strings | `opencode.ai` (themes, schema, docs), `api.opencode.ai`, `app.opencode.ai`, `console.opencode.ai`, `github.com`, `api.github.com`, `raw.githubusercontent.com`, `api.githubcopilot.com`, `auth.openai.com` | GitHub app, web console, Copilot and ChatGPT login paths; not part of any profile |

Login: the four profiles use API keys from the environment. Keys stored by
`opencode auth login` were not measured. The OAuth methods (ChatGPT, GitHub
Copilot, GitLab) are not part of any profile and remain unsupported in
restricted modes.

### Optional-traffic controls

| Control | Effect in 1.18.3 | Precedence |
| --- | --- | --- |
| `OPENCODE_DISABLE_AUTOUPDATE` | Skips the startup update check | Either the variable or `autoupdate: false` disables; `autoupdate: true` cannot re-enable it |
| `OPENCODE_DISABLE_MODELS_FETCH` | No `models.dev` request; the cached or bundled catalog is used | No configuration key |
| `OPENCODE_DISABLE_SHARE` (`1` or `true`) | Share synchronization returns early; no `opncd.ai` request with `share: "auto"` | Wins over `share: "auto"` |
| `OPENCODE_DISABLE_DEFAULT_PLUGINS` | Internal plugins are not loaded | Plugins named in configuration still try `registry.npmjs.org` and are denied |
| `OPENCODE_DISABLE_LSP_DOWNLOAD` | LSP binaries are not downloaded | No configuration key |
| None | Background `@opencode-ai/plugin` install and an explicit `opencode upgrade` | The proxy denies them; startup continues |

With all five variables set and `OPENCODE_CONFIG_CONTENT='{"share":"auto","autoupdate":true}'`,
`opencode run` contacted only the provider host and `registry.npmjs.org`. Without
them, the same run also contacted `models.dev` and `opncd.ai`.

### Bun client behavior

- **Proxy:** OpenCode's HTTPS requests use CONNECT through `HTTPS_PROXY`.
- **Loopback bypass:** with `NO_PROXY=localhost,127.0.0.1,::1`, `opencode run --attach http://127.0.0.1:4096` reached the local server directly. With an empty `NO_PROXY`, the same request went to the proxy as `POST http://127.0.0.1:4096/session` and failed. The loopback bypass is therefore required.
- **CA trust:** a fixture CA with a `CA:FALSE`, `serverAuth` leaf for `api.anthropic.com` was tested behind a CONNECT proxy:
  - without CA variables, OpenCode refused the server (`unable to verify the first certificate`);
  - with `NODE_EXTRA_CA_CERTS` or `SSL_CERT_FILE`, the request `POST /v1/messages` reached the fixture.

### OpenCode under the guard (offline)

The guard was packaged with `network/build-guard.sh` under
`OPENCODE_CONTAINER_MAINTENANCE=1` from toolchain
`localhost/opencode-guard-toolchain:development`. The toolchain ID is
`0b69ba43c894…`; it is the reference toolchain, rebuilt from cache. The guard
SHA-256 is `0c647dfea75667a46a8cd4cc4dfea4ee3d10363752ea7ce5957162bacd6d7ec9`,
identical to Claude and Codex. Every run below used `--network=none`, private
PID and IPC namespaces, a read-only root, no capabilities and
no-new-privileges.

| Check | Result |
| --- | --- |
| `opencode run` against a loopback OpenAI-compatible stub (`@ai-sdk/openai-compatible`, `baseURL` `http://127.0.0.1:18080/v1`) | The stub returned a `bash` tool call. The tool ran and wrote the sentinel to the workspace, owned by the caller UID 1000, and the second turn returned `fixture-done` |
| OpenTUI in a PTY | Rendered, then exited with status 0 after two Ctrl+C presses |
| `bwrap` | Fails (`Failed to make / slave: Operation not permitted`). The OpenCode 1.18.3 binary contains no `bwrap` or `bubblewrap` reference, so OpenCode never uses it; it stays in the image only as a general tool |
| Named Unix socket in `/tmp` | Denied (`PermissionError`), as specified; neither the `run`, tool and TUI paths nor the local server needed one |
| LSP servers and formatters | None are preinstalled. Automatic LSP downloads are disabled in restricted modes, so those features fail until a maintenance change preinstalls the servers |
| Layout with `/tmp`, `/var/tmp` and `/opencode-home` as executable tmpfs mounts and the four state directories bind-mounted below the home | The guard reported `enforced revision=abi3-seccomp-mux-v1 abi=3`; `opencode --version` printed 1.18.3; executing a file from `/tmp` worked; OpenCode wrote `opencode.db` and `log/` to the data bind, owned by the caller |

### Shared reference, artifacts and suites

| Check | Result |
| --- | --- |
| Shared copy | `git archive` of `network/`, `setup/diagnostics.py` and 21 shared tests from `sandbox-ref-2`; `tests/test_guard.py` recopied from `sandbox-ref-3`. `diff -r` against the `sandbox-ref-3` tree: no differences |
| Shared-test defect | Under the guard, `tests/test_guard.py` ran `<agent> --version` with a read-only root and no writable home. OpenCode writes `$HOME/.local` at startup, so the test failed with `EROFS`. Fixed in `claude-container` (tag `sandbox-ref-3`, commit `449ce60`) by mounting an empty `notmpcopyup` tmpfs at the profile home; adopted by Codex and this repository |
| `tests/test_reference_copy.py` (on the host, with the sibling checkout at the tag) | Passed: 5 tests, including an injected byte change, a missing and an extra file, and an injected `OpenCode` literal |
| Profile and policy | `agent/profile.json` validates; the policy `opencode-2026-11-10-v1` validates against the profile rules; the identifiers `opencode`, `anthropic`, `openai` and `openrouter` occur in no shared file |
| Toolchain `localhost/opencode-guard-toolchain:development` | ID `0b69ba43c894c4599fcfc0fa7b5e3c150ec26fcf7a2690e3c83708688ff9402c` (the reference toolchain) |
| Guard | SHA-256 `0c647dfea75667a46a8cd4cc4dfea4ee3d10363752ea7ce5957162bacd6d7ec9`, identical to Claude and Codex |
| Proxy `localhost/opencode-egress:local` | ID `13adbfafd7bdc49393c142ecb7ede21ae6e1a7e4c1d842b1518078cdb5590621`, the same agent-neutral image as Codex |
| Runtime image `localhost/opencode-cli:latest` | ID `6a65050ddeb734005fe908c8a8f6b6f00ede5c457e7dfadc91e8ee4dd8707893`, OpenCode 1.18.3; `/opt/sandbox-egress/relay.py` and `mux.py` match `network/` by SHA-256 |
| `tests/test_image_pins.py` | Passed: 2 tests, including an injected `OPENCODE_VERSION` divergence that names both versions |
| Build-context probe (`test_runtime.py::test_build_context`) | Exactly four files reach the build; nested lookalikes, `network/proxy.py` and `network/bin` are excluded |

### Runner modes (`bash tests/run-runtime.sh <mode>`, final run)

| Mode | Result |
| --- | --- |
| `--wrapper` | Passed: 50 tests, covering modes, delegation, maintenance, proxy image, state, CA, offline and provider order and arguments, credentials per profile, protected values, reserved names, interrupted helpers and qualification entry points |
| `--shared` | Passed: 133 tests, 27 skipped (real-engine checks, run by the modes below) |
| `--qualification` | Passed: 18 tests |
| `--network-feasibility` | Passed: 1 test |
| `--network-policy` | Passed: 14 tests |
| `--mux` | Passed: 26 tests |
| `--guard` | Passed: 19 tests, 1 skipped (the idle check), including the three guarded multiplex checks through the OpenCode `test_network_runtime.py` fixture |
| `--guard-idle` | Passed: 1 test (the idle provider channel resumes after 305 seconds) |
| default (unrestricted runtime suite) | Passed: 19 tests |
| `--network` | 21 tests. One failure: `test_agent_budgets_are_effective_and_lifetime_cleans_owned_proxy` exited with status 255 without the lifetime notice. The notice compares whole seconds, the known lifetime limitation. Rerun alone, the test passed |

The `--network` suite covers:
- offline and provider acceptance through the wrapper after `--container-qualify`;
- denials: IPv4, IPv6, DNS and UDP egress, host and abstract sockets;
- the controlled TLS profiles: `controlled-test` and the four base profiles, with exact addresses;
- policy denials of `models.dev`, `opncd.ai`, `registry.npmjs.org` and another provider's host under `controlled-opencode-zen`;
- redirect, IP-literal, deceptive-suffix, port and administration denials;
- WebSocket upgrade, proxy loss, budgets and hardening;
- CA trust off and on;
- interrupted creation, bootstrap failures and readiness identities;
- arguments, stdin, status and TTY in both state modes;
- concurrent policies with owned cleanup.

Two checks are specific to OpenCode:
- **Bash tool through the relay.** A real `opencode run` used the synthetic OpenAI-compatible Chat Completions fixture (`@ai-sdk/openai-compatible`, CA trust enabled) through the relay. Its `bash` tool wrote the sentinel in both state modes.
- **OpenTUI in a PTY.** OpenTUI started under the guard in offline mode and exited with status 0 after Ctrl+C.

After the runs, no container, volume or test image labeled for `io.opencode-container` remained. The pre-existing containers of other projects were not touched.

Not run:
- a concurrent restricted session of a sibling wrapper (the suite covers two concurrent OpenCode policies with distinct ownership);
- the operator-run authenticated checks for `anthropic-api`, `openai-api`, `openrouter-api` and `opencode-zen` (a real request, streaming, a long-lived request and OpenTUI with each key). They are unavailable until the operator runs them, so no profile is declared verified.

### Static checks

| Check | Result |
| --- | --- |
| `bash -n opencode-container.sh opencode-wrapper` | Passed |
| ShellCheck (`koalaman/shellcheck:stable`) on the wrapper and `tests/run-runtime.sh` | No findings |
| markdownlint (`davidanson/markdownlint-cli2:v0.17.2`) | Only line-length (MD013) and list-spacing (MD032) findings, the same classes as the existing documents |
| `openspec validate add-network-egress --strict` | Valid |
| `git diff --check` | Clean |

Known limitations, unchanged:
- **Lifetime notice.** It compares whole seconds, so it can be missing when a lifetime-limited session ends just past the limit.
- **Test runner stdin.** `tests/run-runtime.sh` passes `--interactive`, so suites that inherit stdin need it closed: run the runner with `</dev/null`, or give the calls explicit input, as `test_deprecated_shim` now does.

## Guided setup (`add-container-setup`): 2026-11-10

Environment as in the network egress section. The shared code was moved to
`claude-container` tag `sandbox-ref-5` (commit
`3388b6ee45a1b9943f8f4aed77c0b1740a9ab4f8`). This port found two defects in
the shared setup test, fixed in Claude and adopted by Codex:
- **`sandbox-ref-4`:** the test required an authentication method with
  `login_args`. OpenCode's methods are API-key only, so it raised
  `StopIteration` at import.
- **`sandbox-ref-5`:** two checks assumed a single-component `config_home`.
  OpenCode's is `.config/opencode`, so they raised `FileNotFoundError`.

Wrapper-side alignments found by the shared tests:
- **Engine message.** The engine-query failure message now uses the reference
  wording, `cannot query Podman or invalid engine response; ...`.
- **State order.** `OPENCODE_CONTAINER_STATE_DIR` is created and validated
  after the engine verification, following the reference order. The lexical
  checks (absolute path, workspace overlap) still precede the engine. Before
  this change, a failed engine query left a new isolated directory behind.
- **Configuration variable.** The shared smoke check requires the profile's
  configuration variable to name a writable directory inside the session. The
  wrapper now sets `OPENCODE_CONTAINER_CONFIG_DIR=/opencode-home/.config/opencode`
  in every session; the host value is never forwarded.

### Setup acceptance

| Check | Result |
| --- | --- |
| Shared copy | `setup/`, `tests/test_setup.py` and `tests/test_alignment.py` from `sandbox-ref-5`; `diff -r` against the tag: no differences |
| `tests/test_reference_copy.py` (on the host, with the sibling checkout at the tag) | Passed: 5 tests; an injected byte change in `setup/common.py` is reported |
| `bash tests/run-runtime.sh --setup` (shared `test_setup.py`) | Passed: 63 tests |
| `tests/test_alignment.py` | Passed: 9 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests. Covered: provider setup with CA trust and the `openrouter` method; a managed `--version` from a fresh environment, through the guard and the diagnostics filter; the shell smoke check; a failed candidate update rolled back; an offline rerun; a relocated managed command; unrestricted setup and shell. Disposable `HOME`, installation and proxy image; no systemd change, credentials or model request |
| Provider setup transcript | Driven through a real pseudo-terminal with the acceptance harness, a disposable `HOME` and the `openrouter` method with no key set. Observed, in order: the residual-exfiltration notice, listing every method's host, with its required acknowledgement; `protected profile: openrouter-api`; the maintenance warning and authorization; `Sandbox qualification: locally-qualified`; `Sandbox: ready`; `Authentication pending. Supply OPENROUTER_API_KEY ...`; `Authentication: pending` |
| Real systemd user-service activation, real API-key requests | Unavailable (not exercised) |

### Final verification (task 4.3)

| Check | Result |
| --- | --- |
| `bash -n`, ShellCheck | Passed, no findings |
| `--wrapper` | Passed: 53 tests, including the setup entry point, the setup-required message, the diagnostics filter, the session configuration variable and the isolated-state order |
| `--shared` (includes `test_alignment.py` and `test_reference_copy.py`) | Passed: 142 tests, 27 skipped (run by the modes) |
| `--setup` | Passed: 63 tests |
| `--setup-runtime` | Passed: 2 tests |
| `--qualification` | Passed: 18 tests |
| default (unrestricted runtime suite) | Passed: 19 tests |
| `--network` | Passed: 21 tests |
| markdownlint | Only line-length (MD013) and list-spacing (MD032) findings, as in the existing documents |
| `openspec validate add-container-setup --strict`, `git diff --check` | Valid, clean |

No container, volume or test image labeled for `io.opencode-container` remained after the runs.

## Adoption of `sandbox-ref-6`: 2026-11-10

`claude-container` `sandbox-ref-6` (commit `3150bfe`) adds the optional profile
field `install.files`: setup installs the declared agent files, the
qualification identity binds them, and the shared qualification test
installation copies them with `Containerfile` and `.containerignore`. This
repository declares none, so its installation is unchanged. The changed shared
files are copied unchanged and `tests/test_reference_copy.py` moves to the
tag.

| Check | Result |
| --- | --- |
| `--shared` (includes `test_reference_copy.py`) | Passed: 143 tests, 27 skipped (run by the modes) |
| `--setup` | Passed: 63 tests |
| `--qualification` | Passed: 18 tests |

## Adoption of `sandbox-ref-7`: 2026-11-10

`claude-container` `sandbox-ref-7` (commit `d52a031`) adds the optional profile
field `install.runtime_build`. With `wrapper`, setup builds the runtime image
through the installed wrapper's build-only `--container-build`; the default
`recipe` keeps the direct `podman build`. This repository declares nothing, so
its setup is unchanged. The changed shared files are copied unchanged and
`tests/test_reference_copy.py` moves to the tag.

| Check | Result |
| --- | --- |
| `--shared` (includes `test_reference_copy.py`) | Passed: 144 tests, 27 skipped (run by the modes) |
| `--setup` | Passed: 64 tests |
| `--qualification` | Passed: 18 tests |

## Adoption of `sandbox-ref-8`: 2026-11-10

`claude-container` `sandbox-ref-8` (commit `12cffab`) changes only the shared
`tests/test_setup.py`: the runtime build test patches the dispatch point
`build_runtime`, so it also holds for profiles that build through the wrapper.

| Check | Result |
| --- | --- |
| `--shared` (includes `test_reference_copy.py`) | Passed: 144 tests, 27 skipped (run by the modes) |
| `--setup` | Passed: 64 tests |

## Adoption of `sandbox-ref-9`: 2026-11-10

`claude-container` tag `sandbox-ref-9` (commit `8b191e5`) lets an account method
declare empty `login_args`, so setup can offer sign-in inside the interactive
agent (needed by Antigravity, whose CLI has no login command). The changed
shared files `network/agent_profile.py`, `setup/setup.py`,
`tests/test_agent_profile.py` and `tests/test_setup.py` were copied unchanged;
the `tests/test_reference_copy.py` manifest moved to the tag. This profile is
unaffected: its methods keep their current setup behavior.

| Check | Result |
| --- | --- |
| `bash tests/run-runtime.sh --shared` | Passed: 145 tests, 27 skipped (run by the modes) |
| `bash tests/run-runtime.sh --setup` | Passed: 65 tests |

## Adoption of `sandbox-ref-10`: 2026-11-11

Copied from `claude-container` tag `sandbox-ref-10` (commit `0f6585f`):

- `network/agent_profile.py`, `setup/common.py`, `setup/setup.py`;
- `tests/test_agent_profile.py`, `tests/test_setup.py`.

The `tests/test_reference_copy.py` manifest moved to the tag.
`agent/profile.json` sets `native.private_shared_dirs: true`: the wrapper
already refuses non-private shared directories, and setup now refuses them too,
before image work. A failed setup smoke launch also shows the wrapper's
sanitized stderr. The profile is part of the qualified code identity, so
existing installations requalify on their next setup.

| Check | Result |
| --- | --- |
| `bash tests/run-runtime.sh --shared` | Passed: 146 tests, 27 skipped (run by the modes) |
| `bash tests/run-runtime.sh --setup` | Passed: 68 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --wrapper` | Passed: 53 tests |

A first run of all wrappers' suites was interrupted by a host crash. Its
leftover test containers were removed before this run.

## Operator authenticated session: 2026-11-11

The operator ran an authenticated OpenCode session in provider mode with the
setup-default profile `anthropic-api`. In the TUI, they asked the model to confirm
that it could use the harness tools and to report the sandbox's access limits.
The model did both, and the operator found the result correct.

The first attempt stalled because of plugins in the operator's earlier host configuration (README, "Plugins and network modes"). The session that passed used fresh state.

This covers an authenticated model request with tool use through the sandbox.
The `openai-api`, `openrouter-api` and `opencode-zen` profiles remain pending. Full profile verification under the readiness checklist is not
claimed. The checklist also covers streaming and long-lived requests,
WebSockets, sign-in, token reuse and refresh, CA behavior and shell mode.

## Adoption of `sandbox-ref-11` and lab-host fixes (`adopt-lab-host-fixes`): 2026-11-12

Copied from `claude-container` tag `sandbox-ref-11` (commit `d17e865`):

- `network/.containerignore`, `network/README.md`, `network/agent_budgets.py`;
- `network/control.py`, `network/guard-build.Containerfile`, `network/guard.c`;
- `network/proxy.py`, `network/proxy_hardening.py`;
- `network/qualification_peer.py`, `network/qualification_probe.py`,
  `network/qualification_records.py`, `network/qualification_runtime.py`;
- `network/qualify.py`, `network/session.py`;
- `setup/setup.py`, `setup/smoke.py`;
- `tests/test_guard.py`, `tests/test_network_policy.py`,
  `tests/test_qualification.py`, `tests/test_session.py`, `tests/test_setup.py`.

The `tests/test_reference_copy.py` manifest moved to the tag.

The same change ports the reference's lab-host adaptations to OpenCode. They
are the same ones Codex adopted on 2026-11-12:

- the Podman 5 `unix://` host socket report is reduced to its pathname
  before the socket check;
- each budget is requested only when the engine reports its cgroup
  controller. An unenforced budget gets a notice, and the inspection
  requires every enforced budget and no unenforced one;
- `/run/secrets` is masked with an empty read-only tmpfs;
- `--read-only-tmpfs=false` is replaced by a `noexec` 64 MiB `/dev`, `devpts`
  and an empty read-only `/dev/shm`. Executable `/tmp`, `noexec` `/var/tmp`,
  `noexec` `/run` and the home tmpfs are unchanged;
- the opted-in host CA is passed to `build_current_image` as the `build-ca`
  secret, and `.containerignore` admits `/podman-build-secret*`;
- Debian packages are fetched over verified HTTPS;
- `/workspace` is created in the package step. In Codex, the missing image
  `WORKDIR` made the gate containers fail on the Rocky host's domain UID.

The wrapper fixture copies `network/agent_budgets.py`, answers the controller
query and derives the fake inspection from the create arguments. In
`tests/test_image_pins.py`, the toolset check now matches
`apt-get -o ... install`, because it previously needed the literal
`apt-get install`.

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 336 tests, 70 skipped |
| `python3 -m unittest discover -s tests -p test_wrapper.py` | Passed: 59 tests. New cases: socket URL and invalid `unix://` values; every subset of controllers; unverifiable lists; unenforced budget present or enforced budget missing; device and secrets mounts in every unrestricted mode, offline and provider; proxy secrets mask and budgets; build secret with and without trust, for `--container-build` and for a missing image |
| `python3 -m unittest tests.test_image_pins` | Passed: 6 tests (transport, toolchain and workdir checks, with mutations) |
| `bash tests/run-runtime.sh --shared` | Passed: 158 tests, 28 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 71 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 26 tests, with `localhost/opencode-guard-toolchain:development` (`215f5ffc1023`) |
| `bash tests/run-runtime.sh --guard` | Passed: 20 tests, 1 skipped (the 305-second idle check) |
| `bash tests/run-runtime.sh --network` | Passed: 21 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 19 tests, including `test_opentui_renderer` and `test_tools_without_capabilities` under the new `/dev` and read-only `/dev/shm`. `test_runtime.py` always uses `localhost/opencode-cli:latest`, so that tag was assigned temporarily to the new image and removed afterwards |
| Runtime image `localhost/opencode-cli:adopt-ref-11` | Built with the wrapper's build arguments. Image `45ae34976eb9`. Debian sources `https://`, no `/tmp/apt-bootstrap-ca.pem`, `ca-certificates` installed, OpenCode `1.18.3`, OpenSpec `1.16.0`. `/workspace` is in the exported layer (root, 755, build time 08:23), and a `keep-id` container without `--workdir` at 08:24 leaves it unchanged |
| `bash -n opencode-container.sh`, `git diff --check`, `openspec validate adopt-lab-host-fixes --strict` | Passed, clean, valid |
| Parity table | SHA-256 `893682205ada6457060a60b3a7cacc48ec8fbc8c78db8422a38344846047cf86`, identical to claude-container and Codex |
| Operator `--container-setup` and session tests on the Rocky Linux 9 lab host, provider profile `opencode-zen` | Passed (operator-reported, 2026-11-12) |
| Operator `--container-setup` and session tests on the newer WSL host, provider profile `opencode-zen` | Passed (operator-reported, 2026-11-12) |
| Operator `--container-setup` and a session on this host | Pending |

Every restricted installation must rebuild and rerun setup or qualification.
The qualification identity, the shared code digests and the runtime image
identity all change.

## Adoption of `sandbox-ref-12`: 2026-11-12

Copied from `claude-container` tag `sandbox-ref-12` (commit `fd196c9`): `network/qualification_records.py`, `network/qualify.py`, `tests/test_qualification.py`, `tests/test_setup.py`.
The `tests/test_reference_copy.py` manifest moved to the tag.

The gate containers and the security-identity probe now pass `--workdir /`.
The shared runtime-build test pins `runtime_build: recipe`. OpenCode already
creates `/workspace` in its image, so no observed behavior changes. The
shared code digests change, so restricted installations rerun qualification.

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 337 tests, 70 skipped |
| `bash tests/run-runtime.sh --shared` | Passed: 159 tests, 28 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 71 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 27 tests |
| `bash tests/run-runtime.sh --guard` | Passed: 20 tests, 1 skipped (the 305-second idle check) |
| `bash tests/run-runtime.sh --network` | Passed: 21 tests |
| Runtime image used | `localhost/opencode-cli:adopt-ref-11` (`45ae34976eb9`), the current recipe |
| Operator `--container-setup` on the hosts in use | Pending |

## Engine-provided `/dev` for pseudo-terminals: 2026-11-12

Change `use-engine-dev-for-pseudo-terminals`, launcher only, as in the Claude
reference (claude-container `docs/validation.md`, same title) and Codex. No
shared file changes.

OpenCode and shell containers no longer mount their own `/dev` tmpfs or
`devpts`. The explicit `devpts` from `sandbox-ref-11` took the kernel
defaults `mode=600,ptmxmode=000`, so no process in a session could open a
pseudo-terminal ("out of pty devices"). The terminal itself attached,
because the engine allocates the console outside that `devpts`. The engine's
`devpts` is `mode=620,ptmxmode=666`. On Podman 5, `/dev` is now the engine's
writable tmpfs without `noexec`. OpenCode's `/tmp` was already executable for
OpenTUI. The requirement "Terminal-compatible device mounts" is replaced by
"Engine-provided device mounts allow pseudo-terminals".

| Check | Result |
| --- | --- |
| Image `localhost/opencode-cli:adopt-ref-11` (`45ae34976eb9`) with the previous `/dev` arguments | `pty.openpty()`: "out of pty devices" |
| `test_pseudo_terminals_and_device_masks` (new) with the previous launcher | Failed: "out of pty devices" |
| `test_pseudo_terminals_and_device_masks` with the fix | Passed |
| `tests/test_wrapper.py` | Passed: 59 tests. With the previous launcher, the updated assertions fail (15 failures) |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 338 tests, 71 skipped (the runtime tests are opt-in) |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 20 tests, including `test_opentui_renderer`, `test_tools_without_capabilities` and `test_pseudo_terminals_and_device_masks`. `test_runtime.py` always uses `localhost/opencode-cli:latest`, so that tag was assigned temporarily to `45ae34976eb9` and removed afterwards |
| Operator `--container-setup` on this host, the Rocky Linux 9 lab host and the newer WSL host | Passed (operator-reported, 2026-11-12) on all three hosts |

Qualification digests the launcher, so restricted installations rerun
`--container-setup`. The runtime image is unchanged.
