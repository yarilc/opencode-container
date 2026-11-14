# Proposal

## Why

OpenCode is on `sandbox-ref-16`. claude-container has published
`sandbox-ref-17` (change `share-toolchain-env-across-profiles`), which makes
the toolchain library work the same way in every wrapper:

- **Neutral variables:** `DBUS_SESSION_BUS_ADDRESS` joins the variables that
  every wrapper protects. No session has a bus.
- **Profile variables:** previously, if a toolchain in the shared index set a
  variable that only the current wrapper protects, `launch-env` refused the
  whole library. This happens when another wrapper installed the toolchain,
  for example one that sets `CLAUDE_CONFIG_DIR`. `launch-env` now leaves that
  variable out of the session and prints one warning naming the toolchain.

Without this change, OpenCode's copy of the shared module differs from the
reference, and a toolchain installed from another wrapper can block every
OpenCode session that uses the library. claude-container, Antigravity and
Codex already run `sandbox-ref-17`.

The dry run of `tools/propagate.py ../opencode-container sandbox-ref-16
sandbox-ref-17` lists:

- two modified files: `setup/toolchains.py` and `tests/test_toolchains.py`;
- nothing added, removed or "not adopted";
- the manifest moving to commit `a23f155`.

## What Changes

- **Adopt `sandbox-ref-17`** with `tools/propagate.py`. The tool copies the
  two shared files byte for byte. It also moves the reference manifest and
  the current-state references (`README.md`, `AGENTS.md`, `docs/setup.md`,
  `docs/network-contract.md`, including the parity cells) to the tag.
- **Rewrite the README "Protected variables" bullet** for the two groups:
  - the neutral variables, including `DBUS_SESSION_BUS_ADDRESS`. The bullet
    keeps the note that OpenCode places its state with the `XDG_` variables.
  - OpenCode's own variables: `OPENCODE_CONTAINER_*`, which covers its
    configuration and approval variables, and the four credential variables
    `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY` and
    `OPENCODE_API_KEY`. `add` rejects them. If another wrapper's toolchain
    sets one, `launch-env` leaves it out of the session with a warning.
- **Update the spec:** the protected-variables requirement in
  `toolchain-library` takes the reference's text.
- **No launcher change.** `opencode-container.sh` reads only the standard
  output of `launch-env`, and the warnings go to standard error, so they reach
  the user unchanged. `setup/toolchains.py` is qualified code, so restricted
  installations rerun `--container-setup`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `toolchain-library`: protected variables are now neutral or profile
  variables. The bus variable is protected. A variable that another wrapper's
  toolchain sets in the shared index is left out with a warning, instead of
  failing the session.

## Impact

- `setup/toolchains.py`, `tests/test_toolchains.py`,
  `tests/test_reference_copy.py`, `README.md`, `AGENTS.md`, `docs/setup.md`,
  `docs/network-contract.md`, `docs/validation.md`.
- Out of scope: Pi, which gets its own change.
