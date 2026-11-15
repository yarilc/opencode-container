# Design

## Context

See proposal.md for the problem. The relevant launcher flow today:

1. `:277-335` builds `provider_names`, `ALL_PROFILE_NAMES`, `PROTECTED_FLAGS`
   and the operator's extra names.
2. `:676-697` runs `setup/toolchains.py launch-env` and collects
   `toolchain_env` (`--env NAME=VALUE`) and `toolchain_path`. `launch-env`
   output carries no toolchain name, and `launch-env` has already dropped
   neutral and `OPENCODE_CONTAINER_*`/credential variables.
3. `:750-783` forwards variables by name, then appends the restricted-mode
   protected flags, the CA paths and the YOLO literal.
4. `:887-899` resolves the session image, computes
   `PATH=<image PATH><toolchain_path>` and appends it with `toolchain_env`.

Podman applies `--env` options in order, and the last one for a name wins.

## Goals / Non-Goals

**Goals:**
- No toolchain value reaches an OpenCode-owned or provider variable.
- Forwarded values and protected literals always come after toolchain values.

**Non-Goals:**
- Changing shared code (`setup/toolchains.py`, `agent/profile.json` schema).
  That is the reference change `harden-shared-session-boundaries`.
- Credential forwarding rules (review finding M1).

## Decisions

### Filter in the launcher, by prefix and provider list

The launcher drops a toolchain variable when its name starts with `OPENCODE_`
or appears in `ALL_PROFILE_NAMES`. Each dropped name gets one warning:
`opencode-container: toolchain environment: skipping <NAME>, which the wrapper
protects`. It goes on standard error before the session starts.

- The `OPENCODE_` prefix covers today's controls (`OPENCODE_PERMISSION`,
  `OPENCODE_CONFIG*`, `OPENCODE_DISABLE_*`, `OPENCODE_SERVER_*`) and any
  control a later OpenCode release adds. A legitimate toolchain has no reason
  to configure the agent.
- `ALL_PROFILE_NAMES` already lists every provider credential and endpoint
  the launcher manages (`OPENAI_BASE_URL`, `AWS_*`, `AZURE_*`).
- Alternative: an exact list of today's names. Rejected: it would miss new
  OpenCode controls.
- Alternative: fail the session. Rejected: the shared `launch-env` warns and
  continues for profile variables, and another wrapper's toolchain must not
  block OpenCode.

The warning names the variable only: the launcher does not receive the
toolchain name from `launch-env`. The shared change will report it.

### Move the toolchain variables before forwarding

The filtered `toolchain_env` is appended to `run_args` just before the
forwarding loop (`:750`). The `PATH` entry stays at `:897`, since it needs
the session image. Neither forwarding nor the protected literals set `PATH`,
and `launch-env` refuses a toolchain `PATH` variable, so its position does
not matter for precedence.

Alternative: move the protected-literal block after `:899`. Rejected: forwarded
operator values would still lose to toolchain values.

## Risks / Trade-offs

- [A toolchain that sets a provider variable on purpose, for example a
  proxy-aware SDK] → It now loses that variable with a warning. The operator
  forwards it with `OPENCODE_CONTAINER_ENV_VARS` instead.
- [Precedence regresses in a later edit] → The new test asserts the final
  value of each protected name, which depends on the order.
- [The launcher and the shared filter disagree after the shared change] → The
  launcher's rule is a superset. The adoption change decides whether to keep
  it.

## Migration Plan

Launcher-only change. No requalification: `setup/` and `network/` are
unchanged, and qualification probes run with the toolchain mount disabled.
Rollback is a revert of the merge.
