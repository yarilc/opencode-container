# Network policy contract

Status: ported by the `add-network-egress` and `add-container-setup` changes.
- Restricted modes, guided setup and the managed launcher are implemented and verified with synthetic and real rootless runtime suites; setup is described in [docs/setup.md](setup.md).
- The authenticated provider checks are operator-run and recorded separately in [the validation record](validation.md).

The durable contract is [network-egress](../openspec/specs/network-egress/spec.md),
with [host-ca-trust](../openspec/specs/host-ca-trust/spec.md) and the session,
isolation, delegation, launcher and image specifications in `openspec/specs/`.

## Reference and intentional differences

The shared components are copied unchanged from `claude-container` at tag
`sandbox-ref-5` (commit `3388b6ee45a1b9943f8f4aed77c0b1740a9ab4f8`):

- `network/` (except the build output `network/bin/`);
- `setup/`;
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
file is fixed in `claude-container` first and then copied; this repository
never carries a fork. [network/README.md](../network/README.md) is part of the
copy and describes the shared mechanism in agent-neutral terms.

Intentional differences are limited to per-agent files:

| File | OpenCode value or behavior |
| --- | --- |
| `agent/profile.json` | Identity: `opencode-container`, prefix `OPENCODE_CONTAINER`, labels `io.opencode-container.*`. Images: `localhost/opencode-cli`, `localhost/opencode-egress`, `localhost/opencode-guard-toolchain`. Runtime: home `/opencode-home`, command `opencode`. State: configuration `.config/opencode` with override `OPENCODE_CONTAINER_CONFIG_DIR`, plus shared `.local/share/opencode`, `.cache/opencode` and `.local/state/opencode`. Approval: `OPENCODE_CONTAINER_YOLO`. Four API-key methods |
| `agent/policies/default.json` | `anthropic-api`, `openai-api`, `openrouter-api` and `opencode-zen`, revision `opencode-2026-11-10-v1` |
| `opencode-container.sh` | OpenCode arguments; fixed shared state paths or isolated state; executable `/tmp` and `/opencode-home`; protected `OPENCODE_DISABLE_*` values; profile-selected credential; no host proxy or CA variables in restricted modes; missing-mode message without setup |
| `Containerfile`, `.containerignore` | OpenCode image; copies `network/relay.py` and `network/mux.py` |
| `tests/test_wrapper.py`, `test_runtime.py`, `test_network_runtime.py`, `network_tls_fixture.py`, `run-runtime.sh`, `test_image_pins.py`, `test_reference_copy.py` | OpenCode names, synthetic OpenAI-compatible Chat Completions fixture, provider host inventories |

## Modes

| Mode | Agent access | Socket delegation |
| --- | --- | --- |
| unset or empty | Launch stops before engine calls and state creation | No session |
| `offline` | Own loopback, pipes and connected socket pairs only | Rejected |
| `provider` | As offline, plus one preconnected channel to an exact-destination proxy | Rejected |
| `unrestricted` (explicit only) | Ordinary runtime networking | Exact opt-in allowed |

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
services are unavailable. OpenCode 1.18.3 needs none for `run`, its tools or
the TUI. It does not use the `bwrap` in the image.

Restricted launches follow the Claude wrapper order:
1. arguments;
2. mode and delegation;
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
| `anthropic-api` | `api.anthropic.com:443` | `ANTHROPIC_API_KEY` | Measured on 1.18.3; real key unverified |
| `openai-api` | `api.openai.com:443` | `OPENAI_API_KEY` | Measured on 1.18.3; real key unverified |
| `openrouter-api` | `openrouter.ai:443` | `OPENROUTER_API_KEY` | Measured on 1.18.3; real key unverified |
| `opencode-zen` | `opencode.ai:443` (Zen `https://opencode.ai/zen/v1`) | `OPENCODE_API_KEY` | Measured on 1.18.3; real key unverified |

In provider mode the profile selects the only forwarded credential.
`OPENCODE_CONTAINER_PROVIDER` must be unset, `none` or the matching provider,
and `OPENAI_BASE_URL` is never forwarded. Offline sessions forward no provider
variable. A key stored by `opencode auth login` also works, because the profile
restricts hosts, not credential sources. Cloud providers, custom `baseURL`
values, other gateways, local model servers and OAuth or browser-callback logins
have no profile and are unsupported in restricted modes.

Restricted sessions set `OPENCODE_DISABLE_AUTOUPDATE`, `..._DEFAULT_PLUGINS`,
`..._LSP_DOWNLOAD`, `..._MODELS_FETCH` and `..._SHARE` to `1` after
forwarding. As measured on 1.18.3, these values win over `opencode.json`
(`autoupdate`, `share: "auto"`). Two requests have no control:
- the background install of `@opencode-ai/plugin` into each configuration directory;
- an explicit `opencode upgrade`.

Both contact `registry.npmjs.org`. The proxy denies them, and startup continues
with a warning. Session sharing uses `opncd.ai`, which no profile allows.

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

The same OpenCode row appears in `claude-container` and `codex-container`.

| Wrapper | Contract adoption | Implementation | Real enforcement | Auth compatibility |
| --- | --- | --- | --- | --- |
| Claude | Reference (`sandbox-ref-5`) | Mandatory bootstrap, multiplexed proxy and guided setup integrated | See the Claude validation record | Account login, reuse and refresh passed; real-key API unavailable |
| Codex | Ported from `sandbox-ref-5`; shared files unchanged | Guard, multiplexed proxy, qualification and guided setup integrated | WSL ABI 3: all runtime modes and setup acceptance passed (2026-11-09) | Pending operator device-code login, refresh and API-key checks; synthetic Responses API streaming and tool call passed |
| Antigravity | Pending (profile-based port planned) | Not assessed | Not assessed | Not assessed |
| OpenCode | Ported from `sandbox-ref-5`; shared files unchanged | Guard, multiplexed proxy, qualification and guided setup integrated | WSL ABI 3: all runtime modes and setup acceptance passed (2026-11-10) | Pending operator API-key checks for the four profiles; synthetic Chat Completions streaming and tool call passed |
| Pi | Pending (profile-based port planned) | Not assessed | Not assessed | Not assessed |

## Port status

| Item | Status |
| --- | --- |
| Shared copy and identifier scan | Done (`tests/test_reference_copy.py`) |
| Shared suites, guard, mux, policy, feasibility, qualification | Passed in the runner; see [validation](validation.md) |
| Wrapper integration and restricted runtime acceptance | Passed; see [validation](validation.md) |
| Shared setup suite and alignment | Passed (`tests/test_setup.py`, `tests/test_alignment.py`) |
| Guided setup acceptance | Passed; see [validation](validation.md) |
| Authenticated provider checks | Operator-run, pending |
