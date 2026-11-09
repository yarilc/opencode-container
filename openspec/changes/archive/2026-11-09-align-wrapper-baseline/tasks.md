# Tasks

## 1. Renames (A02)

- [x] 1.1 Move `opencode-wrapper` to `opencode-container.sh` with `git mv`, switch the usage text and diagnostics prefix to `opencode-container`, and add the `opencode-wrapper` shim (D2). Verify with wrapper tests: through the old name directly and through a symlink, arguments with spaces, empty strings and `--help` arrive unchanged, the exit status (including 125) is preserved, and exactly one deprecation warning appears; help through the new name shows no warning.
- [x] 1.2 Move `Dockerfile` to `Containerfile` and `.dockerignore` to `.containerignore` with `git mv`, update the allowlist and the wrapper `--file` path (D3). Verify that a wrapper test sees `--file .../Containerfile` on build, and that the runtime `test_build_context` passes with the new names.
- [x] 1.3 Rename the five labels to `io.opencode-container.*` (D5). Verify with wrapper tests: the create arguments carry exactly the new label set and no `io.opencode.` label, and ownership recovery filters on `io.opencode-container.session`.

## 2. Image, version and YOLO controls (A01, A02)

- [x] 2.1 Add version resolution with the deprecated alias, version validation and `OPENCODE_CONTAINER_IMAGE` to the early validation block (D4). Verify with wrapper tests:
  - the default tag;
  - `OPENCODE_CONTAINER_VERSION`;
  - `OPENCODE_VERSION` alone warns and is used;
  - both set, where the new name wins;
  - invalid versions (empty, `a/b`, `1:2`, a space) and an invalid image name exit 1 with no engine call;
  - a custom image is inspected, built and created;
  - `Containerfile` `ARG OPENCODE_VERSION` equals the wrapper default.
- [x] 2.2 Add `OPENCODE_CONTAINER_YOLO` (D1). Verify with wrapper tests:
  - each enabling and disabling word, in mixed case;
  - an invalid value exits 1 before engine calls;
  - enabled YOLO adds the literal `OPENCODE_PERMISSION={"*":"allow"}` after forwarding;
  - disabled YOLO adds nothing;
  - YOLO with a host `OPENCODE_PERMISSION` exits 1 before engine calls;
  - mounts and forwarded names are identical with and without YOLO.

## 3. Tests and helpers (A09)

- [x] 3.1 Update `tests/test_wrapper.py`, `tests/test_runtime.py`, `tests/run-runtime.sh` and `tests/image-smoke.sh` for the new script, recipe and labels, including the `io.opencode-container.acceptance` runner label. Move the image hook of `test_image_default_host_is_removed` to `OPENCODE_CONTAINER_IMAGE`. Verify that a repository grep finds `opencode-wrapper`, `Dockerfile`, `.dockerignore`, `io.opencode.` and `OPENCODE_VERSION` only in the shim, deprecation and migration text, the recipe build argument, validation history and archived changes.
- [x] 3.2 Add the real-engine checks (D7):
  - with `OPENCODE_CONTAINER_YOLO=1`, `opencode debug config` in a real session reports permission `{"*":"allow"}`, and without YOLO it does not;
  - a running session container has only `io.opencode-container.*` labels;
  - a session started through the `opencode-wrapper` shim works and cleans up.

  Verify that `bash tests/run-runtime.sh` passes with no credentials or model requests, including the existing lifecycle, response-validation and OpenTUI tests.

## 4. Documentation (A08)

- [x] 4.1 Restructure `--container-help` into the common layout with every `OPENCODE_CONTAINER_*` variable and its default (D6). Verify that the help test lists all nine variables, the YOLO words and the bypass scope, with no engine call or state creation.
- [x] 4.2 Reorganize the README into the common section order (D6). Document:
  - `opencode-container.sh` installation and the shim;
  - YOLO and its scope;
  - `OPENCODE_CONTAINER_IMAGE` and `OPENCODE_CONTAINER_VERSION`;
  - the label migration with the old and new filters.

  Before editing, record a list of every behavioral statement in the current README, and check each one off against the new text. Verify that the checklist is complete and that `git diff --check` passes.
- [x] 4.3 Reorganize `AGENTS.md` into the common "Repository Guidelines" sections, keeping every OpenCode contract and updating names and commands. Use the same checklist method as 4.2. Verify that the checklist is complete and that the verification commands in `AGENTS.md` run as written: `bash -n`, the unit command and the build command.

## 5. Evidence

- [x] 5.1 Run the full credential-free unit suite in the runner container, `bash -n` on the wrapper, shim and entrypoint, ShellCheck, and `bash tests/run-runtime.sh`. Add a dated `docs/validation.md` section covering:
  - the measured OpenCode facts (strict `--auto` parsing, the `OPENCODE_PERMISSION` merge order);
  - the results;
  - the initial failures and reruns;
  - the user-facing renames.

  Verify that `openspec validate align-wrapper-baseline --strict` passes.
- [x] 5.2 Mark A01, A02 and A09 done and the remaining A08 item done in `todo.md`, with a note naming the change and the evidence section, and update the A10 note that the controls were kept. Verify that the notes are present.

## Workflow follow-up

- Archive, commit and merge when the user asks; the user pushes.
- Continue Wave 2 with OpenCode `align-runtime-image` (A03, A04, A05, A11).
