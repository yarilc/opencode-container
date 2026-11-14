# Design

## Context

OpenCode `main` (`c58006e`, one commit ahead of `origin/main`) pins
`sandbox-ref-12`. The dry run of `tools/propagate.py ../opencode-container
sandbox-ref-12 sandbox-ref-16` (commit `1fa091e`) reports the same file set as
for `sandbox-ref-15` (checked against Pi, which has the same base tag):

- six modified files and two added files, nothing removed or "not adopted";
- four documents (`README.md`, `AGENTS.md`, `docs/setup.md`,
  `docs/network-contract.md` with seven references);
- the runner modes `--shared`, `--setup`, `--setup-runtime`,
  `--qualification`, `--guard`, `--network` and `--wrapper`.

A first apply of this change adopted `sandbox-ref-15` on branch
`adopt-sandbox-ref-15`. Its agent-identifier scans failed on a shared
comment that named OpenCode, fixed in `sandbox-ref-16`. That branch holds
only the tool's output and the change directory. It is discarded before the
new apply.

The reference launcher change is claude-container commit `e45957f`. Codex
ported it in `adopt-sandbox-ref-14` (merge `9175a6e`). OpenCode differs from
both:

- **State:** an isolated `OPENCODE_CONTAINER_STATE_DIR`, mounted as
  `/opencode-home`, or four shared host directories below `$HOME`, mounted
  below a tmpfs `/opencode-home`:
  - `.config/opencode`, or `OPENCODE_CONTAINER_CONFIG_DIR`;
  - `.local/share/opencode`;
  - `.cache/opencode`;
  - `.local/state/opencode`.

  The launcher collects every writable state path in `writable_state`
  (`opencode-container.sh` around line 620) and passes them to the session
  helper as `--writable`. The default library
  `~/.local/share/sandbox-toolchains` is a sibling of
  `~/.local/share/opencode`, so it never overlaps.
- **Order:** state is created after engine verification, then `run_args` is
  built (around line 677). The network inputs follow, and the runtime image
  identity is resolved last (`session_image`, around line 832). It is
  `$IMAGE` in unrestricted mode and the image ID in restricted modes.
- **Helpers:** `capture_response <var> <command…>` preserves all output bytes.
  The fake engine in `tests/test_wrapper.py` answers `image inspect` with
  one fixed ID.
- **Environment:** the launcher sets `XDG_*_HOME`, `HOME` and `USER` itself
  and forwards a fixed allowlist of host variables. Toolchain variables are
  never host-forwarded; they come only from `launch-env`, which since
  `sandbox-ref-15` refuses `XDG_` and the other protected names.
- **Temporary storage:** `/tmp` is executable (`exec`); `/var/tmp` and `/run`
  are `noexec`; `/opencode-home` is an executable tmpfs in shared-state mode.
- **Agent instructions:** OpenCode reads `AGENTS.md` in the project and
  `~/.config/opencode/AGENTS.md`, which is `/opencode-home/.config/opencode`
  in the session.
- **Tests:**
  - `tests/test_wrapper.py` creates its base with `TemporaryDirectory`, with
    no directory argument, and sets `HOME=<base>/home`.
  - `tests/run-runtime.sh` runs the suites with `HOME=/tmp` on a
    world-writable tmpfs `/tmp`.
  - `tests/test_runtime.py` hardcodes `localhost/opencode-cli:latest`.
  - `tests/test_network_runtime.py` builds an installation without `setup/`
    or `Containerfile`.
- **Base:** the `Containerfile` has one digest-pinned `FROM`, the same
  `node:22-bookworm-slim@sha256:4b15…` as the reference.

## Goals / Non-Goals

**Goals:**
- OpenCode adopts `sandbox-ref-16` byte for byte, and its parity table matches
  claude-container's.
- OpenCode sessions mount the shared library and get the default environment
  as reference sessions do, without any toolchain changing OpenCode's state
  location.
- Every runner mode the tool lists passes, `--wrapper` included.

**Non-Goals:**
- Any shared-file change, guard, proxy or policy change.
- Copying the example recipes or their opt-in network test.
- Changing `/var/tmp` or `/run` execution policy.

## Decisions

1. **Documented procedure on one branch.**
   - Dry run, stash the change directory, `--apply` on
     `adopt-sandbox-ref-16`, restore the stash. The paused
     `adopt-sandbox-ref-15` branch is deleted first, because it has no work
     worth keeping.
   - Commit the wrapper port on the same branch and merge once with
     `--no-ff`. `main` never has a qualified module that the launcher does
     not use.
2. **Port the reference launcher block, renaming only.**
   - The dispatch, `toolchains_enabled` (existing `boolean` helper), the
     `launch-env` call and parser come from `e45957f`. So do the image `PATH`
     inspection and the mount.
   - Placement:
     - the dispatch next to `--container-setup`;
     - the library check after the state block and before `run_args`, so an
       unsafe library stops before any image or container operation;
     - the mount appended to `run_args`;
     - the environment appended after `session_image` is resolved.
   - The `--avoid` list is `workspace_mount` plus every entry of
     `writable_state`.
   - Alternative: an OpenCode-specific variant. Rejected: identical behavior
     across wrappers is the point of the shared library.
3. **Tests mirror the reference cases** (as in Codex):
   - `tests/test_wrapper.py`:
     - dispatch;
     - private creation;
     - unsafe library: mode, overlap with the workspace, the installation, a
       shared state directory and an isolated state directory;
     - disable;
     - appended environment and the stale-base warning;
     - restricted `--mount-target`;
     - the unsafe home-workspace case.

     The fake engine answers `.Config.Env` inspections. The restricted
     fixture installs `setup/common.py`, `setup/toolchains.py` and
     `Containerfile`.
   - `tests/test_runtime.py`:
     - archive and image sources;
     - failing check;
     - read-only mount;
     - `node` and `python3` not shadowed;
     - disabled mount.
   - `tests/test_network_runtime.py`: the live add during an offline
     session. Its synthetic installation gains `setup/` and `Containerfile`.
   - Existing cases that the new mount affects are adapted where they fail,
     and each adaptation is recorded.
4. **Private temporary storage for the runner**, as in the reference and in
   Codex:
   - `tests/run-runtime.sh` mounts a private executable tmpfs at
     `/sandbox-test-tmp` (`0700`, `U=true`, 1 GiB) and sets
     `SANDBOX_TEST_TMPDIR`;
   - `tests/test_wrapper.py` creates its base there when the variable is set.
5. **Runtime image tag.** `tests/test_runtime.py` uses
   `localhost/opencode-cli:latest`. The runtime runs tag the current setup
   image as `latest` temporarily, and remove only that tag afterwards with
   `podman untag <image> localhost/opencode-cli:latest`. A bare `untag`
   would drop every tag.
6. **Documentation.** The README section states the reference rules adapted
   to OpenCode:
   - the `AGENTS.md` line for the project or
     `~/.config/opencode/AGENTS.md`;
   - writable locations;
   - the XDG note;
   - the link to claude-container's example recipes.

## Risks / Trade-offs

- [An OpenCode fixture assumes a fixed volume list or file set] → The suites
  catch it, and the fixture is updated on the same branch.
- [Unsafe-workspace launches from the home directory now stop] → As in the
  reference, because the home contains the default library. The README
  documents `OPENCODE_CONTAINER_TOOLCHAINS_DIR` and
  `OPENCODE_CONTAINER_TOOLCHAINS=0`.
- [The temporary `latest` tag is left behind after an interrupted run] →
  Remove it explicitly with the named `untag`. It points to the current
  setup image anyway.
- [Qualification reports become stale] → The operator reruns
  `--container-setup` on the three hosts.

## Migration Plan

1. Merge `adopt-sandbox-ref-16` with `--no-ff`. The operator pushes it.
2. Rerun `--container-setup` on this host, the Rocky Linux 9 lab host and the
   newer WSL host. With the Temurin 21 toolchain in the library, check
   `java -version` in an OpenCode session and run
   `opencode-container --container-toolchain verify java21`.
3. Record the results, then archive with the spec sync.
4. Rollback before the push: reset `main` to `c58006e`. The library on disk is
   ignored by the older launcher.
