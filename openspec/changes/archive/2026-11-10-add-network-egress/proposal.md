# Proposal

## Why

Every OpenCode session runs with unrestricted networking today. A prompt-injected agent, a plugin, an MCP server or any tool it runs can therefore reach any host, the LAN and host services. `claude-container` at tag `sandbox-ref-3` implements this protection in agent-neutral shared components (`network/`, `agent/profile.json`), and `codex-container` already runs them unchanged. This change ports that final state to OpenCode as the first of its two consolidated Wave 3 changes. `add-container-setup` follows with guided setup and the managed launcher.

## What Changes

- **BREAKING** `OPENCODE_CONTAINER_NETWORK` selects `offline`, `provider` or `unrestricted`.
  - An unset or empty mode stops ordinary launches before any engine call, with a message asking for an explicit mode. `add-container-setup` later replaces that message with `--container-setup` guidance. This follows the operator decision of 2026-11-09 applied to Codex, which replaces the "default offline" decision of 2026-11-08 recorded in `todo.md`.
  - Unknown values fail before image operations.
  - Restricted failures never fall back to unrestricted networking.
- **BREAKING** Image builds, including the automatic build of a missing image, require the exact `OPENCODE_CONTAINER_MAINTENANCE=1` in every mode. A provider proxy image is pulled only under the same authorization and only by digest.
- **BREAKING** `OPENCODE_CONTAINER_PODMAN=1` is rejected in `offline` and `provider` before image or resource operations. Delegation remains available only with explicit `unrestricted`.
- **BREAKING (shared state layout)** Shared OpenCode state uses fixed host paths: `~/.config/opencode`, `~/.local/share/opencode`, `~/.cache/opencode` and `~/.local/state/opencode`. The wrapper no longer derives them from the host `XDG_*_HOME` variables. The new `OPENCODE_CONTAINER_CONFIG_DIR` overrides the configuration directory only. This is the layout the shared `qualify.py` and setup code model (one configuration directory plus directories fixed below `$HOME`); the operator chose it on 2026-11-10 instead of extending the shared schema. `OPENCODE_CONTAINER_STATE_DIR` is unchanged and conflicts with a nonempty `OPENCODE_CONTAINER_CONFIG_DIR`.
- Copy `network/` unchanged from `claude-container` `sandbox-ref-3`. It contains:
  - the static Landlock ABI ≥ 3 and seccomp guard (`sandbox-egress-guard`);
  - the multiplexed relay and egress proxy, with initial and retried TLS ClientHello SNI binding (`tls-clienthello-sni-v2`);
  - protected policy and installation checks;
  - proxy hardening (no capabilities, 128 processes, 256 MiB);
  - platform eligibility, local qualification and its records;
  - the shared session helper (`prepare`, `start`, `agent-args`, `stop`).

  It also includes `setup/diagnostics.py`, which `network/control.py` verifies when present.
- Add `agent/profile.json`, the single source of OpenCode-specific values, and `agent/policies/default.json` with four exact API-key profiles, chosen by the operator on 2026-11-10:
  - `anthropic-api`: `api.anthropic.com:443`, key `ANTHROPIC_API_KEY`;
  - `openai-api`: `api.openai.com:443`, key `OPENAI_API_KEY`;
  - `openrouter-api`: `openrouter.ai:443`, key `OPENROUTER_API_KEY`;
  - `opencode-zen`: the OpenCode Zen gateway hosts measured on OpenCode 1.18.3, key `OPENCODE_API_KEY`.

  The policy is dated and versioned, with no wildcards. Cloud providers, custom `baseURL` values, other gateways, local model servers and OAuth or browser-callback logins are not profiles in this change.
- In provider sessions, the profile selects the single forwarded credential. `OPENCODE_CONTAINER_PROVIDER` must be unset, `none` or the matching provider, and the URL-selecting `OPENAI_BASE_URL` is not forwarded. Offline sessions forward no provider credential.
- In restricted sessions, the host proxy variables are no longer forwarded. The shared helper sets only the relay values and the loopback `NO_PROXY=localhost,127.0.0.1,::1`, which keeps the OpenTUI connection to its local server working. `OPENCODE_CONTAINER_ENV_VARS` cannot name proxy or CA variables there.
- In provider sessions, disable OpenCode's optional traffic with protected environment values that the writable OpenCode configuration cannot override: automatic updates, default plugin downloads, LSP downloads, the remote model catalog and session sharing, as supported by 1.18.3. Any control that is missing is documented, and the proxy denies that traffic anyway.
- Add `--container-qualify` and require a current local qualification report before every ordinary `offline` or `provider` launch. The report is bound to the boot, engine, security policy, code, images, policy, profile, CA and hardening settings.
- Port opt-in host CA trust (`OPENCODE_CONTAINER_TRUST_HOST_CA`, `OPENCODE_CONTAINER_CA_BUNDLE`) with a read-only bundle at `/opencode-home/ca/bundle.pem` and the standard CA variables. Restricted launches use an immutable runtime image ID.
- The runtime image copies `network/relay.py` and `network/mux.py`, and `.containerignore` admits only these files besides `Containerfile`. The pinned OpenCode version must equal the policy's `tested.cli`.
- Port the shared tests, adapt the wrapper and runtime tests, and record real rootless evidence in `docs/validation.md`. The documentation covers:
  - the README and wrapper help;
  - `AGENTS.md`;
  - `docs/network-contract.md`;
  - `network/README.md`;
  - the residual exfiltration disclosure for the four provider profiles.

Out of scope, deferred to `add-container-setup`:
- `--container-setup`, `setup/` other than `diagnostics.py`, `setup.json` and the managed launcher;
- the setup acknowledgement of residual exfiltration;
- `docs/setup.md` and the missing-setup admission message;
- the OpenCode row of the five-wrapper parity table.

## Capabilities

### New Capabilities

- `network-egress`: operator-selected network modes, the native IPC and network guard, the multiplexed egress proxy with exact destination and SNI binding, protected policies and agent profile, the four OpenCode provider profiles, optional-traffic suppression, the loopback bypass for OpenTUI, platform prerequisites, credential-free local qualification, owned proxy lifecycle, redacted diagnostics and documented limits.
- `host-ca-trust`: opt-in exposure of one host CA bundle, read-only at `/opencode-home/ca/bundle.pem`, with the standard CA variables.

### Modified Capabilities

- `container-session`: explicit network-mode admission, the required current local qualification for restricted launches, consistent restricted prerequisite decisions, and qualification binding of hardening settings.
- `container-isolation`:
  - fixed shared state paths and `OPENCODE_CONTAINER_CONFIG_DIR`;
  - the conflict between isolated state and the configuration override;
  - restricted-mode forwarding: no host proxy variables and the profile-selected credential.
- `container-podman-access`: socket delegation is accepted only in explicit unrestricted mode.
- `container-launcher`: builds require exact maintenance authorization, help describes the new modes and variables, and `--container-qualify` is a wrapper option.
- `runtime-image`:
  - restricted launches use an immutable image ID;
  - the build context admits the relay and multiplex inputs;
  - the pinned CLI matches the policy's tested version.

## Impact

- **Code:**
  - `opencode-container.sh` gains:
    - mode parsing and preflight;
    - calls to `network/session.py`;
    - `--container-qualify`;
    - fixed state paths, CA handling and the maintenance gate;
    - restricted forwarding rules.

    The restricted lifecycle stays in the shared helper.
  - New files: `network/` (copied unchanged), `setup/diagnostics.py`, `agent/`.
  - `Containerfile` and `.containerignore` change.
- **Tests:**
  - the shared tests copied from Claude (the `tests/test_alignment.py` list), except `test_alignment.py` and `test_setup.py`, which arrive with `add-container-setup`; until then a per-agent `tests/test_reference_copy.py` checks the copy against `sandbox-ref-3`;
  - adapted `test_wrapper.py`, `test_runtime.py` and `run-runtime.sh`, plus a new `test_network_runtime.py` with `network_tls_fixture.py`;
  - `test_image_pins.py` checks `tested.cli`.
- **Users:**
  - existing launches must set `OPENCODE_CONTAINER_NETWORK=unrestricted` to keep today's networking;
  - first builds need `OPENCODE_CONTAINER_MAINTENANCE=1`;
  - users with a custom `XDG_*_HOME` must move their OpenCode state to the fixed paths, or use `OPENCODE_CONTAINER_CONFIG_DIR` or `OPENCODE_CONTAINER_STATE_DIR`;
  - restricted modes need:
    - host Python 3;
    - a same-host rootless Podman ≥ 4.9 Unix service with Netavark;
    - Landlock ABI ≥ 3;
    - a passing `--container-qualify`.
- **Compatibility risks, measured before porting code:**
  - the Bun runtime honoring the proxy variables for HTTPS, SSE streaming and WebSockets, and the CA variables;
  - OpenTUI, the local OpenCode server, LSP and plugins using only loopback TCP, which the guard allows, and no Unix sockets;
  - OpenCode's own `bubblewrap` use, if any, under the guard;
  - the exact OpenCode Zen hosts and the optional-traffic controls in 1.18.3;
  - the executable `/tmp` and `/opencode-home` that OpenTUI needs, under the guard's mount-layout checks.
