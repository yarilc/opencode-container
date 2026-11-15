# Proposal

## Why

OpenCode is on `sandbox-ref-17`. claude-container has published `sandbox-ref-18`
(change `harden-shared-session-boundaries`), from the cross-wrapper review of
2026-11-14:

- **Agent variables:** the optional profile field `native.protected_env`
  lists the variables and `_`-terminated prefixes the agent itself reads.
  Toolchains cannot set them: `add` rejects them and `launch-env` leaves them
  out with a warning. Without a declaration, OpenCode keeps today's protection.
- **Toolchain check in `/`:** `toolchains.check()` passes `--workdir /`.
- **No state inside the workspace:** the shared `writable_mounts()` refuses
  an isolated state directory that overlaps the workspace, so managed
  launches refuse it.
- **Alignment tests:** the mismatch test runs the real check, which reads the
  launcher's code and its help text separately.

The review also found gaps in OpenCode's own launcher that the reference does not
have:

- **Name collisions (M2):** after a failed create without an ID, any
  existing container with the candidate name counts as a collision
  (`opencode-container.sh:1182`), even when it carries this session's label. The wrapper
  then moves to the next name and leaves its own container behind. The
  reference checks the label first.

## What Changes

- **Adopt `sandbox-ref-18`** with `tools/propagate.py`. The dry run lists
  seven modified shared files (`network/agent_profile.py`, `setup/common.py`,
  `setup/toolchains.py` and four shared tests), nothing added, removed or "not
  adopted", and the manifest moving to commit `958465b`.
- **Declare OpenCode's agent variables** in `agent/profile.json`
  `native.protected_env`: `OPENCODE_`, `ANTHROPIC_`, `OPENAI_`, `OPENROUTER_`, `GEMINI_`, `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, the five `AWS_` Bedrock names and the two `AZURE_` names.
  The launcher filter added by `protect-session-env-from-toolchains` stays as
  defense in depth: it covers the same names.
- **Ownership-checked collisions:** a failed create without an ID counts as a
  collision only when the existing container's session label differs from
  this session's token. Otherwise the wrapper reports the failure and removes
  its own container in cleanup.
- **Tests and docs:** wrapper tests for each new behavior; the README
  "Protected variables" bullet lists the agent variables.
- **Requalification:** shared qualified code changes, so restricted
  installations rerun `--container-setup`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `toolchain-library`: the toolchain check starts in `/`; profile variables
  include the agent variables the profile declares.
- `container-session`: name collisions are confirmed by ownership.

## Impact

- Shared copies: `network/agent_profile.py`, `setup/common.py`,
  `setup/toolchains.py`, `tests/test_agent_profile.py`,
  `tests/test_alignment.py`, `tests/test_setup.py`, `tests/test_toolchains.py`,
  `tests/test_reference_copy.py`.
- OpenCode: `agent/profile.json`, `opencode-container.sh`, `tests/test_wrapper.py`, `README.md`,
  `docs/network-contract.md`, `docs/validation.md` and the documents the tool
  updates.
- Out of scope: credential forwarding (M1), the remaining low-severity review
  items.
