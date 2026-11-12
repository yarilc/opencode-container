# Proposal

## Why

claude-container published `sandbox-ref-12` with two shared fixes found while
the wrappers adopted `sandbox-ref-11`:

- Qualification containers started from the runtime image without
  `--workdir`, so the engine created and chowned a missing image `WORKDIR`.
  On the Rocky Linux 9 lab host that fails for a domain UID under
  `--userns=keep-id`. OpenCode avoided it by creating `/workspace` in its image.
  The shared code should not depend on that.
- A shared setup test assumed a recipe-built runtime. It passes in OpenCode
  (`runtime_build: recipe`) but failed in Pi.

OpenCode is on `sandbox-ref-11` and must adopt the tag to keep its shared files
identical to the reference and its parity table aligned.

## What Changes

- Adopt `sandbox-ref-12` with `tools/propagate.py` (`sandbox-ref-11` →
  `sandbox-ref-12`). The tool copies four shared files byte for byte:
  - `network/qualify.py` and `network/qualification_records.py`: every
    qualification container from the runtime image passes `--workdir /`;
  - `tests/test_qualification.py` and `tests/test_setup.py`: the new
    workdir tests, and the runtime-build test pinned to `recipe`.

  It also moves the reference manifest and the current-state references
  (`README.md`, `AGENTS.md`, `docs/setup.md`, `docs/network-contract.md`,
  including the parity cells) to the tag.
- No OpenCode launcher, recipe or wrapper-test change. OpenCode keeps its own
  `/workspace` creation in the image.
- The shared code digests in the qualification identity change, so
  restricted installations rerun qualification.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `network-egress`: qualification containers do not depend on the runtime
  image's working directory.

## Impact

- The four shared files, `tests/test_reference_copy.py` and the four
  documents listed above, plus `docs/validation.md` (adoption record).
- `main` is one commit ahead of `origin/main` (the archive of
  `adopt-lab-host-fixes`). That is unrelated and stays as it is.
