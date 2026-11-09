# Design

## Context

State before this change, after `align-wrapper-baseline`:
- **Image:** `opencode-container.sh` builds `localhost/opencode-sandbox:<version>-<user>-<uid>-<gid>` from `Containerfile`.
  - The base is `FROM ghcr.io/anomalyco/opencode:${OPENCODE_VERSION}` (Alpine), with `apk add` of Bash, curl, Git, jq, `podman-remote` and ripgrep.
  - `adduser` bakes in the caller's identity, and `USER` is set in the image.
  - The entrypoint `opencode-entrypoint` exports `USER` and a fallback `HOME`.
- **Home:** the wrapper sets `HOME` to the host home path. It mounts each validated host XDG `opencode` directory at its physical host path and sets the XDG variables to the physical parents.
- **Hardening:** `--pids-limit=512` is fixed.
- **Missing pieces:** no memory or CPU budget, no workspace guard, no lifetime.

Reference implementations:
- `codex-container` `Containerfile`: pinned base, apt toolset, `npm install --global` at exact versions, tmpfs `HOME`;
- the Codex and Antigravity budget, guard and lifetime Bash blocks, ported from Claude `sandbox-ref-2`.

Measured on 2026-11-09 on the pinned base `node:22-bookworm-slim@sha256:4b150b48…79da`:
- `npm view opencode-ai@1.18.3` reports a registry `dist.integrity` SHA-512 and exact-version `optionalDependencies` for the platform packages, such as `opencode-linux-x64` 1.18.3. Its `postinstall` copies the matching platform binary to `bin/opencode.exe`.
- `npm install --global opencode-ai@1.18.3` produced a working `opencode` that reports `1.18.3` and is linked only against glibc.
- The postinstall step selects the AVX2 or baseline x64 build from the build host's `/proc/cpuinfo`.

## Goals / Non-Goals

**Goals:**
- Same image model, toolset, pinning and session baseline as Codex and Antigravity, with the `OPENCODE_CONTAINER_` prefix.
- Existing users keep their OpenCode configuration, credentials and sessions without migration.
- All new validation and the workspace guard run before the first engine query or state creation.

**Non-Goals:**
- Network, setup questions, qualification and the Python budget module (Wave 3).
- Moving persistent-state requirements from `container-isolation` to `persistent-state`, or mount requirements to `workspace-mounts`, beyond the new guard.
- Running the runtime tests inside the new image instead of the external runner image.

## Decisions

### D1: Containerfile
The recipe is Codex's recipe:
- the same pinned base and apt package list, plus `nano`;
- `ARG OPENCODE_VERSION=1.18.3` and `ARG OPENSPEC_VERSION=1.16.0`;
- `npm install --global --omit=dev "@fission-ai/openspec@${OPENSPEC_VERSION}" "opencode-ai@${OPENCODE_VERSION}"`;
- cleanup of the apt lists and the npm cache;
- `mkdir -m 1777 /opencode-home`;
- `ENV HOME=/opencode-home`, `OPENCODE_DISABLE_AUTOUPDATE=1` and `DEBIAN_FRONTEND=noninteractive`;
- `WORKDIR /workspace` and `ENTRYPOINT ["opencode"]`.

A `RUN` step checks that `opencode --version` and `openspec --version` equal the arguments.

`opencode-entrypoint` is deleted. Its two jobs are covered elsewhere:
- `HOME` is set by the wrapper and the image;
- `USER` is set by the wrapper from `id -un`, as today, and keep-id supplies the passwd entry.

`.containerignore` allows only `/Containerfile` and `/.containerignore`.

Alternatives considered:
- **Keep the third-party OpenCode image as a build stage and copy its binary:** rejected, because it keeps an unpinned third-party image in the supply chain.
- **Download the GitHub release with a recorded SHA-256:** viable, but npm is the channel Codex and Claude already use, and it verifies the registry integrity of every package.

### D2: Image identity
The default image becomes `localhost/opencode-cli:latest`, and `OPENCODE_CONTAINER_IMAGE` overrides it. The build passes no build arguments; the recipe defaults are the pins. Version resolution is removed. If `OPENCODE_CONTAINER_VERSION` or `OPENCODE_VERSION` is set, the early validation block prints:

`opencode-container: <NAME> is ignored; the OpenCode version is pinned in Containerfile`

Old per-user images are never touched. The README gives `podman image ls 'localhost/opencode-sandbox'` and the removal command.

### D3: Home and state layout
`run_args` gains:
- `--env HOME=/opencode-home`;
- the four XDG variables `XDG_CONFIG_HOME=/opencode-home/.config`, `XDG_DATA_HOME=/opencode-home/.local/share`, `XDG_CACHE_HOME=/opencode-home/.cache` and `XDG_STATE_HOME=/opencode-home/.local/state`.

How `/opencode-home` is provided depends on the state mode:
- **Shared mode (default):** `--tmpfs /opencode-home:rw,exec,nosuid,nodev,mode=1777,size=512m`. `private_xdg` keeps resolving and validating the host directories unchanged. Each one is then bound at its fixed destination below `/opencode-home` instead of its host path.
- **Isolated mode (`OPENCODE_CONTAINER_STATE_DIR`):** the wrapper validates the value. It must be absolute, contain no colon or newline, and not overlap the workspace mount on the physical path.
  1. It creates the directory privately if missing.
  2. It resolves it physically, applying the same ownership, access and mode checks as `private_xdg`.
  3. It creates the four `opencode` subdirectories privately.
  4. It binds the directory at `/opencode-home` read/write instead of the tmpfs.

  The host XDG directories are not touched in this mode.

The integration destination for `~/.agents` becomes `/opencode-home/.agents`. `add_bind` already rejects destination conflicts. The tmpfs-shadow check gains `/opencode-home` only for the tmpfs mode, where binds below it are intended, so the check allows descendants and refuses the exact path.

### D4: Budgets, guard and lifetime
The Codex block is copied with the `OPENCODE_CONTAINER_` prefix and the `opencode-container:` messages. It covers:
- budget validation and normalization;
- `RUN_TIMEOUT` validation;
- the workspace guard on the physical workspace mount, after worktree parent selection, with the physical home taken from `cd "$HOME" && pwd -P`;
- the exact override with its warning.

It runs immediately after the existing exposure-control validation, before `command -v podman`, which is earlier than the current `workspace_mount` computation. The workspace computation moves up into that block.

`run_args` changes:
- the fixed `--pids-limit=512` becomes `--memory=<bytes> --cpus=<text> --pids-limit=<n>`;
- `--timeout <n>` is added when the lifetime is greater than zero.

After create and before start, the wrapper inspects the budgets with a bounded `podman inspect` on the owned full ID. A mismatch dies with the cgroup v2 delegation diagnostic, and the existing EXIT cleanup removes the owned container. `started_at=$SECONDS` and the lifetime notice follow Codex.

### D5: Tests
**`tests/test_wrapper.py`:**
- the fake engine answers `inspect` for budgets, with `FAKE_AGENT_BUDGETS` and `FAKE_INSPECT_STATUS`;
- cases ported from Codex: budgets, inspection, guard, lifetime and help;
- new cases:
  - the default image and no build arguments;
  - the ignored version warning;
  - the home and XDG variables and destinations in shared mode, including symlinked and nonstandard host XDG bases;
  - isolated mode: creation, validation failures, workspace overlap and no host XDG mounts;
  - `.agents` mounted at `/opencode-home/.agents`.
- Existing fixtures that launch from a refused directory set the override.

**`tests/test_image_pins.py`:** new, adapted from Codex. It requires:
- the base by digest;
- exact `opencode-ai` and `@fission-ai/openspec` versions;
- no `ghcr.io/anomalyco/opencode` image;
- no `@latest`;
- every toolset package.

**`tests/test_runtime.py` and `tests/run-runtime.sh`:**
- the image constant becomes `localhost/opencode-cli:latest`;
- `test_build_context` uses a two-file context;
- the entrypoint and HOME test becomes a home-layout test covering shared and isolated modes;
- effective capabilities, `NoNewPrivs` and cgroup v2 budgets, with default and overridden values, with and without delegation;
- process-limit enforcement;
- lifetime expiry and early exit;
- a refused home workspace;
- the tool inventory through `tests/image-smoke.sh`, which is updated for the toolset, generic identity and new home;
- OpenTUI on glibc.

Runtime tests keep the external Python runner image. Unit suites run in the runner container, as in the earlier changes.

## Risks / Trade-offs

- **The AVX2 or baseline binary is chosen at build time.** An image built on an AVX2 host and copied to a host without AVX2 would fail. The image is built locally per host and never distributed, and the README states it.
- **npm postinstall scripts run during the build.** They come from the pinned, integrity-checked packages, at the same trust level as Codex's npm install.
- **Users launch from their home or a drive root.** The launch is refused with guidance, and the exact override exists.
- **Hosts lack delegated cgroup controllers.** The launch stops with a diagnostic, and the README states the requirement.
- **4 GiB is too little for large language-server workloads.** The budgets can be overridden per launch.
- **Host state shared through tmpfs-backed binds.** Files that OpenCode writes outside the four directories, such as `~/.npm` from plugins, are now ephemeral, where before they landed in the host home only if mounted, which they were not. Isolated mode makes the whole home persistent.

## Migration Plan

1. Implement on branch `align-runtime-image`. Unit suites run in the runner container, and the real-engine suite with `bash tests/run-runtime.sh`.
2. The first launch builds `localhost/opencode-cli:latest` automatically. Users keep their host XDG state. They remove old `localhost/opencode-sandbox:*` images when ready, and drop `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION`.
3. Rollback: revert the merge. The old per-user images still exist unless removed, and the state format is unchanged.
