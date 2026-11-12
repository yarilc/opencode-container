# Design

## Context

OpenCode `main` (`df43216`) pins `sandbox-ref-11`. The dry run of
`tools/propagate.py ../opencode-container sandbox-ref-11 sandbox-ref-12` reports:

- four modified files (`network/qualification_records.py`,
  `network/qualify.py`, `tests/test_qualification.py`, `tests/test_setup.py`);
- nothing added, removed or "not adopted";
- the manifest moving to commit `fd196c9`;
- four documents.

`network/qualification_records.py` and `network/qualify.py` are code inputs
of the qualification identity, so existing reports become stale. OpenCode's own
recipe already creates `/workspace` (change `adopt-lab-host-fixes`, task 4.1), so the new
`--workdir /` changes no observed behavior here. It only removes the
dependency on the image.

## Goals / Non-Goals

**Goals:**
- OpenCode adopts `sandbox-ref-12` byte for byte.
- Its parity table again matches claude-container's.

**Non-Goals:**
- Any wrapper-owned change.
- The Bun question, which concerns Pi only.

## Decisions

1. **Use the documented procedure as it is**: dry run, `--apply` on branch
   `adopt-sandbox-ref-12`, the runner modes the tool lists, the validation
   record from the tool's template, and one `--no-ff` merge. The change
   directory is stashed around `--apply`, because the tool refuses untracked
   files.
2. **Runner scope.** The tool lists `--shared`, `--setup`, `--setup-runtime`,
   `--qualification`, `--guard` and `--network`. The changed files affect
   setup tests and qualification, so `--setup`, `--qualification` and
   `--shared` are required. The other three modes are run too, because the
   procedure lists them.

## Risks / Trade-offs

- [A wrapper-specific literal in a changed shared test] → The unit
  discovery and `test_alignment` catch it. A shared defect stops the
  adoption, per `docs/propagation.md`.
- [Qualification reports become stale] → Setup requalifies. The operator
  reruns `--container-setup`.

## Migration Plan

1. Merge `adopt-sandbox-ref-12` with `--no-ff`. The operator pushes it.
2. Rerun `--container-setup` on the hosts in use.
3. Rollback before the push: reset `main` to `df43216`.
