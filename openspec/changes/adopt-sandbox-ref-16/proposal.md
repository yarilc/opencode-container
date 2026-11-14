# Proposal

## Why

claude-container published the operator-managed toolchain library in
`sandbox-ref-13` (change `add-toolchain-library`). The library is one host
directory shared by all five wrappers and mounted read-only at
`/toolchains`. A restricted session can then use Java, Go or another
relocatable toolchain without Podman access, an unrestricted network or a
rebuilt image. Two follow-up tags fixed defects found while the wrappers
adopted it:

- `sandbox-ref-14`: the shared qualification fixture installs `setup/`.
- `sandbox-ref-15`: every `XDG_` variable is protected from toolchains.
  OpenCode places its state with `XDG_CONFIG_HOME`, `XDG_DATA_HOME`,
  `XDG_CACHE_HOME` and `XDG_STATE_HOME`, and Podman keeps the last `--env`,
  so a toolchain could otherwise have moved that state.
- `sandbox-ref-16`: a comment in the shared `setup/toolchains.py` no longer
  names an agent. In OpenCode, the shared agent-identifier scans failed on
  the `sandbox-ref-15` comment, so this change adopts `sandbox-ref-16`.

OpenCode is on `sandbox-ref-12`. Without this change, its shared files diverge
from the reference, its parity table falls behind, and its sessions cannot
see the library. The launcher integration is wrapper code and is ported by
hand, as Codex did in `adopt-sandbox-ref-14`.

## What Changes

- **Adopt `sandbox-ref-16`** with `tools/propagate.py` (`sandbox-ref-12` →
  `sandbox-ref-16`). The tool copies eight shared files byte for byte:
  - added: `setup/toolchains.py`, `tests/test_toolchains.py`;
  - modified: `network/agent_profile.py`, `network/control.py`,
    `network/qualification_records.py`, `setup/common.py`,
    `tests/test_alignment.py`, `tests/test_qualification.py`.

  It also moves the reference manifest and the current-state references to
  the tag.
- **Port the launcher integration to `opencode-container.sh`:**
  - `--container-toolchain add|list|remove|verify` as the first argument,
    dispatched to the shared module before the network mode is read;
  - `OPENCODE_CONTAINER_TOOLCHAINS` (`0`/`false`/`no` omits the mount) and
    `OPENCODE_CONTAINER_TOOLCHAINS_DIR`;
  - the library checked by `launch-env` against the workspace and every
    writable state directory: the isolated `OPENCODE_CONTAINER_STATE_DIR`, or
    the four shared OpenCode directories. It is then mounted at `/toolchains`
    with `ro,nosuid,nodev`;
  - `--mount-target /toolchains` for restricted sessions;
  - default toolchain `PATH` entries appended after the runtime image's
    `PATH`, plus their variables;
  - help text for the option and both variables.
- **Tests:**
  - wrapper cases with the fake engine;
  - real-engine runtime cases;
  - the live add during an offline session in the network runtime suite;
  - adaptations of the existing fixtures that the new mount affects.
- **Test runner:** `tests/run-runtime.sh` gives the suites a private
  executable tmpfs as `SANDBOX_TEST_TMPDIR`, and `tests/test_wrapper.py`
  creates its fixtures there, as in the reference and in Codex.
- **Documentation:**
  - a README "Toolchains" section adapted to OpenCode: the `AGENTS.md`
    instruction line, `/tmp` executable but `/var/tmp` and `/run` not, and
    the XDG protection;
  - the help-related README parts, `AGENTS.md` and `docs/setup.md`
    (requalification).

  The example recipes stay in claude-container and are linked.
- **BREAKING (installation):** the launcher and the qualified shared code
  change, so restricted installations rerun `--container-setup`.

## Capabilities

### New Capabilities

- `toolchain-library`: the shared library, the `--container-toolchain`
  command, the read-only `/toolchains` mount and the default environment in
  OpenCode sessions, and the protected session variables.

### Modified Capabilities

None. Existing requirements do not enumerate the session mounts exhaustively.

## Impact

- The eight shared files, `tests/test_reference_copy.py`, `README.md`,
  `AGENTS.md`, `docs/setup.md`, `docs/network-contract.md` (parity cells),
  `docs/validation.md`.
- `opencode-container.sh`, `tests/test_wrapper.py`, `tests/test_runtime.py`,
  `tests/test_network_runtime.py`, `tests/run-runtime.sh`.
- `main` is one commit ahead of `origin/main` (the archive of
  `use-engine-dev-for-pseudo-terminals`); that stays as it is.
- Out of scope:
  - registry network access for toolchain dependencies;
  - copying the example recipes;
  - the Codex, Pi and Antigravity adoptions of `sandbox-ref-16` (their own
    changes).
