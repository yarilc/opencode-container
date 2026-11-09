# Tasks

## 1. Baseline

- [x] 1.1 Record a pre-change baseline on the host for `docs/validation.md`:
  - capability sets and `NoNewPrivs`;
  - cgroup `memory.max`, `pids.max` and `cpu.max`;
  - `opencode --version`, `HOME` and the XDG variables inside a session;
  - the tool inventory;
  - the current unit and runtime suite results.

  Verify that the notes are captured in the working notes.

## 2. Image (A03)

- [x] 2.1 Rewrite `Containerfile` per D1, delete `opencode-entrypoint`, and reduce `.containerignore` to `Containerfile` and itself. Build with `--container-build`. Verify:
  - `opencode --version` reports 1.18.3 and `openspec --version` reports 1.16.0;
  - every toolset command exists;
  - `podman image inspect` shows no user-specific build argument and an `opencode` entrypoint.
- [x] 2.2 Add `tests/test_image_pins.py` per D5. Verify that it passes, and that it fails on mutated copies: a tag-only base, `@latest`, an unversioned package, the third-party OpenCode image, or a missing toolset package.

## 3. Wrapper (A03, A04, A05)

- [x] 3.1 Switch the default image to `localhost/opencode-cli:latest`, remove version resolution and the user build arguments, and add the ignored-version warning (D2). Verify with wrapper tests:
  - the default and custom image names;
  - no `--build-arg` on build;
  - one warning each for `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION`, with the session continuing.
- [x] 3.2 Implement the shared-mode home layout (D3): the tmpfs `/opencode-home`, `HOME` and the XDG variables, the four validated host directories at their fixed destinations, and `.agents` at `/opencode-home/.agents`. Verify with wrapper tests:
  - the exact destinations and variables;
  - nonstandard and symlinked host XDG bases;
  - the existing state validation cases still failing before image operations;
  - no host-path XDG destinations.
- [x] 3.3 Implement `OPENCODE_CONTAINER_STATE_DIR` (D3). Verify with wrapper tests:
  - creation of the directory and the four subdirectories with private modes;
  - the bind at `/opencode-home` and no tmpfs home;
  - no host XDG mounts;
  - relative, empty, insecure, foreign-owned and workspace-overlapping values exit 1 with no engine call.

## 4. Session baseline (A11)

- [x] 4.1 Port the budget validation, workspace guard and lifetime validation (D4), and move the workspace computation into the early block. Verify with wrapper tests ported from Codex:
  - default and overridden budgets, and every rejected form;
  - each refused root, the worktree parent equal to the home, a symlink to `/etc`, `/mnt/d` refused while a project below it is accepted, and the exact and non-exact override;
  - unset, `0`, valid and invalid lifetimes.

  Every refusal must happen with no engine call or state creation.
- [x] 4.2 Replace the fixed `--pids-limit=512` with the budget arguments, and add `--timeout`, the post-create inspection and the lifetime notice (D4). Verify with wrapper tests:
  - the flags in normal, shell, YOLO and delegated launches;
  - matching, missing and different limits, and an inspection failure, each removing only the owned container without start;
  - the notice after a slow non-zero client.

## 5. Real-engine checks

- [x] 5.1 Update `tests/test_runtime.py`, `tests/run-runtime.sh` and `tests/image-smoke.sh` per D5, and set the override in fixtures that launch from refused directories. Verify that `bash tests/run-runtime.sh` passes on the host with no credentials or model requests, including:
  - OpenTUI on glibc;
  - effective budgets with default and overridden values, with and without delegation;
  - process-limit enforcement;
  - lifetime expiry, recording the observed status, and early exit;
  - the refused home;
  - persistence in shared and isolated modes;
  - the tool inventory;
  - the existing lifecycle, response-validation, delegation and worktree tests.

## 6. Documentation and evidence

- [x] 6.1 Update `--container-help`, the README and `AGENTS.md`:
  - the image and toolset;
  - the pinned versions and the "Updating pinned image inputs" procedure, with the provider-metadata and permission rechecks;
  - the home layout, shared and isolated state;
  - budgets, lifetime, the refused set and override, and the storage-growth statement;
  - the cgroup controller requirement;
  - the AVX2 build-host note;
  - the migration from per-user images and the ignored version variables.

  Verify that a help test lists all new variables with defaults, and that `bash -n` and `git diff --check` pass.
- [x] 6.2 Run the full credential-free unit suites in the runner container, ShellCheck and `bash tests/run-runtime.sh`. Add a dated `docs/validation.md` section covering the baseline comparison, the npm channel facts, the results, the initial failures and reruns, the lifetime status, the pinned versions and the limitations. Verify that `openspec validate align-runtime-image --strict` passes.
- [x] 6.3 Mark A03, A04, A05, A10 and A11 in `todo.md` with an implementation note, and note in the Wave 2 status that OpenCode is complete. Verify that the notes name the change and the evidence section.

## Workflow follow-up

- Archive, commit and merge when the user asks; the user pushes.
- Continue Wave 2 with Pi (`narrow-exposed-state` first).
