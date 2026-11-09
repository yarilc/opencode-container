# Proposal: Align the OpenCode runtime image and session baseline

## Why

The other wrappers share one runtime model:
- one generic image, `node:22-bookworm-slim` pinned by digest, with the common Debian toolset, OpenSpec and the agent CLI at an exact version;
- the user is set only at launch (`--userns=keep-id --user UID:GID`);
- a dedicated container home;
- the Claude `sandbox-ref-2` session baseline: resource budgets checked after create, refusal of sensitive workspaces, an optional lifetime, and pinned image inputs.

OpenCode differs:
- it builds a per-user image on the third-party Alpine image `ghcr.io/anomalyco/opencode`, with the user name and IDs baked in;
- the entrypoint derives the user and home;
- `HOME` is the host home path;
- the image has no Python, OpenSpec, nano or bubblewrap;
- the image tag depends on a runtime version variable;
- only the process limit is set, and no workspace guard or lifetime exists.

This change closes todo A03, A04, A05 and A11, the last OpenCode item of Wave 2.

## What Changes

- **BREAKING, image (A03):** `Containerfile` builds one generic image, `localhost/opencode-cli:latest`:
  - the base is `docker.io/library/node:22-bookworm-slim` pinned by the `sandbox-ref-2` digest;
  - it adds the common Debian toolset: `bash`, `bubblewrap`, `bzip2`, `ca-certificates`, `coreutils`, `curl`, `diffutils`, `file`, `findutils`, `gawk`, `git`, `grep`, `jq`, `less`, `nano`, `patch`, `podman`, `procps`, `python3`, `ripgrep`, `sed`, `tar`, `unzip`, `util-linux`, `xz-utils`, `zip`;
  - it installs exactly `opencode-ai@1.18.3` and `@fission-ai/openspec@1.16.0` with npm. npm verifies the registry SHA-512 integrity of each package, and the platform binary packages are pinned to the same exact version.
  - The image runs OpenCode directly. No user, UID, GID or entrypoint script is baked in, and `opencode-entrypoint` is removed.
  - Existing per-user `localhost/opencode-sandbox:*` images are no longer used. The first launch builds the new image, and the README explains how to remove the old ones.
- **Image identity:** the user is set only at launch with `--userns=keep-id --user UID:GID`, and `OPENCODE_CONTAINER_IMAGE` defaults to `localhost/opencode-cli:latest`.
- **BREAKING, version variables:** `OPENCODE_CONTAINER_VERSION` and the deprecated `OPENCODE_VERSION` are removed. If either is set, the wrapper warns that it is ignored and that the version is pinned in `Containerfile`.
- **BREAKING, home (A04):** sessions use `HOME=/opencode-home`, an ephemeral tmpfs. The four OpenCode state directories are mounted beneath it, and the XDG variables point there:
  - `/opencode-home/.config/opencode`;
  - `/opencode-home/.local/share/opencode`;
  - `/opencode-home/.cache/opencode`;
  - `/opencode-home/.local/state/opencode`.

  By default the sources stay the caller's host XDG directories, validated as today, so existing configuration, credentials and sessions keep working. The opted-in `~/.agents` is mounted at `/opencode-home/.agents`. The workspace keeps its host absolute path.
- **Isolated state (A05):** new `OPENCODE_CONTAINER_STATE_DIR` selects a private host directory that becomes the persistent `/opencode-home`, containing the four OpenCode directories, instead of the shared host XDG state.
  - The directory is created and validated like the existing state: absolute, caller-owned, mode without group or other bits, never repaired, and no credentials imported.
  - It must not equal the workspace or lie inside it, and it must not contain the workspace.
- **BREAKING, budgets (A11):** budgets copied from Claude `sandbox-ref-2`:
  - `OPENCODE_CONTAINER_MEMORY_LIMIT` (default `4g`);
  - `OPENCODE_CONTAINER_CPU_LIMIT` (default `2`);
  - `OPENCODE_CONTAINER_PIDS_LIMIT` (default `512`, replacing the fixed `--pids-limit=512`).

  They are validated before any engine query, checked with `podman inspect` after create, and verified as effective cgroup v2 values in runtime tests. A mismatch stops before start.
- **BREAKING, sensitive workspaces (A11):** the wrapper refuses a writable workspace or worktree parent that physically resolves to a sensitive directory:
  - `/` and the system directories;
  - `/tmp`;
  - the physical home;
  - a `/mnt/<letter>` drive root.

  Only the exact `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1` overrides the refusal, with a warning.
- **Lifetime (A11):** new optional `OPENCODE_CONTAINER_RUN_TIMEOUT` maps to the native `--timeout`. A lifetime stop prints a notice and keeps the client's exit status.
- **Kept controls (A10):** `--cap-drop=all`, no-new-privileges, the exec `/tmp`, the tmpfs layout and by-name forwarding stay unchanged.
- **Documentation:** help, README, `AGENTS.md`, `docs/validation.md` and `todo.md` cover:
  - the image and toolset;
  - the pinned versions and their update procedure, including re-reading the OpenCode provider metadata;
  - the home layout and the state option;
  - budgets, the guard and the lifetime;
  - the migration from per-user images.

## Capabilities

### New Capabilities

- `runtime-image`: the generic pinned image, its toolset, the update procedure and the default-deny build context. This is the common capability name from Wave 1, and OpenCode did not have it yet.
- `workspace-mounts`: refusal of sensitive workspace roots and the exact override. This is a common capability name; the existing OpenCode mount requirements stay in `container-isolation` for now.

### Modified Capabilities

- `container-launcher`:
  - the image default, refresh and identity requirements become generic-image requirements, and the version override is removed;
  - the build-context requirement moves to `runtime-image`.
- `container-isolation`:
  - the dedicated home and XDG layout, the isolated-state option and the integration destinations;
  - identity set at launch;
  - budgets verified after create;
  - documentation of the controls.
- `container-session`: the optional lifetime limit.

## Impact

- **Files:**
  - `Containerfile` is rewritten and `.containerignore` allows only `Containerfile` and itself;
  - `opencode-entrypoint` is removed;
  - `opencode-container.sh`: validation block, mounts and home, run arguments, build, post-create inspection, lifetime notice and help.
- **Tests:**
  - `tests/test_wrapper.py`;
  - `tests/test_runtime.py`, `tests/run-runtime.sh` and `tests/image-smoke.sh`, for the new image, home and toolset;
  - new `tests/test_image_pins.py`.
- **Documentation:** `README.md`, `AGENTS.md`, `docs/validation.md`, `todo.md`.
- **Users:**
  - one rebuild, which is automatic on first launch;
  - host OpenCode state keeps working;
  - launching from the home directory or a drive root needs the override;
  - hosts without delegated cgroup v2 controllers cannot start sessions;
  - the version variables are ignored with a warning.
