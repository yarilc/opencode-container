# Proposal

## Why

The cross-wrapper review of 2026-11-14 (finding H1) found that a toolchain in
the shared library can change OpenCode's security settings:

- `opencode-container.sh` appends the toolchain variables (`:899`) after the
  protected `OPENCODE_DISABLE_*=1` literals (`:767-772`) and after the YOLO
  `OPENCODE_PERMISSION` literal (`:780-783`). Podman keeps the last `--env`
  for a name, so the toolchain value wins, in restricted modes too.
- Reordering alone is not enough. Without YOLO the launcher sets no
  `OPENCODE_PERMISSION` at all, so a toolchain that sets
  `OPENCODE_PERMISSION={"*":"allow"}` or `OPENCODE_CONFIG_CONTENT` bypasses
  approvals with nothing to override it.
- The shared `setup/toolchains.py` protects only the `OPENCODE_CONTAINER_*`
  prefix and the four credential variables. The library is shared, so a
  toolchain installed from another wrapper reaches OpenCode sessions.

This contradicts the `toolchain-library` requirement "Session variables are
protected from toolchains" and the `network-egress` protected-values
requirement. The shared fix (a per-profile list of agent-owned variables) needs
a new reference tag. This change closes the hole in OpenCode now, without
waiting for it.

## What Changes

- **Launcher filter:** a toolchain variable whose name starts with
  `OPENCODE_`, or that is one of the provider variables the launcher knows
  (`ANTHROPIC_API_KEY`, `OPENAI_BASE_URL`, `AWS_*` for Bedrock, and the other
  names in the provider list), is left out of the session with one warning
  per variable. This matches how the shared `launch-env` treats profile
  variables.
- **Ordering:** the remaining toolchain variables are added before the
  forwarded variables and before the protected literals, so the operator's
  forwarded values, the restricted-mode protected values and YOLO always win.
  The toolchain `PATH` entry keeps its place: it needs the image's `PATH`, and
  no later value sets `PATH`.
- **Tests:** `tests/test_wrapper.py` gets a case with a default toolchain that
  sets the protected flags, `OPENCODE_PERMISSION`, `OPENCODE_CONFIG_CONTENT`
  and `OPENAI_BASE_URL`, in restricted and unrestricted modes, with and
  without YOLO.
- **Docs:** the README "Protected variables" bullet and
  `docs/network-contract.md` state that OpenCode's own `OPENCODE_*` variables
  and the provider variables are protected from toolchains.
- No shared file changes, so no requalification and no reference-copy drift.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `toolchain-library`: a new requirement makes the launcher leave
  OpenCode's own `OPENCODE_*` variables and the provider variables out of the
  session, and keeps toolchain variables below forwarded and protected ones.
- `network-egress`: the protected values also win over toolchain variables.

## Impact

- `opencode-container.sh`, `tests/test_wrapper.py`, `README.md`,
  `docs/network-contract.md`, `docs/validation.md`.
- Follow-up outside this change: the shared `native.protected_env` list in
  claude-container (change `harden-shared-session-boundaries`), adopted here
  with the next reference tag. The launcher filter can then stay as defense
  in depth.
