# Design

## Context

OpenCode `main` (`59e04b2`) pins `sandbox-ref-10`. Running
`tools/propagate.py` from `sandbox-ref-10` to `sandbox-ref-11` reports the
same 21 modified shared files as for Codex, with nothing added, removed or
"not adopted". It lists these runner modes: `--shared`, `--setup`,
`--setup-runtime`, `--qualification`, `--guard` and `--network`.

Codex followed the same path in `adopt-lab-host-fixes`, archived on
2026-11-12. That change found:

- 21 wrapper tests fail on the shared files alone, because the fixture
  lacks `network/agent_budgets.py` and an answer to the controller query.
  The OpenCode fixture (`tests/test_wrapper.py` around line 1062) has the
  same file list, so it fails the same way;
- a `WORKDIR` declared after the last build step is in no layer. The gate
  containers then make Podman chown it, which fails on the Rocky host's
  domain UID. The OpenCode recipe ends with `COPY ...`, `WORKDIR /workspace`
  and `ENTRYPOINT`, so `/workspace` is missing in the same way.

The OpenCode launcher differs from the Codex launcher in these points:

- it uses `capture_response <var> <command>`, like the reference;
- the socket check requires `true\n/...` before extracting the path
  (around line 505), so a `unix://` value is rejected by the pattern
  before any prefix could be removed;
- one `build_current_image` function holds the only `podman build` call;
- the inspection compares the exact `memory cpu pids` triple (around line
  1065), and the help text states that budgets require all three
  controllers;
- mounts:
  - `/tmp` is `exec` 512 MiB, for OpenTUI;
  - `/var/tmp` (512 MiB) and `/run` (32 MiB) are `noexec`;
  - the home is a 512 MiB `exec` tmpfs;
- `.containerignore` uses anchored `/` patterns.

## Goals / Non-Goals

**Goals:**
- OpenCode adopts `sandbox-ref-11` byte for byte, with launcher and recipe
  behavior equivalent to the reference and to Codex.
- OpenCode's own mounts, sizes and messages stay as they are, except where
  the specs change.

**Non-Goals:**
- Changing the shared files or the guard's `/run/secrets` rule.
- `--workdir /` for the shared gate containers, which goes to a
  claude-container change and `sandbox-ref-12`.
- Plugin and network-mode behavior. The README section "Plugins and network
  modes" stays as it is.

## Decisions

1. **Single branch.** `propagate.py --apply` creates `adopt-sandbox-ref-11`,
   and every wrapper adaptation is committed on it before one `--no-ff`
   merge. The tool refuses untracked files, so the change directory is
   stashed (`git stash -u`) around `--apply` and restored on the branch, as
   in Codex.

2. **Socket URL.** Strip `unix://` from the second response line before the
   pattern check. The pattern then still requires `true` and an absolute
   path, so `unix://relative`, `unix://` and `unix:///` fail as before.

3. **Budgets.** Use the reference block as it is, with the
   `opencode-container:` prefix and `capture_response`:
   - query `{{.Host.CgroupControllers}}` in every mode after the
     launch-engine checks, and validate it with
     `^\[([a-z_]+( [a-z_]+)*)?\]$`;
   - build `budget_args`, with `--pids-limit=-1` when `pids` is missing;
   - print one notice per missing controller;
   - at inspection, accept `0` or `-1` for unenforced pids and `0` for
     unenforced memory and CPU. The diagnostic names the reported
     controllers.

   The help text describes the conditional enforcement.

4. **Mounts.** Remove `--read-only-tmpfs=false` and add
   `--mount type=tmpfs,destination=/run/secrets,ro=true`, a
   `--tmpfs /dev:rw,nosuid,noexec,mode=755,size=65536k`,
   `--mount type=devpts,destination=/dev/pts` and
   `--mount type=tmpfs,destination=/dev/shm,ro=true`. `/tmp`, `/var/tmp`,
   `/run` and the home tmpfs are unchanged.

5. **Build secret.** `build_current_image` adds
   `--secret id=build-ca,src=<bundle>` when `ca_bundle` is set. The bundle
   is resolved before the build (around line 611), so no reordering is
   needed. `.containerignore` gains `!/podman-build-secret*`, in the anchored
   style.

6. **Recipe.** Use the reference HTTPS prologue as it is:
   - the Node.js root export;
   - the optional `build-ca` append;
   - the `sed` to `https://`;
   - `Acquire::https::CAInfo` on both apt calls;
   - `rm -f` of the bundle before `npm install`.

   Keep OpenCode's package list, the version `test`s and the cleanup. The
   step ends with `mkdir -m 1777 /opencode-home && mkdir -p /workspace`, so
   the working directory is root-owned 755 in the layer.

7. **Tests.**
   - `tests/test_wrapper.py`:
     - the fixture copies `network/agent_budgets.py`, and the fake engine
       answers `{{.Host.CgroupControllers}}` from `FAKE_CONTROLLERS`, by
       default `[cpu memory pids]`;
     - the fake inspection reports `0` for unrequested memory and CPU;
     - new cases cover controller subsets, unverifiable lists,
       unenforced-or-missing inspection, the socket URL, the device and
       secret mounts in every mode, and the build secret with and without
       trust;
     - the existing `--read-only-tmpfs=false` and tmpfs-list assertions are
       updated.
   - `tests/test_image_pins.py` gains the reference's transport and
     toolchain checks and Codex's workdir check, with OpenCode wording.

## Risks / Trade-offs

- [OpenTUI or other tools may need POSIX shared memory, but `/dev/shm` is
  read-only] → The runtime suite's `test_opentui_renderer` and
  `test_tools_without_capabilities` cover it. A break is recorded in
  `docs/validation.md` and needs a new change, not a writable `/dev/shm`.
- [Unenforced memory or process budgets let a session exhaust host
  resources] → The notices are printed on every launch and in the setup
  plan, the enforced set is bound to qualification, and the README states
  the risk.
- [Plugins in provider mode are already known to hang on denied npm
  registry traffic] → This change does not touch that behavior. The
  runtime suite uses fresh state.
- [The Rocky-specific failures, such as the domain UID chown, cannot be
  reproduced here] → Layer-level checks run here, and the operator's Rocky
  setup is the final check.

## Migration Plan

1. Merge `adopt-sandbox-ref-11` into `main` with `--no-ff` after validation.
   The operator pushes it, together with the two pending parity commits.
2. On each host: `--container-setup` with refresh approved.
3. Rollback: before the push, reset `main` to `59e04b2`. After the push,
   revert the merge.
