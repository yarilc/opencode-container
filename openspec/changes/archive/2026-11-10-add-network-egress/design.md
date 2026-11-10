# Design

## Context

See `proposal.md`. The reference is `claude-container` at tag `sandbox-ref-3` (merge `449ce60`; `sandbox-ref-2` plus the guard test home fix found by this port). `codex-container` completed the same port on 2026-11-09 and 2026-11-10 (`add-network-egress`, then `add-container-setup`). Its archived change is the template for this one, including the measured pitfalls:
- the rustls fixture certificate needed `CA:FALSE`;
- an inner sandbox could not run under the guard;
- a shared test expected the Claude wording of an engine message.

**Reference.**
- `network/` and the shared tests listed in its `tests/test_alignment.py` contain no agent identifiers.
- Every agent value comes from `agent/profile.json`, through `network/agent_profile.py`.
- The shared model of host state is:
  - one configuration directory, named by `native.config_dir_env` or found at `$HOME/<native.config_home>`;
  - extra directories fixed at `$HOME/<native.shared_dirs[i]>`;
  - an isolated home selected by `<PREFIX>_STATE_DIR`, which conflicts with a nonempty `config_dir_env`.
- `network/qualify.py` (`writable()`) and, later, `setup/common.py` use this model for the protected-installation overlap checks and the questionnaire.
- The shared session helper sets `HTTP(S)_PROXY` in both cases and `NO_PROXY=localhost,127.0.0.1,::1`, and clears every inherited proxy variable.

**Current OpenCode wrapper.** `opencode-container.sh` (697 lines) already has:
- the hardened baseline: no capabilities, no-new-privileges, verified budgets, workspace guard and optional lifetime;
- atomic naming, signal forwarding, bounded owned cleanup and same-host Unix engine verification;
- `OPENCODE_CONTAINER_STATE_DIR` (isolated `/opencode-home` with the four XDG subtrees);
- the by-name allowlist, with `OPENCODE_CONTAINER_PROVIDER` and `OPENCODE_CONTAINER_ENV_VARS`;
- the YOLO switch, which sets `OPENCODE_PERMISSION={"*":"allow"}`.

It has no network modes, CA trust or maintenance gate. It builds missing images automatically and forwards host proxy variables in its base allowlist. Shared state is four directories, `$XDG_*_HOME/opencode`, each defaulting under `$HOME`, mounted below a `/opencode-home` tmpfs that allows execution. `/tmp` also allows execution, which OpenTUI requires.

**Runtime image.** The image is the Debian `node:22-bookworm-slim` base pinned by digest. It installs `opencode-ai@1.18.3` (a Bun-compiled platform binary), `python3`, `ca-certificates` (which pulls `openssl`, used by the qualification fixture) and `bubblewrap`. The `todo.md` notes about Alpine, `opencode-entrypoint`, `Dockerfile` and per-user tags predate Wave 2 and are obsolete.

**Coupling.** As for Codex, copying `network/` unchanged brings qualification (C09), CA trust (C02) and the state model into this change.

## Goals / Non-Goals

**Goals:**
- `network/` and `setup/diagnostics.py` byte-identical to `sandbox-ref-3`. OpenCode differences stay only in `agent/`, the wrapper, the image files and the per-agent tests.
- Restricted OpenCode sessions behave like restricted Claude and Codex sessions, including interactive OpenTUI. An `unrestricted` mode behaves like today's wrapper, apart from the fixed state paths.
- Measured answers to the OpenCode-specific risks before the wrapper integration is written.

**Non-Goals:**
- Guided setup, the managed launcher, `setup.json`, release rollback and the setup acknowledgement (all in `add-container-setup`).
- Changes to shared files or to the profile schema. A defect is fixed in `claude-container` first.
- Profiles beyond the four API-key profiles: cloud providers, custom `baseURL`, local model servers, GitHub Copilot and OAuth logins.
- Release acceptance entries and authenticated provider checks in automated tests.

## Decisions

### Copy the reference tree from the tag

As for Codex: `git -C ../claude-container archive sandbox-ref-3 network setup/diagnostics.py <shared tests>`, without `test_alignment.py` and `test_setup.py`. Until `add-container-setup` arrives, the per-agent `tests/test_reference_copy.py` checks:
- the SHA-256 manifest;
- missing or extra files;
- the identifier scan;
- an optional `diff -r` against a sibling checkout.

The Codex version of that test is reused with OpenCode names.

### Fixed shared state paths (operator decision of 2026-11-10)

The profile declares:
- `config_home`: `.config/opencode`;
- `shared_dirs`: `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode`;
- `config_dir_env`: `OPENCODE_CONTAINER_CONFIG_DIR`.

The wrapper mounts exactly these host paths. It no longer derives them from host `XDG_*_HOME`, which the shared code does not model. `OPENCODE_CONTAINER_CONFIG_DIR` is a new host-side override for the configuration directory only, validated like the other state. It conflicts with `OPENCODE_CONTAINER_STATE_DIR`, as the shared code requires. In the container the XDG variables stay fixed at `/opencode-home/...`, so OpenCode itself is unaffected.

`CONFIG_DIR` is not one of the profile's reserved suffixes, so the schema accepts the name. It is never forwarded into the container.

Alternatives considered:
- extending the shared schema in Claude, which needs a new tag and a Codex re-copy;
- isolated state only for restricted modes, which diverges from Claude and Codex setup.

Both were rejected by the operator.

### Missing mode is an explicit-selection error until setup exists

Codex follows the operator decision of 2026-11-09: no default mode, and a message naming `OPENCODE_CONTAINER_NETWORK`, its values and `unrestricted` as the previous behavior. `add-container-setup` replaces only the message. The 2026-11-08 "default offline" note in `todo.md` is superseded and is updated when the tasks are checked off.

### Follow the Claude wrapper order of checks

The order is the same as Claude and Codex:
1. arguments;
2. mode and delegation;
3. budgets and lifetime;
4. engine;
5. restricted platform queries;
6. state;
7. CA;
8. `session.py prepare`;
9. image operations under the maintenance gate;
10. immutable image ID;
11. `qualify.py check`;
12. `session.py start` and `agent-args`;
13. owned create and start;
14. `session.py stop`.

The OpenCode-specific provider and allowlist checks belong to step 1 or 2, before engine calls. The existing lifecycle code stays.

### OpenCode agent profile

| Field | Value |
| --- | --- |
| `name` / `wrapper` | `opencode-container` / `opencode-container.sh` |
| `env_prefix` | `OPENCODE_CONTAINER` |
| `label_namespace` | `io.opencode-container` |
| `identifiers` | `opencode`, `anthropic`, `openai`, `openrouter` (scan result checked in task 1.2) |
| `images` | `localhost/opencode-cli`, `localhost/opencode-egress`, `localhost/opencode-guard-toolchain` |
| `install.state_name` | `opencode-egress` |
| `native.home` / `command` | `/opencode-home` / `opencode` |
| `native.approval_bypass_env` | `OPENCODE_CONTAINER_YOLO` |

Authentication methods. Each method has one policy profile and one `credential_env`, and none has `login_args`:

| Method | Policy profile | Hosts | Credential |
| --- | --- | --- | --- |
| `anthropic` | `anthropic-api` | `api.anthropic.com` | `ANTHROPIC_API_KEY` |
| `openai` | `openai-api` | `api.openai.com` | `OPENAI_API_KEY` |
| `openrouter` | `openrouter-api` | `openrouter.ai` | `OPENROUTER_API_KEY` |
| `opencode-zen` | `opencode-zen` | measured | `OPENCODE_API_KEY` |

The method names match the existing `OPENCODE_CONTAINER_PROVIDER` values where one exists. An `opencode auth login` API-key entry stored in the data directory also works, because the profile restricts hosts, not credential sources.

### Credentials and forwarding in restricted modes

- **Offline** forwards no provider variable.
- **Provider** forwards only the profile's `credential_env`. `OPENCODE_CONTAINER_PROVIDER` must be unset, `none` or the provider of the selected profile; otherwise the wrapper stops before engine calls. The mapping is `anthropic`→`anthropic-api`, `openai`→`openai-api`, `openrouter`→`openrouter-api` and `opencode`→`opencode-zen`. `OPENAI_BASE_URL` is not forwarded.
- **Both restricted modes** drop from the base allowlist the eight proxy variables and the CA variables. `OPENCODE_CONTAINER_ENV_VARS` names them, and the protected optional-traffic variables, as authoritative (skipped with a warning).
- **Unrestricted** is unchanged.

Credentials of other providers listed explicitly in `OPENCODE_CONTAINER_ENV_VARS` are still forwarded. They cannot broaden the network, and the operator chose to list them.

### Optional traffic uses protected environment values

OpenCode reads `OPENCODE_DISABLE_*` and similar flags from the environment. In restricted modes the wrapper appends them after forwarding as literal `--env NAME=VALUE` settings, so they override any inherited value. The candidates are:
- `OPENCODE_DISABLE_AUTOUPDATE` (already set in the image);
- `OPENCODE_DISABLE_DEFAULT_PLUGINS`;
- `OPENCODE_DISABLE_LSP_DOWNLOAD`;
- `OPENCODE_DISABLE_MODELS_FETCH`;
- a share control.

Task 2.2 verifies each against the 1.18.3 binary. `opencode.json` can set `share`, `autoupdate` and plugins, so the measurement also records whether the environment wins over the writable configuration. Where it does not, the residual behavior is documented, and the proxy still denies hosts outside the profile.

Session sharing deserves care: with `opencode-zen`, the gateway host may coincide with the share service. Disabling share is then the only control, and the residual exfiltration disclosure names it.

### OpenCode client through the relay

The Bun runtime should honor `HTTPS_PROXY` and `NO_PROXY` for `fetch`, and `NODE_EXTRA_CA_CERTS` or `SSL_CERT_FILE` for trust. This is measured with the synthetic provider fixture before integration (task 2.3). The fixture is the shared `network_tls_fixture.py` pattern with a `CA:FALSE`, `serverAuth` leaf certificate.

OpenTUI talks to its local server over `127.0.0.1`, which the loopback `NO_PROXY` covers. An incompatible transport fails closed and is documented. The allowlist is never broadened and the guard is never weakened.

### Local tools under the guard

OpenTUI, the local server, LSP servers, formatters, plugins and local MCP servers must work with loopback TCP, pipes and connected pairs only. Task 2.4 runs:
- an interactive PTY session (start, local server, quit);
- a shell command through OpenCode's bash tool;
- a bundled LSP or formatter, if any is preinstalled.

All run under the guard in offline mode. Any Unix-socket dependency is recorded and documented. OpenCode's possible use of `bubblewrap`, which is installed in the image, is checked as for Codex. If it cannot run under the guard, the documented outcome follows the Codex precedent, and the guard is never weakened.

### Executable temporary storage stays

`/tmp` and `/opencode-home` stay executable tmpfs mounts. The guard checks that the private `/tmp`, `/run` and `/var/tmp` hierarchies are not host binds. Task 2.5 runs the guard runtime fixtures on the OpenCode layout. If they fail, the finding goes to Claude.

### Proxy and guard artifacts without setup

These are the same operator build inputs as Codex:
1. the toolchain image `localhost/opencode-guard-toolchain`;
2. `network/build-guard.sh` under maintenance;
3. `localhost/opencode-egress` from `network/Containerfile`.

`docs/validation.md` records the commands and image IDs.

## Risks / Trade-offs

- **Every existing invocation breaks until a mode is set, and custom `XDG_*_HOME` users lose their state location.** Mitigation: the error message names `unrestricted`, and the README migration section covers both breaks, including the move to `OPENCODE_CONTAINER_CONFIG_DIR` or `OPENCODE_CONTAINER_STATE_DIR`.
- **Bun ignores proxy or CA variables for some transport.** Mitigation: that traffic fails closed and is measured and documented. The allowlist is not broadened.
- **The OpenCode Zen gateway shares hosts with other opencode.ai services (share, catalog, auth).** Mitigation: exact hosts only; protected disable flags; disclosure that any allowed host can receive data.
- **Writable configuration re-enables a feature that the environment disables.** Mitigation: measured in task 2.2. The proxy still limits destinations to the profile, and the gap is documented.
- **LSP servers or plugins need Unix sockets or downloads.** Mitigation: they fail under the guard. Downloads are disabled in restricted modes, and preinstallation is left to a later maintenance change.
- **A defect in a shared file shows up during the port.** Mitigation: stop, fix it in `claude-container`, and recopy.
- **Change size.** About 5,000 lines are copied, plus wrapper and test work. Mitigation: the same task order as Codex, with the shared suites passing first.

## Migration Plan

1. To keep today's behavior, users set `OPENCODE_CONTAINER_NETWORK=unrestricted` and add `OPENCODE_CONTAINER_MAINTENANCE=1` to commands that build. Users with custom `XDG_*_HOME` move their OpenCode directories, or set `OPENCODE_CONTAINER_CONFIG_DIR` or `OPENCODE_CONTAINER_STATE_DIR`.
2. Restricted use requires, in order:
   1. the operator build inputs;
   2. `OPENCODE_CONTAINER_NETWORK=offline bash ./opencode-container.sh --container-qualify`;
   3. ordinary launches.

   Provider mode adds the proxy image and `OPENCODE_CONTAINER_NETWORK_PROFILE`, `..._NETWORK_POLICY` and `..._NETWORK_RUNTIME_DIR`.
3. Rollback: check out the previous `main` merge (`46546ca`). The state directories are the default paths, so they are untouched.

## Open Questions

- The exact OpenCode Zen hosts, the optional-traffic controls and their precedence over `opencode.json`. Both are measured in task group 2 and do not change the spec shape.
- Whether OpenCode 1.18.3 uses `bubblewrap` or Unix sockets in any default path. This is measured in task 2.4.
