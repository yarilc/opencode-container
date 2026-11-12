# Tasks

## 1. Adopt sandbox-ref-12

- [x] 1.1 From claude-container, run `python3 -I tools/propagate.py
  ../opencode-container sandbox-ref-11 sandbox-ref-12` (dry run). Verify that it
  lists the four modified shared files, nothing added, removed or "not
  adopted", and `REFERENCE_COMMIT` `fd196c9`.
- [x] 1.2 Stash the change directory (`git stash -u`), run `--apply`, and
  restore the stash on branch `adopt-sandbox-ref-12`. Verify:
  - the stash list is empty;
  - `git diff --name-only` lists only the four shared files,
    `tests/test_reference_copy.py` and the four documents;
  - `python3 -m unittest tests.test_reference_copy tests.test_alignment`
    passes.

## 2. Validation and publication

- [x] 2.1 Run the full unit discovery on executable, private, native
  temporary storage. Verify that there are no failures, apart from known
  timing-sensitive tests that pass on a rerun, which are recorded as such.
- [x] 2.2 Run `bash tests/run-runtime.sh` with `--shared`, `--setup`,
  `--setup-runtime`, `--qualification`, `--guard` and `--network`, using the
  current OpenCode runtime image. Verify that every mode passes, or record it as
  unavailable.
- [x] 2.3 Fill in the tool's validation-record template in
  `docs/validation.md` with the results of 2.1–2.2 and the requalification
  note. Verify that the parity table hash matches claude-container's.
- [x] 2.4 Commit on `adopt-sandbox-ref-12` with the tool's message and the
  co-author trailer, merge it into `main` with `--no-ff`, and verify that
  `git log --oneline -3` shows the merge.

## Workflow follow-up

- The operator pushes OpenCode `main` and reruns `--container-setup` where OpenCode is
  installed. The results are added to `docs/validation.md`.
- Sync the delta spec and archive this change after review.
