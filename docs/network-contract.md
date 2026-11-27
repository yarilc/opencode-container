# Network policy contract

Status: ported by the `add-network-egress` and `add-container-setup` changes.
- Restricted modes, guided setup and the managed launcher are implemented and verified with synthetic and real rootless runtime suites; setup is described in [docs/setup.md](setup.md).
- The authenticated provider checks are operator-run and recorded separately in [the validation record](validation.md).

The durable contract is [network-egress](../openspec/specs/network-egress/spec.md),
with [host-ca-trust](../openspec/specs/host-ca-trust/spec.md) and the session,
isolation, session container engine, launcher and image specifications in
`openspec/specs/`.

## Reference and intentional differences

The shared components are copied unchanged from `sandbox-container` at tag
`sandbox-ref-36` (commit `ce2c9d28873838a4ac541da34edaf7d8b5264be4`):

- `launcher/` (the shared launcher core, Windows entry helpers and session engine recipe);
- `network/` (except the build output `network/bin/`);
- `setup/` (including `setup/engine.py` and `setup/toolchain-catalog/`);
- the shared tests listed in that tag's `tests/test_alignment.py`.

`sandbox-ref-5` is `sandbox-ref-2` plus three shared-test fixes that this port
found:
- the guarded production test mounts a writable profile home (`sandbox-ref-3`),
  because OpenCode writes there even for `--version`;
- the setup test supports API-key-only profiles (`sandbox-ref-4`);
- the setup test supports a nested configuration home such as
  `.config/opencode` (`sandbox-ref-5`).

`tests/test_reference_copy.py` holds the SHA-256 of every copied file. It fails
on a changed, missing or extra file; the unchanged `tests/test_alignment.py`
fails on a profile identifier (`opencode`, `anthropic`, `openai`,
`openrouter`) in a shared file and checks the wrapper against the profile. A defect in a shared
file is fixed in `sandbox-container` first and then copied; this repository
never carries a fork. [network/README.md](../network/README.md) is part of the
copy and describes the shared mechanism in agent-neutral terms.

Intentional differences are limited to per-agent files:

| File | OpenCode value or behavior |
| --- | --- |
| `agent/profile.json` | Identity: `opencode-container`, prefix `OPENCODE_CONTAINER`, labels `io.opencode-container.*`. Images: `localhost/opencode-cli` (engine image derived as `localhost/opencode-cli-engine`), `localhost/opencode-egress`, `localhost/opencode-guard-toolchain`. Runtime: home `/opencode-home`, command `opencode`. State: configuration `.config/opencode` with override `OPENCODE_CONTAINER_CONFIG_DIR`, plus shared `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode`. Approval: `OPENCODE_CONTAINER_YOLO`. Executable temporary storage (`native.exec_tmp`). Four API-key methods |
| `agent/policies/default.json` | `anthropic-api`, `openai-api`, `openrouter-api` and `opencode-zen`, revision `opencode-2026-11-10-v1` |
| `opencode-container.sh` | The thin entry script, identical to the reference's apart from the wrapper name |
| `agent/launcher.sh` | OpenCode's data for the shared core: `AGENT_EXEC=/usr/local/bin/opencode`, executable temporary storage, one credential per policy profile, the fixed XDG bases, protected `OPENCODE_DISABLE_*=1` values in restricted sessions; hooks for `OPENCODE_CONTAINER_PROVIDER`, the native variables, the read-only integrations, the YOLO permission and the help |
| `Containerfile`, `.containerignore` | OpenCode image; copies `network/relay.py` and `network/mux.py` |
| `tests/test_wrapper.py`, `test_setup_wrapper.py`, `test_setup_runtime.py`, `test_runtime.py`, `image-smoke.sh`, `test_network_runtime.py`, `network_tls_fixture.py`, `run-runtime.sh`, `test_image_pins.py`, `test_reference_copy.py` | OpenCode names, synthetic OpenAI-compatible Chat Completions fixture, provider host inventories |

## Modes

| Mode | Agent access | Session container engine |
| --- | --- | --- |
| unset or empty | `provider`; without the provider settings the launch stops with setup guidance before engine calls and state creation | As `provider` when configured; host delegation (`OPENCODE_CONTAINER_PODMAN=1`) rejected |
| `offline` | Own loopback, pipes and connected socket pairs only | Private rootless engine when library holds images, sharing offline network namespace; host delegation rejected |
| `provider` | As offline, plus one preconnected channel to an exact-destination proxy | Private rootless engine when library holds images, sharing provider network boundary; host delegation rejected |
| `unrestricted` (explicit only) | Ordinary runtime networking | Private rootless engine when library holds images, sharing session network; host delegation (`OPENCODE_CONTAINER_PODMAN=1`) rejected |

Unknown modes fail before image operations. Restricted failures never retry
with unrestricted networking. None of the following can broaden the outer
policy:
- workspace and application settings, including `opencode.json` and `OPENCODE_CONFIG*`;
- plugins and permission settings;
- YOLO and shell mode.

Restricted agents have no direct route, external resolver, UDP/QUIC,
host/LAN/metadata access or proxy administration access. Every agent
container, in every mode, drops all capabilities, enables no-new-privileges
and has verified memory, CPU and process budgets.

The relay sets `NO_PROXY=localhost,127.0.0.1,::1`. OpenTUI and `opencode run
--attach` reach the local OpenCode server over loopback without the relay;
with an empty `NO_PROXY` that connection fails. Named Unix sockets and host
services are unavailable. The OpenCode 1.19.5 TUI starts and renders under
these constraints. The image provides `bwrap` as a general tool.

Restricted launches follow the Claude wrapper order:
1. arguments;
2. mode and legacy delegation refusal;
3. budgets and lifetime;
4. engine verification;
5. restricted platform queries;
6. state;
7. CA;
8. `network/session.py prepare`;
9. image operations under the maintenance gate;
10. the immutable image ID;
11. `network/qualify.py check`;
12. `session.py start` and `agent-args`;
13. owned create and start;
14. `session.py stop` within the remaining shutdown budget.

## Provider profiles

| Profile | Destinations | Credential | Status |
| --- | --- | --- | --- |
| `anthropic-api` | `api.anthropic.com:443` | `ANTHROPIC_API_KEY` | Measured on 1.19.5 with a dummy key |
| `openai-api` | `api.openai.com:443` | `OPENAI_API_KEY` | Measured on 1.19.5 with a dummy key |
| `openrouter-api` | `openrouter.ai:443` | `OPENROUTER_API_KEY` | Measured on 1.19.5 with a dummy key |
| `opencode-zen` | `opencode.ai:443` (Zen `https://opencode.ai/zen/v1`) | `OPENCODE_API_KEY` | Measured on 1.19.5 with a dummy key |

In provider mode the profile selects the only forwarded credential.
`OPENCODE_CONTAINER_PROVIDER` must be unset, `none` or the matching provider,
and `OPENAI_BASE_URL` is never forwarded. Offline sessions forward no provider
variable. A key stored by `opencode auth login` also works, because the profile
restricts hosts, not credential sources. Cloud providers, custom `baseURL`
values, other gateways, local model servers and OAuth or browser-callback logins
have no profile and are unsupported in restricted modes.

Restricted sessions set `OPENCODE_DISABLE_AUTOUPDATE`, `..._DEFAULT_PLUGINS`,
`..._LSP_DOWNLOAD`, `..._MODELS_FETCH` and `..._SHARE` to `1` after
forwarding and after the toolchain variables. A toolchain cannot set any
`OPENCODE_` or provider variable: the launcher leaves it out with a warning.
In 1.19.5, `OPENCODE_DISABLE_MODELS_FETCH` suppresses requests to
`models.opencode.ai` and leaves the bundled catalog available.
`OPENCODE_DISABLE_AUTOUPDATE` suppresses the startup update check even with
`autoupdate: true`. Starting with 1.19.0, installation of updates requires
an explicit action.
`OPENCODE_DISABLE_DEFAULT_PLUGINS` skips built-in plugins and
`OPENCODE_DISABLE_LSP_DOWNLOAD` blocks automatic LSP downloads.

Session sharing was discontinued in 1.19.1. The wrapper still sets
`OPENCODE_DISABLE_SHARE` for older releases. A background configuration
dependency install and explicit `opencode upgrade` still contact
`registry.npmjs.org`. The proxy denies both requests.

## Limits

- The proxy binds the initial and retried TLS ClientHello server name
  (`tls-clienthello-sni-v2`) to the CONNECT host; TLS 1.2 renegotiation is
  encrypted and not inspected.
- It does not prove exclusive communication with the operator's provider
  account: the HTTP `Host`, shared-service routing and provider-side forwarding
  stay opaque. `opencode.ai` also serves other OpenCode web content.
- Allowed services can receive data: an injected agent can send workspace data
  to an allowed host with an attacker's key or account. Only `offline` removes
  this.
- Provider-hosted tools such as web search run outside the local boundary.
- LSP servers are not preinstalled and cannot be downloaded in restricted
  modes; plugins named in configuration cannot be installed from npm.
- Image pulls and build `RUN` steps happen outside runtime filtering and need
  separate maintenance authorization.
- Qualification reports are local (`locally-qualified`); the release
  acceptance inventory is empty.

## Five-wrapper parity

The same OpenCode row appears in `sandbox-container`, `claude-container`, `codex-container`, `antigravity-container` and `pi-container`.

| Wrapper | Contract adoption | Implementation | Real enforcement | Auth compatibility |
| --- | --- | --- | --- | --- |
| Sandbox (reference) | Reference (`sandbox-ref-36`, shared launcher core) | Guard, qualification and guided setup integrated; session container engine for image toolchains, with systemd in nested containers, host Podman delegation removed; Windows entry on a Podman machine (WSL provider) with installer, offline and unrestricted modes; no provider mode (no authentication method); provider mechanics covered by the fixture profile and the fixture agent part | WSL ABI 3: all runner modes passed (2026-11-22); `sandbox-ref-29` to `sandbox-ref-31` runner modes in a nested `cgroupfs` engine passed except the recorded budget and explicit-limit tests, `sandbox-ref-32` and `sandbox-ref-33` modes from a session passed except the nested-engine cases, `sandbox-ref-34` all modes from a session passed except the nested-engine cases and the tests that need cgroup limits, and its engine case passed on the machine's engine (2026-11-24), `sandbox-ref-35` all modes passed natively, the terminal tests included (2026-11-25), `sandbox-ref-36` the unit discovery, default, network, qualification, setup and setup runtime modes passed natively, the terminal tests included, and the engine started without a capability error (2026-11-26); Podman machine on Windows: validation script passed on both PowerShell editions (2026-11-21) and on 5.1 with the session engine (2026-11-24), nested systemd: runtime and qualification modes passed on the machine's engine (2026-11-26); native Linux (Rocky 9, Podman 5.8.0, `systemd` with `memory` and `pids`, no IPv6): `sandbox-ref-34` engine budgets and offline engine sessions verified, `sandbox-ref-35` every mode passed with the guarded terminal tests unavailable, and a terminal attached in an interactive session (2026-11-25), `sandbox-ref-36` the same modes as on WSL passed with the guarded terminal tests unavailable, and an unrestricted session started its engine without a capability error (2026-11-26) | Not applicable |
| Claude | Adopted `sandbox-ref-36`: shared launcher core | Shared launcher core, mandatory bootstrap, multiplexed proxy and guided setup integrated; session container engine for image toolchains, with systemd in nested containers, host Podman delegation removed; Windows entry on a Podman machine (WSL provider) with installer and every network mode | WSL ABI 3: all runner modes passed on `sandbox-ref-28` (2026-11-22); `sandbox-ref-34` modes from a Claude session with its engine passed except the nested-engine cases and the tests that need cgroup limits, and the engine and setup runtime cases passed on the machine's engine (2026-11-25), `sandbox-ref-35` unit discovery, guard, network, feasibility and setup runtime modes passed natively, the terminal tests included, with the interrupted-creation case passing alone after timeouts in the full network run (2026-11-25), and `sandbox-ref-36` unit tests of the changed files, setup, setup runtime, qualification and wrapper modes and the engine cases of the runtime and network suites passed natively, the other modes not rerun (2026-11-26); Podman machine on Windows: setup, account login, a Claude session and the validation script on both PowerShell editions passed (2026-11-22), and the validation script on 5.1 with the session engine (2026-11-24); native Linux (Rocky 9, Podman 5.8.0, `systemd` with `memory` and `pids`, no IPv6): `sandbox-ref-35` unit discovery, guard, network, feasibility and setup runtime modes passed with the guarded terminal tests unavailable, and a terminal attached in an interactive session (2026-11-25) | Account login, reuse and refresh passed; operator session with tool use passed (2026-11-11, `anthropic-account`); real-key API unavailable |
| Codex | Adopted `sandbox-ref-36`: shared launcher core | Shared launcher core, guard, multiplexed proxy, qualification and guided setup integrated; session container engine for image toolchains, with systemd in nested containers, host Podman delegation removed; Windows entry on a Podman machine (WSL provider) with installer and every network mode | WSL ABI 3: all runner modes passed on `sandbox-ref-28` (2026-11-22), and on `sandbox-ref-36` natively, the terminal tests and the engine cases included, with the shared and wrapper modes passing on a rerun after timing failures under load (2026-11-26); Podman machine on Windows: setup, device-code login, a Codex session, Codex's own sandbox in `unrestricted` and the validation script on both PowerShell editions passed (2026-11-22), the `sandbox-ref-36` smoke test pending (release risk) | Operator session with tool use passed (2026-11-11, `openai-account`; 2026-11-22 on Windows); refresh and real-key API checks pending; synthetic Responses API streaming and tool call passed |
| Antigravity | Adopted `sandbox-ref-28`: shared launcher core | Shared launcher core, guard, multiplexed proxy, qualification and guided setup integrated; keyring removed; Windows entry on a Podman machine (WSL provider) with installer and every network mode, no delegation | WSL ABI 3: all runner modes passed on `sandbox-ref-28` (2026-11-23); Podman machine on Windows: setup, Google sign-in, an `agy` session with tool use, token reuse, the Gemini API key method with a dummy key and the validation script on both PowerShell editions passed (2026-11-23) | Operator session with tool use passed (2026-11-11, `google-account`, policy `antigravity-2026-11-11-v2`; 2026-11-23 on Windows); refresh and real-key Gemini API checks pending; synthetic Gemini streaming and tool call passed |
| OpenCode | Adopted `sandbox-ref-36`: shared launcher core | Shared launcher core, guard, multiplexed proxy, qualification and guided setup integrated; private session container engine for image toolchains with nested systemd, host Podman delegation removed; Windows entry on a Podman machine (WSL provider) with installer and every network mode | WSL ABI 3: all runner modes passed on `sandbox-ref-28` (2026-11-23); Podman machine on Windows: setup, an OpenCode session with tool use (`openrouter-api`), native variables through `OPENCODE_CONTAINER_ENV_VARS` and the validation script on both PowerShell editions passed (2026-11-23); `sandbox-ref-36` shared manifest, alignment, static checks, OpenSpec merge preview and full non-runtime synthetic suites passed in the working session (2026-11-27), production WSL/Linux and Windows checks scheduled after closure | Operator session with tool use passed (2026-11-11, `anthropic-api`; 2026-11-23 on Windows, `openrouter-api`); the `openai-api` and `opencode-zen` profiles pending; synthetic Chat Completions streaming and tool call passed |
| Pi | Adopted `sandbox-ref-28`: shared launcher core | Shared launcher core, guard, multiplexed proxy, qualification and guided setup integrated; Windows entry on a Podman machine (WSL provider) with installer and every network mode, no delegation | WSL ABI 3: all runner modes passed on `sandbox-ref-28` (2026-11-23); Podman machine on Windows: setup, a Pi session with tool use (`openrouter-api`), `PI_NPM_CACHE_SIZE` through `PI_CONTAINER_ENV_VARS` and the validation script on both PowerShell editions passed (2026-11-23) | Operator session with tool use passed (2026-11-11, `anthropic-api`; 2026-11-23 on Windows, `openrouter-api`); the `openai-api` and `gemini-api` profiles pending; synthetic Chat Completions streaming and tool call passed |

## Port status

| Item | Status |
| --- | --- |
| Shared copy and identifier scan | Done (`tests/test_reference_copy.py`) |
| Shared suites, guard, mux, policy, feasibility, qualification | Passed in the runner; see [validation](validation.md) |
| Wrapper integration and restricted runtime acceptance | Passed; see [validation](validation.md) |
| Shared setup suite and alignment | Passed (`tests/test_setup.py`, `tests/test_alignment.py`) |
| Guided setup acceptance | Passed; see [validation](validation.md) |
| Authenticated provider checks | Operator-run, pending |
