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

## Adoption of `sandbox-ref-16` and the toolchain library (`adopt-sandbox-ref-16`): 2026-11-14

Copied from `claude-container` tag `sandbox-ref-16` (commit `1fa091e`):
`network/agent_profile.py`, `network/control.py`,
`network/qualification_records.py`, `setup/common.py`,
`tests/test_alignment.py`, `tests/test_qualification.py`,
`setup/toolchains.py`, `tests/test_toolchains.py`.
The `tests/test_reference_copy.py` manifest moved to the tag.

Wrapper port of the reference toolchain library (claude-container
`add-toolchain-library`, commit `e45957f`; Codex `adopt-sandbox-ref-14`):
- `--container-toolchain add|list|remove|verify`, dispatched before the
  network mode;
- `OPENCODE_CONTAINER_TOOLCHAINS`, parsed like the other boolean settings, and
  `OPENCODE_CONTAINER_TOOLCHAINS_DIR`;
- the library checked against the workspace and every writable state
  directory (the four shared OpenCode directories or the isolated
  `OPENCODE_CONTAINER_STATE_DIR`) before any image or container operation;
- the read-only `/toolchains` mount (`ro,nosuid,nodev`), with
  `--mount-target /toolchains` in restricted modes;
- default toolchain `PATH` entries appended after the image `PATH`.

Since `sandbox-ref-15`, toolchains cannot set `XDG_` variables, so they never
move OpenCode's state. The README has a "Toolchains" section with the
`AGENTS.md` instruction line; the example recipes are linked in
claude-container.

A first apply of this change, on `sandbox-ref-15`, was discarded before any
commit. A shared comment named OpenCode, and the agent-identifier scans
failed on it. The reference fixed it in `sandbox-ref-16`.

`tests/run-runtime.sh` mounts a private executable tmpfs at
`/sandbox-test-tmp` as `SANDBOX_TEST_TMPDIR`, and `tests/test_wrapper.py`
creates its fixtures there, as in the reference and Codex.

Fixture adaptations required by the new mount:
- `tests/test_wrapper.py`:
  - an exposed home stops on the library overlap, and passes with
    `OPENCODE_CONTAINER_TOOLCHAINS=0`;
  - bare wrapper copies without `setup/` omit the library;
  - the host-XDG test accepts that only the shared library follows
    `XDG_DATA_HOME`;
  - the isolated-state test accepts the library below the host home and a
    third volume;
  - the restricted fixture installs `setup/` and `Containerfile`.
- `tests/test_network_runtime.py`: the synthetic installation gains
  `setup/common.py`, `setup/toolchains.py` and `Containerfile`.

| Check | Result |
| --- | --- |
| New `tests/test_wrapper.py` cases with the previous launcher | Failed as intended (dispatch, mount, private creation, unsafe library including shared and isolated state, disabled mount, appended `PATH`, restricted `--mount-target`, home workspace overlap) |
| `python3 -m unittest tests.test_reference_copy tests.test_toolchains` (private tmpfs), including the agent-identifier scans | Passed |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 370 tests, 74 skipped |
| `bash tests/run-runtime.sh --shared` | Passed: 160 tests, 28 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 71 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 28 tests |
| `bash tests/run-runtime.sh --guard` | Passed: 20 tests, 1 skipped |
| `bash tests/run-runtime.sh --network` | Passed: 22 tests, including a toolchain added on the host during an offline session, usable without direct network |
| `bash tests/run-runtime.sh --wrapper` | Passed: 65 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 22 tests, including archive and image sources, a failing check, the read-only mount, the image's `node` and `python3` kept first, the wrapper's `XDG_DATA_HOME` kept, and the omitted mount |
| Five-wrapper parity table | Identical to claude-container's (`sandbox-ref-16`) |
| Operator `--container-setup` on this host, the Rocky Linux 9 lab host and the newer WSL host, `java -version` with the Temurin 21 toolchain, and `--container-toolchain verify java21` | Passed (operator-reported, 2026-11-14); `main` pushed |

Runtime image: setup image `d671ac84156f`, tagged `localhost/opencode-cli:latest`
only for the runs and untagged by name afterwards (its setup tags remain).
Qualification digests the launcher and `setup/toolchains.py`, so restricted
installations rerun `--container-setup`.

## Adoption of `sandbox-ref-17`: 2026-11-14

Copied from `claude-container` tag `sandbox-ref-17` (commit `a23f155`):
`setup/toolchains.py`, `tests/test_toolchains.py`.
The `tests/test_reference_copy.py` manifest moved to the tag.

`sandbox-ref-17` splits the protected toolchain variables into two groups:

- **Neutral:** the same in every wrapper, now including
  `DBUS_SESSION_BUS_ADDRESS`. `add` rejects them, and `launch-env` fails on
  them.
- **Profile:** OpenCode's own variables, which are `OPENCODE_CONTAINER_*`
  and the four credential variables. `add` rejects them. If another wrapper's
  toolchain in the shared index sets one, `launch-env` leaves it out of the
  session and prints one warning naming the toolchain.

The README "Protected variables" bullet now describes both groups. The
launcher reads only the standard output of `launch-env`, and the warnings go
to standard error. The launcher and the wrapper tests are therefore unchanged.

| Check | Result |
| --- | --- |
| `python3 -m unittest tests.test_reference_copy tests.test_alignment tests.test_toolchains` (private tmpfs) | Passed: 38 tests, 1 skipped |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 372 tests, 74 skipped |
| `bash tests/run-runtime.sh --shared` | Passed: 160 tests, 28 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 71 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 28 tests |
| `bash tests/run-runtime.sh --wrapper` | Passed: 65 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 22 tests |
| Five-wrapper parity table | Identical to claude-container's (`sandbox-ref-17`) |
| Operator `--container-setup` on this host, the Rocky Linux 9 lab host and the newer WSL host | Passed (operator-reported, 2026-11-14); `main` pushed |

Runtime image: setup image `d671ac84156f`. It was tagged
`localhost/opencode-cli:latest` only for the runs and untagged by name
afterwards; its setup tags remain. `setup/toolchains.py` is qualified code,
so restricted installations rerun `--container-setup`.

## Toolchain variables cannot override the session (`protect-session-env-from-toolchains`): 2026-11-14

Fixes finding H1 of the cross-wrapper review of 2026-11-14. The launcher
appended the toolchain variables after the protected `OPENCODE_DISABLE_*=1`
values and after the YOLO `OPENCODE_PERMISSION`, and Podman keeps the last
`--env` for a name. A default toolchain in the shared library, possibly
installed from another wrapper, could therefore re-enable optional traffic
in restricted modes, grant every approval without YOLO through
`OPENCODE_PERMISSION` or `OPENCODE_CONFIG_CONTENT`, or override a forwarded
provider variable.

The launcher now:
- leaves out a toolchain variable that starts with `OPENCODE_` or is listed
  in `ALL_PROFILE_NAMES`, with one warning per variable;
- adds the remaining toolchain variables before forwarding, so forwarded
  values, the protected values and YOLO come later and win. The toolchain
  `PATH` entry keeps its place after image resolution.

The new `test_toolchain_cannot_override_protected_variables` checks the
final value of each name in restricted provider mode with and without YOLO,
and in unrestricted mode with a forwarded `OPENAI_BASE_URL`. It fails on
`main` (the toolchain's `0` and URL win) and passes on the branch.

| Check | Result |
| --- | --- |
| `shellcheck opencode-container.sh` | Same two warnings as on `main` (SC2054, SC2154) |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 373 tests, 76 skipped |
| `bash tests/run-runtime.sh --wrapper` | Passed: 66 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 22 tests |

Runtime image: setup image `d671ac84156f`, tagged
`localhost/opencode-cli:latest` only for the runs and untagged by name
afterwards. No shared file changed, and qualification probes run without the
toolchain mount, so no requalification is needed.

## Adoption of `sandbox-ref-18`: 2026-11-15

Copied from `claude-container` tag `sandbox-ref-18` (commit `958465b`):
`network/agent_profile.py`, `setup/common.py`, `setup/toolchains.py`,
`tests/test_agent_profile.py`, `tests/test_alignment.py`, `tests/test_setup.py`,
`tests/test_toolchains.py`.
The `tests/test_reference_copy.py` manifest moved to the tag.

`sandbox-ref-18` adds the optional profile field `native.protected_env`, runs
the toolchain check in `/`, refuses an isolated state directory that overlaps
the workspace on managed launches, and makes the alignment test check the
launcher's code and its help text separately. The shared tests passed
without adapting an OpenCode fixture.

OpenCode changes, from the cross-wrapper review of 2026-11-14:

- **Agent variables:** `agent/profile.json` declares `OPENCODE_`,
  `ANTHROPIC_`, `OPENAI_`, `OPENROUTER_`, `GEMINI_`, `GOOGLE_API_KEY`,
  `GOOGLE_GENERATIVE_AI_API_KEY`, the five `AWS_` Bedrock variables,
  `AZURE_RESOURCE_NAME` and `AZURE_API_KEY`. `launch-env` now leaves them out
  with its own warning, including names the launcher filter does not cover,
  such as `ANTHROPIC_BASE_URL` (H1 follow-up).
- **Launcher filter kept:** the filter from `protect-session-env-from-toolchains`
  stays as a second layer. With the declaration, `launch-env` drops these
  variables first, so `test_toolchain_cannot_override_protected_variables`
  now expects the shared warning, and a new `launcher-filter` case removes
  `protected_env` from the installed profile to keep the launcher filter
  covered.
- **Name collisions (M2):** after a failed create without an ID, an existing
  container with the candidate name is a collision only when its session
  label differs. This session's own container stays pending, so the existing
  label recovery in cleanup removes it, and the wrapper returns the create
  status without retrying. An unreadable label is reported and not retried.

The fake engine in `tests/test_wrapper.py` now answers the name-label
inspection. The new tests (`test_toolchain_cannot_set_agent_variables`,
`test_owned_name_is_not_a_collision`) fail on `main` and pass on the branch.

| Check | Result |
| --- | --- |
| `shellcheck opencode-container.sh` | Same two warnings as on `main` (SC2054, SC2154) |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 379 tests, 76 skipped |
| `bash tests/run-runtime.sh --shared` | Passed: 161 tests, 28 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 72 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` (not in the tool's checklist; shared `setup/` modules are qualified code) | Passed: 28 tests |
| `bash tests/run-runtime.sh --wrapper` | Passed: 68 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 22 tests |
| Five-wrapper parity table | Identical to claude-container's (`sandbox-ref-18`) |
| Operator `--container-setup` on this host, the Rocky Linux 9 lab host and the newer WSL host | Passed (2026-11-15, reported by the operator after the push) |

Runtime image: setup image `d671ac84156f`, tagged
`localhost/opencode-cli:latest` only for the runs and untagged by name
afterwards. Shared qualified code changes, so restricted installations rerun
`--container-setup`.

## Adoption of `sandbox-ref-20`: 2026-11-16

`sandbox-container` is now the reference (it replaced `claude-container`).
Copied from `sandbox-container` tag `sandbox-ref-20` (commit `d4fd4ca`) with
`tools/propagate.py`: `network/README.md`, `network/agent_profile.py`,
`network/policy.py`, `network/qualification_records.py`, `network/qualify.py`,
`network/session.py`, `setup/common.py`, `setup/setup.py`, `setup/toolchains.py`,
`tests/sandbox_profile.py`, `tests/test_agent_profile.py`, `tests/test_alignment.py`,
`tests/test_guard.py`, `tests/test_qualification.py`, `tests/test_session.py`,
`tests/test_setup.py` and the fixture profiles in `tests/fixtures/`. The
`tests/test_reference_copy.py` manifest moved to the tag and names
`sandbox-container` as its sibling. Per-agent: `tests/test_setup_wrapper.py`
(copied from Claude), the lifetime notice measured with a monotonic clock
(`/proc/uptime`, since WSL2 steps the wall clock backwards) from just before
container creation plus a boundary test (failed with the old launcher),
documents pointing at `sandbox-container`, parity table fixed by hand.

Runtime image: setup image `d671ac84156f`
(`localhost/opencode-cli:setup-7604937c…`), tagged `localhost/opencode-cli:latest`
only for the runs and untagged by name afterwards; WSL2 6.6.87.2, Podman 4.9.3.

**Known shared defect:** in `--guard`,
`test_production_filter_and_landlock_on_real_rootless_kernel` fails with
`EROFS: read-only file system, mkdir '/opencode-home/.local'`. The shared
`tests/test_guard.py` mounts the writable home of the fixture profile
(`/fixture-home`) on the real image instead of the wrapper's home; OpenCode
writes to its home at startup, the other wrappers' version commands do not.
With `REAL_PROFILE.home` (temporary local change, reverted) the test passes. The
fix belongs to the reference and arrives with `sandbox-ref-21`.

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 397 tests, 74 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 66 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 28 tests |
| `bash tests/run-runtime.sh --guard` | 20 tests, 1 skipped: 1 failure, the shared defect above |
| `bash tests/run-runtime.sh --network` | Passed: 22 tests |
| `bash tests/run-runtime.sh --network-policy` | Passed: 15 tests |
| `bash tests/run-runtime.sh --network-feasibility` | Passed: 1 test |
| `bash tests/run-runtime.sh --wrapper` | Passed: 69 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 22 tests |
| `git diff --check`, `bash -n opencode-container.sh` | Passed |
| Operator `--container-setup` on the three hosts (`sandbox-ref-21`) | Passed (operator, 2026-11-16) |

## Adoption of `sandbox-ref-21`: 2026-11-16

Copied from `sandbox-container` tag `sandbox-ref-21` (commit `4b25eae`) with
`tools/propagate.py`: `tests/sandbox_profile.py`, `tests/test_guard.py`. The
`tests/test_reference_copy.py` manifest moved to the tag; parity table fixed by
hand. The shared guard runtime test now mounts the image's own native home
(`AGENT_HOME`) instead of the fixture profile's home. It failed here under `sandbox-ref-20` (`EROFS` on `/opencode-home/.local`).

Runtime image: `localhost/opencode-cli:setup-7604937c250c47628c5de0104612b917`; WSL2 6.6.87.2, Podman 4.9.3.

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 397 tests, 74 skipped |
| `bash tests/run-runtime.sh --guard` | Passed: 20 tests, 1 skipped |
| `git diff --check` | Passed |
| Operator `--container-setup` on the three hosts (`sandbox-ref-21`) | Passed (operator, 2026-11-16) |

Only shared test files changed: installations need no new setup for this tag.

## Adoption of `sandbox-ref-25`: 2026-11-18

Change `adopt-sandbox-ref-25`: full adoption of the shared launcher core, from
`sandbox-ref-21` straight to `sandbox-ref-25` (commit `6bed770`). Copied from
`sandbox-container` with `tools/propagate.py`: `network/README.md`,
`network/agent_profile.py`, `network/control.py`, `network/qualification_records.py`,
`network/qualify.py`, `setup/common.py`, `setup/launch.py`, `setup/setup.py`,
`tests/fixtures/agent/profile.json`, `tests/sandbox_profile.py`,
`tests/test_agent_profile.py`, `tests/test_alignment.py`, `tests/test_network_policy.py`,
`tests/test_qualification.py`, `tests/test_setup.py`, `launcher/core.sh`,
`tests/fake_podman.py`, `tests/fixtures/agent/launcher.sh`,
`tests/fixtures/shell-agent/launcher.sh`, `tests/test_launcher.py`. The
`tests/test_reference_copy.py` manifest moved to the tag and lists `launcher` as
a closed directory; the parity rows were copied from their repositories.

- **Launcher:** `opencode-container.sh` is the reference entry script with the
  wrapper name replaced; `opencode-wrapper` is deleted. `agent/launcher.sh` holds
  OpenCode's profile values, `AGENT_EXEC=/usr/local/bin/opencode`,
  `AGENT_EXEC_TMP=1`, one credential per policy profile, the fixed XDG bases
  (reserved), the five `OPENCODE_DISABLE_*=1` switches for restricted sessions,
  and five hooks: `agent_validate`, `agent_mounts`, `agent_environment`,
  `agent_approval_bypass` and `agent_help`. `agent/profile.json` declares
  `native.exec_tmp: true`.
- **Build (U3, U8):** images carry `build-inputs-hash`; images prepared before
  this change are refused as stale until rebuilt. `--container-build` without
  OpenCode arguments builds and exits.
- **Temporary storage (U7, L7):** `/tmp` and the shared-state home stay
  executable 512 MiB tmpfs mounts, `/var/tmp` is `noexec`, `/run` (32 MiB) is
  not writable by the session user.
- **Dropped:** the version-variable notices, the shim, the extra
  `io.opencode-container.*` labels, the credential notice (design decision 2)
  and OpenCode's own toolchain filter (contract: redundant with
  `setup/toolchains.py`).

Old tests gate (design decision 4): the `sandbox-ref-21` `tests/test_wrapper.py`
(69 cases) ran with its embedded fake engine against the new entry script and
core, with only its harness adapted (the fake answers the core's
`build-inputs-hash` label and its one-line socket query; synthetic installations
copy the core, the agent part and the build inputs; removal arguments and tmpfs
options are recorded in the old order). The first run found a defect in the
agent part (an unset `OPENCODE_CONTAINER_YOLO` read under `set -u`), fixed before
the classification. 31 cases then failed, each classified below. No lost
behavior: two candidates (the create warning and the create umask) were
classified as visible changes by the user (2026-11-18).

| Old case | Outcome | Maps to |
| --- | --- | --- |
| `test_application_status_survives_cleanup_failure` | visible change | wording; status preserved (U9 cleanup report "cleanup rm failed or timed out") |
| `test_budget_inspection_failures` | visible change | wording ("agent not started"); start still refused |
| `test_creation_signals` | visible change | the old internal `error` file; the core keeps create diagnostics in its private session directory |
| `test_deprecated_shim` | visible change | U2: `opencode-wrapper` removed (obsolete in the test map) |
| `test_device_and_secret_mounts_in_every_unrestricted_mode` | visible change | L7: `/run` without mode 1777, not writable by the session user |
| `test_exact_delegation_and_remapping` | visible change | phase 5 union (M6): `--unsetenv CONTAINER_CONNECTION` in every session |
| `test_extra_environment_names` | visible change | a name listed twice is passed twice, by name, with the same value |
| `test_help_and_arguments` | visible change | help text from the core |
| `test_help_documents_modes_migration_and_provider_limits` | visible change | U1: no migration text; hosts printed from the policy |
| `test_host_ca_trust_modes` | visible change | wording ("isolated configuration escapes state home"); refusal kept |
| `test_image_and_ignored_version_variables` | visible change | U2: version-variable notices removed |
| `test_image_inspection_and_build` | visible change | a failed image inspection exits 1 with a diagnostic instead of the engine status (user, 2026-11-17, Codex) |
| `test_labels_use_common_namespace` | visible change | phase 6: only the session ownership label (obsolete in the test map) |
| `test_maintenance_gates_every_build` | visible change | as `test_image_inspection_and_build` |
| `test_missing_mode_stops_before_engine_state_and_other_checks` | visible change | U1 provider default and its setup message |
| `test_mode_and_delegation_rejections_precede_engine` | visible change | phase 1-2 union: setup guidance before mode-specific settings |
| `test_modes` | visible change | U14: shell receives its arguments |
| `test_mount_paths_and_boundaries` (colon in the workspace) | visible change | phase 5: binds are validated by the core's bind builder after the read-only image check; no build or create |
| `test_names_failures_and_owned_records` (create warning) | visible change (user, 2026-11-18) | stderr of a successful create is not shown; it is printed when create fails |
| `test_offline_order_arguments_and_status` | visible change | U8 label inspection adds one image query; qualification check after the name listing, before create |
| `test_owned_name_is_not_a_collision` | visible change | wording: the create diagnostics are reported; no retry and no removal by name |
| `test_private_xdg_and_umask` (create umask) | visible change (user, 2026-11-18) | create runs with the caller's umask; the CID record lives in a private 0700 session directory |
| `test_provider_order_credentials_and_protected_values` | visible change | L7 `/run` |
| `test_restricted_credentials_match_the_agent_profile` | visible change | source inspection of the old launcher; `AGENT_CREDENTIALS` (U10) |
| `test_restricted_modes_reserve_network_variables` | visible change | wording ("which this session sets itself") |
| `test_session_names_the_effective_configuration_directory` | visible change | wording ("which this session sets itself") |
| `test_setup_entry_point_is_dedicated_and_help_takes_precedence` | visible change | help text from the core |
| `test_stubborn_sessions_and_control_failures_are_bounded` | visible change | U9 rewrite; wording |
| `test_tmpfs_and_named_environment` | visible change | L7 `/run` |
| `test_toolchain_cannot_override_protected_variables` (launcher filter) | visible change | contract: OpenCode's own toolchain filter is dropped; `setup/toolchains.py` protects the profile's names |
| `test_unselected_provider_forwards_nothing_and_notifies` | visible change | design decision 2: the credential notice is dropped; nothing is forwarded |

The other "to verify at adoption" cases passed against the core. The hook cases
are rewritten in the reduced `tests/test_wrapper.py` (14 tests).

Environment: WSL2 6.6.87.2, Podman server 4.9.3; image rebuilt through the
build-only path: `localhost/opencode-cli:latest` `4987c713b195`, OpenCode 1.18.3,
`build-inputs-hash` `b6c2cfc8a65472fc6afae0abd75b0bafaa772b605f2fc870167d98be28afbc88`;
guard toolchain tagged from the setup image of this host.

| Check | Result |
| --- | --- |
| `--container-build` alone (real engine, maintenance) | Passed: built, labeled, no session container |
| `python3 -m unittest tests.test_alignment tests.test_agent_profile tests.test_launcher` (disposable container) | Passed: 145 tests, 1 skipped |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 456 tests, 76 skipped |
| `bash tests/run-runtime.sh --wrapper` | Passed: 121 tests (`test_launcher.py`, `test_wrapper.py`) |
| `bash tests/run-runtime.sh --shared` | Passed: 288 tests, 29 skipped |
| `bash tests/run-runtime.sh --setup` | Passed: 67 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 29 tests |
| `bash tests/run-runtime.sh --network` | Passed: 22 tests |
| `bash tests/run-runtime.sh --guard` | Passed: 20 tests, 1 skipped |
| `bash tests/run-runtime.sh` (`test_runtime.py`, `image-smoke.sh`) | Passed: 23 tests |
| `git diff --check`, `bash -n` on the entry script, the agent part and the scripts | Passed |
| ShellCheck (warning) on `opencode-container.sh` and `agent/launcher.sh` | Passed |
| Operator `--container-setup` on this host, the Rocky Linux 9 lab host and the newer WSL host, then an OpenCode session in provider mode | Passed (operator, 2026-11-18) |

The installed and qualified code changes (entry script, core, agent part,
profile) and every runtime image needs the label: installations rerun
`--container-setup`.

## OpenCode 1.19.5 and OpenSpec 2.0.0 image pins (2026-11-18)

The change `pin-opencode-1-19-5` uses the newest stable npm releases at least
72 hours old at the 2026-11-18 freeze. OpenCode 1.19.6 had yet to meet that
threshold. OpenCode 2.x uses a different distribution and has a separate
migration plan. The base digest remains
`sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`.

| Image | Image ID | OpenCode | OpenSpec |
| --- | --- | --- | --- |
| Baseline | `4987c713b195b28ad2facae12086fb23ef19fb83507da55d4d4ab97b9e969f44` | 1.18.3 | 1.16.0 |
| Updated | `d64a72cd560eb6b97472f61d0705b391a3ea5ca65d630b2f9d1149b19e4f430f` | 1.19.5 | 2.0.0 |

The maintenance build used HTTPS Debian sources and produced build-inputs hash
`5a57734ac0bd74841737351881fd121bb41b74f9ba9a123eb1d03ddb3fa3204d`.
The checked Linux x64 and x64-baseline binaries have SHA-256
`7df4e4136301f16589b0f30bf91a61380fca5f8ef22dd36570f5ebe1d4ec802c`.
Validation used WSL2 6.6.87.2 with Podman client 4.3.1, rootless server 4.9.3,
and Netavark.

### Provider metadata and CLI behavior

The bundled catalog was read from `GET /provider` on loopback with catalog
fetching disabled. Anthropic, OpenAI, OpenRouter, and Zen still list
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, and
`OPENCODE_API_KEY` respectively. The destination and forwarding tables still
match the four restricted profiles. Policy revision
`opencode-2026-11-18-v1` records this measurement.

`opencode debug config` and `opencode debug agent build` reported `read: ask`
and `bash: deny` from a disposable project configuration. Adding
`OPENCODE_PERMISSION={"*":"allow"}` placed the wildcard last and made the
effective rules `allow` for both. This matched 1.18.3. The 1.19.5 CLI accepted
`--auto` on the default interface and `run`, and rejected it with
`debug paths`. An actual `run --auto` attempted CONNECT to `api.openai.com`
through the loopback fixture proxy.

### Endpoint and optional-traffic measurements

Both image versions ran in containers with `--network=none`, fresh XDG state,
dummy keys, and a loopback logging proxy that rejected every request with HTTP
403. The measurements used `autoupdate: true` and `share: "auto"`. The
per-provider CONNECT targets were identical across versions and with all five
controls set or unset.

| Profile | Model | Provider host |
| --- | --- | --- |
| `anthropic-api` | `anthropic/claude-sonnet-4-5` | `api.anthropic.com` |
| `openai-api` | `openai/gpt-5` | `api.openai.com` |
| `openrouter-api` | `openrouter/openai/gpt-5` | `openrouter.ai` |
| `opencode-zen` | `opencode/gpt-5` | `opencode.ai` |

| Additional CONNECT traffic | 1.18.3 | 1.19.5 |
| --- | --- | --- |
| `run` with all five controls unset | `models.dev`, `opncd.ai`, `registry.npmjs.org` | `models.opencode.ai`, `registry.npmjs.org` |
| `run` with all five controls set | `registry.npmjs.org` | `registry.npmjs.org` |
| `models` with controls unset | `models.dev` | `models.opencode.ai` |
| `models` with controls set | None | None |
| Explicit `upgrade --method npm`, either setting | `registry.npmjs.org` | `registry.npmjs.org` |

The old sharing hostname and `OPENCODE_DISABLE_SHARE` are absent from the
checked 1.19.5 binaries. Session sharing ended in
[1.19.1](https://github.com/anomalyco/opencode/releases/tag/v1.19.1).
The binary and tagged sources retain the update, model fetch, built-in plugin,
and LSP download controls. The update control suppresses the availability
check. Since [1.19.0](https://github.com/anomalyco/opencode/releases/tag/v1.19.0),
installation of updates requires an explicit action. A denied explicit upgrade
in 1.19.5 printed `Couldn't check for updates` and returned 0, where 1.18.3
returned 1. The registry remains outside the four profiles. The catalog host
change concerns optional traffic and leaves the required destinations intact.

The unchanged-tree pin suite passed all six tests, and credential-free unit
discovery passed with 456 cases and 76 skips. The updated pin suite passed all
six tests. The reference ShellCheck run emitted the same 71 existing findings
before and after the changes (14 in the shared core and 32 and 25 in the
shared launcher fixtures).

### Acceptance checks

| Check | Result |
| --- | --- |
| Credential-free unit discovery on the updated image | Passed, 456 cases with 76 skips, matching the baseline |
| Host `tests.test_reference_copy` and `tests.test_alignment` | Passed all 22 tests with the reference checkout available |
| `bash tests/run-runtime.sh --wrapper` | Passed all 121 tests |
| `bash tests/run-runtime.sh --shared` | Passed, 288 cases with 29 skips |
| `bash tests/run-runtime.sh --setup` | Passed all 67 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed both tests |
| `bash tests/run-runtime.sh` | Passed all 23 tests, including image smoke and the OpenTUI renderer |
| `bash tests/run-runtime.sh --qualification` | Passed all 29 tests |
| `bash tests/run-runtime.sh --network` | Passed all 22 tests, including TLS binding, OpenTUI in both state modes, and a tool call through a synthetic API |
| `bash tests/run-runtime.sh --guard` | Passed, 20 cases with the opt-in 305-second idle case skipped |
| `--container-qualify` on a disposable offline installation | Returned `locally-qualified` for the updated image |
| Interactive OpenTUI with `--auto` in the qualified offline session | Displayed the welcome prompt and exited with status 0 |
| Offline OpenSpec planning round trip | `init --tools none`, `new change`, `validate --all --strict`, and `list --json` passed. The temporary change used `skip_specs: true` |
| `git diff --check` | Passed |
| `openspec validate pin-opencode-1-19-5 --strict` | Passed |

## Adoption of `sandbox-ref-28`: 2026-11-23

Change `adopt-sandbox-ref-28`, from `sandbox-ref-25` directly. It takes in
`sandbox-ref-26`, `sandbox-ref-27` and `sandbox-ref-28`:
- the process rlimit fallback and systemd-only cgroup delegation;
- the shared launcher files passing ShellCheck;
- Windows support on a Podman machine;
- the Windows setup guidance for agent wrappers.

Copied from `sandbox-container` tag `sandbox-ref-28` (commit `ba1ef14`):
- updated: `launcher/core.sh`, `network/README.md`, `network/agent_budgets.py`,
  `network/control.py`, `network/guard.c`, `network/proxy_hardening.py`,
  `network/qualification_probe.py`, `network/qualification_records.py`,
  `network/session.py`, `setup/common.py`, `setup/launch.py`, `setup/setup.py`,
  `setup/smoke.py`, `tests/fake_podman.py`, both fixture `launcher.sh`,
  `tests/test_alignment.py`, `tests/test_guard.py`, `tests/test_launcher.py`,
  `tests/test_qualification.py`, `tests/test_session.py` and
  `tests/test_setup.py`;
- added: the five `launcher/windows/` files, `tests/test_windows_bootstrap.py`,
  `tests/test_windows_enter.py` and `tests/windows/shim_tests.ps1`.

The `tests/test_reference_copy.py` manifest moved to the tag. The tool also
rewrote the Pi parity row, which stays on `sandbox-ref-25`; it was restored by
hand.

By hand, as `docs/propagation.md` says:
- `opencode-container.ps1` is a byte-for-byte copy of `sandbox-container.ps1`;
- `.gitattributes` was copied. The LF rewrite changed nothing: every tracked
  file was already LF in the index and the working tree;
- `agent/launcher.sh` already had the ShellCheck header of the reference agent
  part, so it did not change.

OpenCode's own tests changed where the shared behavior did, as in the other
wrappers:
- `tests/test_setup_wrapper.py` is the shared adapted file, byte for byte: the
  files were identical before. It adds a failing `systemctl`, the budget plan
  with the rlimit fallback and `cgroupfs`, and the case for setup without a
  launch service;
- `tests/test_runtime.py`: `cgroup()` and `test_effective_hardening_and_budgets`
  follow the delegated controllers and the process mechanism, with the launch
  notices, and `test_process_limit_enforced` uses a budget of 128 with 200
  children.

The README, `docs/setup.md` and `AGENTS.md` cover:
- the Windows entry for OpenCode, with the four API key methods through
  `$env:<KEY>` and keys stored with `opencode auth login`;
- OpenCode's native variables and the variables of
  `OPENCODE_CONTAINER_PROVIDER`, which reach a session from Windows only
  through `OPENCODE_CONTAINER_ENV_VARS`;
- the installer;
- host CA trust on Windows;
- the Windows limits, including Bitdefender;
- the `cgroupfs` budgets, the rlimit fallback and the guard as init;
- the setup changes.

**This runner.** WSL2 `6.18.58.1-microsoft-standard-WSL2`, Podman server
4.9.3, the `systemd` cgroup manager and controllers `[cpu memory pids]`.
- The engine had no `localhost/opencode-cli:latest`. Its
  `localhost/opencode-cli:setup-3450e309a6834139be0539695a028f98`
  (`cb50f94ee11b`) predates the OpenCode 1.19.5 pin (`build-inputs-hash`
  `b6c2cfc8...`, inputs `5a57734a...`). The adoption changes no build input.
- `localhost/opencode-cli:latest` `da65a1a29d9f` was rebuilt with
  `--container-build`, `build-inputs-hash` `5a57734a...`, OpenCode 1.19.5 and
  OpenSpec 2.0.0. The runner's network intercepts TLS, so the build used host
  CA trust with the session's CA bundle as the build secret.
- For the guard toolchain,
  `localhost/opencode-guard-toolchain:setup-3450e309a6834139be0539695a028f98`
  was also tagged `localhost/opencode-guard-toolchain:development`, the name
  that `--guard`, `--qualification` and `--network` use.

| Check | Result |
| --- | --- |
| `python3 -m unittest tests.test_reference_copy tests.test_alignment` (host Python, siblings present) | Passed: 26 tests, no skips |
| `bash tools/shellcheck.sh ../opencode-container`, `bash tools/powershell.sh ../opencode-container` (from `sandbox-container`) | Passed: no finding, 62 shim cases |
| `python3 -m unittest discover -s tests` (disposable container, private executable tmpfs) | Passed: 511 tests, 84 skipped. A first run, while the operator's Windows validation loaded the computer, failed two boundary attempts of the timing-sensitive shared `test_lifetime_notice_preserves_status`, which passed in `--wrapper`; the rerun on its own passed |
| `bash tests/run-runtime.sh --wrapper` | Passed: 125 tests, 1 skipped |
| `bash tests/run-runtime.sh --shared` | Passed: 303 tests, 35 skipped. A first run under the same load failed the shared signal test `test_int_and_hup_forwarding`, which passed in `--wrapper`; the rerun on its own passed |
| `bash tests/run-runtime.sh --setup` | Passed: 88 tests |
| `bash tests/run-runtime.sh --setup-runtime` | Passed: 2 tests |
| `bash tests/run-runtime.sh --qualification` | Passed: 31 tests |
| `bash tests/run-runtime.sh --guard` | Passed: 25 tests, 1 skipped (`--guard-idle`) |
| `bash tests/run-runtime.sh --network` | Passed: 22 tests |
| `bash tests/run-runtime.sh` (`test_runtime.py`) | Passed: 23 tests, including the budget checks above |
| `git diff --check` | Passed |

**Windows** (operator, 2026-11-23). Windows WSL 3.0.5.0, kernel 6.18.58.1-1,
Landlock ABI 7. The Podman Desktop machine `podman-machine-default` uses the
`cgroupfs` manager, with Ubuntu running. The checkouts were snapshots of this
branch and of `sandbox-container` in `C:\Work`.

| Step | Result |
| --- | --- |
| Setup from `opencode-container.ps1`: provider networking with the `openrouter` method, shared state, host CA trust with `/etc/ssl/certs/ca-certificates.crt`, permission bypass on, images refreshed | The plan printed `enforced agent budgets: none`, the `cgroupfs` notices and the process rlimit for the agent (512) and the proxy (128). Images built in the machine, `Sandbox qualification: locally-qualified`, `Sandbox: ready`. Setup said `Set $env:OPENROUTER_API_KEY = '...' in PowerShell before opencode-container.ps1`, with no distribution path |
| An OpenCode session with `$env:OPENROUTER_API_KEY` | Provider session with `openrouter-api`, OpenCode 1.19.5, model Flint (free) through OpenRouter. OpenCode ran `ls -la` on the project and read its file with the `read` tool. `$LASTEXITCODE` was 0 after `/exit` and 130 after Ctrl+C, the OpenTUI quit status already recorded on Linux. `podman ps -a` then listed no container of the session (operator) |
| `opencode-container.ps1 run "Say Hello"` | Answered through OpenRouter |
| Native variables: `$env:OPENCODE_CONFIG_CONTENT = '{}'`, then `--container-shell -c 'echo "${OPENCODE_CONFIG_CONTENT-unset}"'` | Printed `unset`; with `$env:OPENCODE_CONTAINER_ENV_VARS = 'OPENCODE_CONFIG_CONTENT'` it printed `{}` |
| `windows-validate.ps1 -Checkout C:\Work\opencode-container -Install -StopMachine`, Windows PowerShell 5.1 | 55 passed, 0 failed, 1 skipped (restricted mode without a prepared installation, because setup saved provider). Installer, user `PATH`, uninstall, stopped machine, a distribution started by WSL alone, the restart with Podman, "Offline qualification", "Offline session", "Redirected input" and "One engine for sessions and the machine" passed |
| The same without `-Install -StopMachine`, PowerShell 7.7.0 | 43 passed, 0 failed, 3 skipped |

Notes:

- **`registry.npmjs.org` is denied in provider sessions.** OpenCode installs
  `@opencode-ai/plugin` in the background and the proxy refuses it
  (`policy-denied`), as recorded on Linux. The sessions are unaffected.
- **An empty first answer.** The first answer of the session, from the
  preselected model `Nano Banana Pro Preview`, was empty (1.7 s); the prompt
  was repeated with Flint (free). The proxy denied no OpenRouter request, so
  it is a model or account matter.
- **The `transport-closed` diagnostic.** At session end, the
  `recent protected egress diagnostics` line with `transport-closed` is the
  behavior already recorded on Linux.
- **The machine keeps the method of the last setup** (`openrouter`).

The installed launcher core, setup and guard change, so installations rerun
`--container-setup`.

## Adoption of `sandbox-ref-36`: 2026-11-27

Change `adopt-sandbox-ref-36`, from `sandbox-ref-28` (`ba1ef14`) directly to
`sandbox-ref-36` (`ce2c9d2`). It takes in `sandbox-ref-29` through
`sandbox-ref-36` and explicitly excludes `add-read-only-dependency-mirror`
(whose code landed on `sandbox-container/main` after `sandbox-ref-36`):
- host Podman delegation is removed in every mode (`OPENCODE_CONTAINER_PODMAN=1`
  stops startup before engine queries with migration guidance) and replaced by a
  private, session-owned rootless Podman engine
  (`localhost/opencode-cli-engine:latest`) whenever the enabled toolchain
  library holds image toolchains;
- toolchains are provisioned from the shipped release catalog
  (`setup/toolchain-catalog/`) and host-side HTTPS archive downloads without
  maintenance consent, with read-only `.images` storage, idle-engine checks on
  image removal, Windows drive-path translation, and automatic re-verification
  during `--container-setup`;
- the process rlimit fallback is set inside each container by its first process
  (never `--ulimit nproc`), verified per container across agent, proxy and
  engine containers;
- nested systemd containers and explicit nested limits on eligible engines, and
  `io.containers.capabilities` (`SETUID,SETGID,SYS_CHROOT,CHOWN`) declared on
  the engine image;
- guarded terminal availability probing (`tests/guard_terminal_probe.py`) and
  runtime-test portability updates.

Copied from `sandbox-container` tag `sandbox-ref-36` (commit `ce2c9d2`):
- updated (29): `launcher/core.sh`, `launcher/windows/bootstrap.sh`,
  `launcher/windows/core.ps1`, `network/README.md`, `network/agent_budgets.py`,
  `network/agent_profile.py`, `network/proxy_hardening.py`,
  `network/qualification_probe.py`, `network/qualification_records.py`,
  `network/qualify.py`, `network/session.py`, `setup/common.py`,
  `setup/launch.py`, `setup/setup.py`, `setup/smoke.py`, `setup/toolchains.py`,
  `tests/fake_podman.py`, `tests/guard_runtime_fixture.py`,
  `tests/network_fixture.py`, `tests/test_alignment.py`, `tests/test_guard.py`,
  `tests/test_launcher.py`, `tests/test_network_feasibility.py`,
  `tests/test_qualification.py`, `tests/test_session.py`, `tests/test_setup.py`,
  `tests/test_toolchains.py`, `tests/test_windows_bootstrap.py`,
  `tests/windows/shim_tests.ps1`;
- added (17): the eight `launcher/engine/` files, `setup/engine.py`, the six
  `setup/toolchain-catalog/` files, `tests/guard_terminal_probe.py` and
  `tests/test_engine.py`;
- removed: none.

The `tests/test_reference_copy.py` manifest moved to `sandbox-ref-36`
(`ce2c9d28873838a4ac541da34edaf7d8b5264be4`, 92 entries). `opencode-container.ps1`,
`.gitattributes`, `Containerfile` (OpenCode `1.19.5`, OpenSpec `2.0.0`),
`.containerignore`, `agent/profile.json`, `agent/launcher.sh` and
`agent/policies/default.json` are unchanged.

OpenCode-specific updates:
- `tests/run-runtime.sh`: removed `OPENCODE_CONTAINER_PODMAN_SOCKET`, selecting
  the Unix socket from `CONTAINER_HOST` or the runtime directory; aligned
  `--shared` with `tests/test_alignment.py` by adding `test_engine`,
  `test_toolchains`, `test_windows_bootstrap`, `test_windows_enter` and
  `test_image_pins`;
- `tests/test_wrapper.py`: removed the synthetic
  `OPENCODE_CONTAINER_PODMAN_SOCKET` fixture, stale `OPENCODE_CONTAINER_PODMAN`
  entry, and duplicate `qualification-input` stub (now provided by
  `synthetic_install`), keeping all OpenCode hooks, provider sets, YOLO,
  integrations and policy checks;
- `tests/test_setup_wrapper.py` and `tests/test_setup_runtime.py`: removed host
  Podman delegation prompts and summary assertions, isolated `XDG_RUNTIME_DIR`
  in synthetic setup tests, asserted schema 3 preferences (`schema_version == 3`,
  `engine_image`, absent `podman` / `delegation_socket`), copied the CA fixture
  into native storage, routed prepared engine image lookups when present, and
  tracked disposable `setup-<release>` runtime, engine, toolchain and proxy tags;
- `tests/test_runtime.py`: removed `test_child_container_host_bind` and legacy
  delegation branches, updated `test_image_default_host_is_removed` and
  `test_containerized_caller_with_remapped_socket` to verify absent
  `CONTAINER_HOST`/`DOCKER_HOST`/host socket and exact
  `OPENCODE_CONTAINER_PODMAN=1` refusal, added
  `test_process_rlimit_counts_per_container`, and ported `SessionEngineTests`
  (6 cases covering workspace binds, caller ownership, read-only store, build/load,
  per-container rlimit, no-engine mode, concurrent isolation, cgroup delegation
  and nested systemd containers) while keeping OpenCode's version, YOLO,
  OpenTUI renderer and state/mount checks;
- `tests/test_network_runtime.py`: installed `setup/engine.py`, `engine.INPUTS`,
  `setup/toolchain-catalog/` and the derived engine seccomp profile; replaced
  delegation checks with exact `OPENCODE_CONTAINER_PODMAN=1` refusal across all
  modes; added `test_offline_session_engine_has_no_external_path`,
  `test_image_recipe_check_runs_without_network`, controller-aware agent/proxy
  budget checks, `test_proxy_starts_beside_containers_holding_more_than_its_budget`,
  bounded cleanup for interrupted fixtures, and `guard_terminal_probe.py` gating
  for guarded terminal cases (keeping pipe cases independently runnable and
  preserving OpenCode's four provider TLS binding checks and synthetic chat-API
  tool call);
- `README.md`, `AGENTS.md`, `docs/setup.md`, `docs/network-contract.md` and
  `openspec/specs/toolchain-library/spec.md` (`## Purpose`): replaced host
  Podman delegation docs with launch service, session container engine,
  container tests, shipped catalog, image recipes, Windows drive paths, schema 3
  migration and in-container process rlimit fallback.

### Working-session checks (2026-11-27)

Environment: guarded sandbox session (`CONTAINER_HOST=tcp://127.0.0.1:2375`,
rootless Linux `cgroupfs`, kernel `6.6.87.2-microsoft-standard-WSL2`), checkout
on DrvFS (`/mnt/d/`, mode `777`). Synthetic suites that require private
executable `0700` storage ran in a disposable offline `localhost/docgen:1.0.0`
container with private executable `tmpfs` (`SANDBOX_TEST_TMPDIR=/sandbox-test-tmp`).
Real OpenCode runtime images (`localhost/opencode-cli:latest`,
`localhost/opencode-guard-toolchain:development`), the engine base image,
`shellcheck`, `pwsh` and host Unix sockets (blocked with `EPERM` by the session
guard) are unavailable in this session.

| Check | Result |
| --- | --- |
| `python3 -B -m unittest tests.test_reference_copy tests.test_alignment -v` (host Python, git and sibling checkouts present) | Passed: 26 tests, 0 skips |
| `python3 -B -m unittest tests.test_wrapper -v` (disposable container, private executable `tmpfs`) | Passed: 14 tests |
| `python3 -B -m unittest tests.test_setup_wrapper -v` (disposable container, private executable `tmpfs`) | Passed: 9 tests |
| `python3 -B -m unittest tests.test_toolchains tests.test_engine -v` (disposable container, private executable `tmpfs`) | Passed: 87 tests |
| `python3 -B -m unittest discover -s tests -p 'test_*.py' -v` (disposable `localhost/docgen:1.0.0` container, private executable `tmpfs`) | 590 tests discovered: 497 passed, 90 opt-in real-engine/sibling skips (`test_runtime` 29, `test_network_runtime` 25, `test_guard` 24, `test_qualification` 7, `test_setup_runtime` 2, `test_network_feasibility` 1, `test_launcher` 1, `test_reference_copy` 1); 3 `test_alignment` harness-only failures/errors (`git` absent in `docgen:1.0.0` and temp-dir parent), all 21 `test_alignment` cases passed on host Python above |
| `bash -n` on all 21 tracked `*.sh` files | Passed |
| `python3 -B -m py_compile` on updated test modules | Passed |
| `git diff --check` | Passed |
| `openspec validate adopt-sandbox-ref-36 --strict` | Passed (0 errors, 0 warnings) |
| Disposable OpenSpec archive/spec-merge preview (`openspec archive --yes` + `openspec validate --specs` in temp copy) | Passed: `container-podman-access` retired, `session-container-engine` created with 20 requirements, launch-engine verification moved to `container-launcher`, OpenCode contracts preserved, 13/13 specs passed |
| `python3 -I ../sandbox-container/tools/propagate.py . sandbox-ref-28 sandbox-ref-36 --checklist` | Generated 13-entry checklist (`runtime`/`toolchain` images, engine build, 9 runner modes, Windows manual step) |
| `bash tests/run-runtime.sh --shared` (preflight check in guarded session) | Failed closed at preflight (exit 125, `socket: operation not permitted` under session guard; `localhost/opencode-cli:latest` absent in session engine) |
| `bash ../sandbox-container/tools/shellcheck.sh .`, `bash ../sandbox-container/tools/powershell.sh .` | Unavailable in session (`shellcheck` and `pwsh` not installed, no offline tool images in session engine) |
| Real-engine runner modes (`--shared`, `--setup`, `--setup-runtime`, `--qualification`, `--wrapper`, default, `--network-feasibility`, `--guard`, `--network`) | Unavailable in session (no `localhost/opencode-cli:latest`, no `localhost/opencode-guard-toolchain:development`, no host Unix Podman service) |
| Authenticated provider checks (`anthropic-api`, `openai-api`, `openrouter-api`, `opencode-zen`) | Not run in session (operator-only; prior `sandbox-ref-28` results remain in history) |
| Windows PowerShell 5.1 validation | Not run in session (Linux session; post-closure follow-up) |

### Follow-up after closure

- On WSL or the native Linux host, from `sandbox-container`:
  `bash tools/adoption-run.sh /mnt/d/Workspace/sandboxes/opencode-container sandbox-ref-28 sandbox-ref-36`: pending
  (prepare `localhost/opencode-cli-engine:latest` and record image IDs,
  `io.containers.capabilities`, runner suites, and any host-specific skips).
- On a Windows host, rerun `--container-setup` from PowerShell and run from
  `sandbox-container`:
  `.\tools\windows-validate.ps1 -Checkout <the Windows checkout>` on Windows
  PowerShell 5.1: pending (verify saved-delegation refusal, library-image
  session with private engine, and interactive OpenTUI).
- Static ShellCheck and PSScriptAnalyzer/shim checks (`tools/shellcheck.sh` and
  `tools/powershell.sh` from `sandbox-container`): pending on host with tool
  images/binaries.
- Cross-repository parity table synchronization (`sandbox-container` and
  sibling wrappers): pending as separate parity step after closure.

The installed launcher core, setup, guard and engine recipe change, and setup
builds `localhost/opencode-cli-engine:latest` and migrates schema 1/2
preferences to schema 3, so existing installations must rerun
`--container-setup`.
