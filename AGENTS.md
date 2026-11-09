# Repository Guidelines

## Project Structure & Module Organization

- `opencode-container.sh` owns runtime policy: mounts, hardening, environment forwarding, YOLO, socket handling, naming, labels, and cleanup.
- `opencode-wrapper` is a deprecated shim that warns once and execs `opencode-container.sh` with unchanged arguments; keep it until the final cleanup.
- `Containerfile` owns the generic image: the digest-pinned base, the common toolset, and the pinned OpenCode (`1.18.3`) and OpenSpec (`1.16.0`) npm packages; `.containerignore` is its default-deny build-context allowlist. The image contains no caller identity and its entrypoint is `opencode`.
- `tests/test_image_pins.py` rejects floating image inputs and a missing toolset package.
- `README.md` documents setup, usage and security; keep it synchronized with runtime behavior and trust the scripts when they disagree.
- `openspec/specs/` contains current behavior contracts; `openspec/changes/` holds active proposals and dated archives.
- `tests/` contains synthetic wrapper tests and opted-in real Podman checks; `docs/validation.md` records verification results and limitations.

## Build, Test, and Development Commands

Run static shell checks first:

```bash
bash -n opencode-container.sh
bash -n opencode-wrapper
```

Build the image with rootless Podman:

```bash
podman build --tag localhost/opencode-cli:latest --file Containerfile .
```

Focused smoke test:

```bash
./opencode-container.sh --version
./opencode-container.sh
podman ps --all --filter label=io.opencode-container.managed=true
```

The first command must print `1.18.3`. Start and quit the second command interactively; `--version` does not initialize OpenTUI and cannot catch renderer failures. The final command must show no test-owned wrapper container; preserve any preexisting sessions. ShellCheck may be run through Podman when unavailable on the host.

## Coding Style & Naming Conventions

Use Bash with `set -euo pipefail`, quoted variables, and command arrays for user-controlled arguments. Follow the script's four-space indentation. Prefer small functions and actionable errors prefixed `opencode-container:`. Wrapper settings use the `OPENCODE_CONTAINER_` prefix; never add generic names in OpenCode's own `OPENCODE_*` namespace. Labels use `io.opencode-container.*`. Write documentation, comments, help, and messages in English.

## Testing Guidelines

Run the standard-library synthetic suites with `python3 -m unittest discover -s tests -p 'test_*.py' -v`. `tests/run-runtime.sh` opts into real rootless tests, using private native Linux state in a disposable volume and the same absolute workspace mount. Its tooling image defaults to `localhost/claude-code:latest`; `OPENCODE_TEST_TOOLS_IMAGE` can select another image with Python 3.11+, Bash, GNU timeout, Git, Podman remote, and a passwd entry for the invoking identity. The production OpenCode image does not need Python. Tests never import actual credentials.

Keep synthetic evidence separate from real acceptance in `docs/validation.md`. Check OpenTUI startup and quit interactively in a PTY in addition to version output, and inspect test-owned resources afterward. Temporary transcripts and Python caches are ignored by `.gitignore`; production build inputs remain governed solely by `.containerignore`.

## OpenSpec Workflow

For OpenSpec changes, keep proposal, delta specs, design, and tasks coherent. Proposal work changes planning artifacts only; implement through the apply workflow. Mark tasks complete after verification, synchronize delta specs into main specs, and archive completed changes under dated directories.

## Commit & Pull Request Guidelines

Use concise imperative subjects. Keep commits focused. PRs should explain behavior changes, list verification, identify security/mount changes, and update `README.md` when usage changes.

## Security & Configuration

### Required behavior

- Use rootless Podman only. Docker and Compose support are intentionally out of scope.
- Require host Podman and GNU coreutils timeout. Validate a complete Linux rootless launch response with boolean ServiceIsRemote before image operations. Accept local or explicit same-host absolute Unix endpoints; reject named/implicit remote/TCP/SSH contexts and slash-only paths.
- Delegate only with exact `OPENCODE_CONTAINER_PODMAN=1`; all other values omit the mount and explicitly unset session CONTAINER_HOST. Enabled verification failures stop before image operations. Select nonempty OPENCODE_CONTAINER_PODMAN_SOCKET, Unix launch endpoint, then runtime default; query the canonical accessible socket and bind its reported absolute host source. Never start/enable services or silently fall back.
- Preserve host security policy: no SELinux label disabling or automatic relabeling. Document manual service/permissions/SELinux setup. Socket authority can create host mounts beyond the workspace. Reject failed, incomplete, extra-record, or CR-containing engine/service responses, preserving trailing records and query status.
- Preserve the host workspace at the same absolute path inside the container so containers launched through `podman-remote` can bind it correctly.
- Keep the root filesystem read-only. Only the workspace and OpenCode XDG directories are host-writable. `.agents` and `/etc/opencode` are read-only mounts only on exact `OPENCODE_CONTAINER_AGENTS_DIR=1` / `OPENCODE_CONTAINER_SYSTEM_CONFIG=1`; never mount `~/.claude` or another agent's state.
- Keep `/tmp` as an ephemeral `tmpfs` with `nosuid,nodev`, but never add `noexec`: OpenTUI extracts a shared library there and loads it at startup.
- Keep `--cap-drop=all`, `no-new-privileges`, the pinned image inputs and by-name forwarding; never add `--privileged` or add a capability back.
- Validate `OPENCODE_CONTAINER_MEMORY_LIMIT` (4g), `OPENCODE_CONTAINER_CPU_LIMIT` (2), `OPENCODE_CONTAINER_PIDS_LIMIT` (512) and `OPENCODE_CONTAINER_RUN_TIMEOUT` before engine queries with the Claude `sandbox-ref-2` rules and messages; inspect the created container and start it only when the configured budgets match; print the lifetime notice while keeping the client status.
- Refuse a workspace or worktree parent that physically is `/`, a system directory, `/tmp`, the physical home or a `/mnt/<letter>` drive root, before engine queries or state creation, unless exactly `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1`, which warns.
- Do not replace existing containers. Names are `<sanitized-workspace-basename>-N`, where `N` is one greater than the highest existing suffix; reserve names atomically with `podman create`.
- One generic image (`OPENCODE_CONTAINER_IMAGE`, default `localhost/opencode-cli:latest`); the numeric identity is set only at launch with `--userns=keep-id --user UID:GID`. `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION` are ignored with a warning.
- Sessions use `HOME=/opencode-home` with XDG bases below it. By default it is a 512 MiB exec tmpfs with the four validated host OpenCode XDG directories bound at fixed paths below it; `OPENCODE_CONTAINER_STATE_DIR` instead binds a private, validated, non-overlapping host directory as the persistent home.
- Forward environment variables by name only from the base allowlist, the provider profile selected with `OPENCODE_CONTAINER_PROVIDER`, and names in `OPENCODE_CONTAINER_ENV_VARS`; never forward GitHub tokens or other providers' keys by default, and never introduce `--env-host`. Profile variable sets follow the pinned OpenCode version's provider metadata; re-read them when the version changes.
- `OPENCODE_CONTAINER_YOLO` accepts `1/true/yes` and `''/0/false/no` case-insensitively and rejects other values before engine queries. Enabled, it adds the literal `OPENCODE_PERMISSION={"*":"allow"}` after forwarding and refuses a host `OPENCODE_PERMISSION`; disabled, it adds nothing. YOLO and delegation are independent and YOLO changes no mount or forwarding.

### State and environment contracts

Privately create only missing OpenCode XDG config/data/cache/state directories with a scoped umask; physically resolve and verify each caller-owned directory's read/write/traverse access and absence of group/other permissions before image operations. Never repair state with chmod/chown or copy credentials. Resolve nonstandard host homes and symlinked host XDG bases physically, then bind each validated directory at its fixed path below `/opencode-home`; isolated state follows the same validation and must not overlap the workspace. A tmpfs home binds below `/opencode-home` but never shadows it. Reject destination conflicts. Keep opted-in integrations read-only and preserve physical absolute bind sources. Use explicit tmpfs mounts: exec `/tmp` 512 MiB, exec `/opencode-home` 512 MiB in shared mode, noexec `/var/tmp` 512 MiB and noexec `/run` 32 MiB, all nosuid/nodev mode 1777; disable automatic read-only tmpfs provisioning. Verify actual flags and ephemeral lifetime at runtime.

Forward nonempty inherited variables by name from the base allowlist, the selected provider profile and the operator-listed names, keeping secret values out of generated engine-client arguments. Validate the YOLO, version, image and provider values and the listed names, and check opted-in integration directories, before engine queries. This does not hide values from engine inspection or container processes. Identity/path assignments remain explicit; image defaults or forwarded values must not override disabled delegation.

### Wrapper modes

The host must provide GNU coreutils `timeout` for bounded session cleanup. Use `--container-help` for wrapper help without engine or state side effects; normal `--help` remains an OpenCode argument. `--container-build` refreshes the versioned per-user image and then starts the selected session. `--container-shell` bypasses the OpenCode entrypoint and opens `/bin/bash`, omitting all OpenCode arguments. `--container-git-worktree` explicitly exposes the physical current directory's entire immediate parent read/write while retaining the original physical working directory and naming basename. Other OpenCode arguments keep their order and boundaries.

### Image inspection and build context

Keep the pinned versions in `Containerfile` (`OPENCODE_VERSION=1.18.3`, `OPENSPEC_VERSION=1.16.0`) and the base digest; change them only through the README "Updating pinned image inputs" procedure, re-reading the OpenCode provider metadata and permission merge behavior. `OPENCODE_CONTAINER_IMAGE` overrides the image name; builds pass no build arguments. Only image-exists status 1 triggers an automatic build; other engine/storage errors stop startup. Explicit refresh still performs all preflights first. Builds use the wrapper's physical recipe directory. The sole `.containerignore` defaults to denying all inputs and allows only root `Containerfile` and `.containerignore`. Update this allowlist deliberately for any future local COPY input; nested lookalikes, credentials, state and unrelated files must remain excluded.

### Session lifecycle

Names use the original physical workspace basename, sanitized, followed by an index above the highest running/stopped suffix. Parse at most nine digits in base ten (including `08`); ignore malformed/oversized suffixes. Reserve atomically with create and retry at most 20 confirmed collisions. Checked enumeration and collision errors stop startup. Never replace or remove another session to obtain a name. Private creation records and `io.opencode-container.session` identify owned full container IDs; stderr warnings must not become part of an ID. Never adopt or remove containers labeled with the earlier `io.opencode.*` prefix.

Stdin remains interactive for pipes/files as well as terminals; allocate a TTY only with terminal stdin and stdout. Preserve input/EOF for the attached client. Forward TERM/INT/HUP explicitly once and return 143/130/129. Preserve application exit statuses, including 125, and the first interruption status despite cleanup errors or repeated signals. Shutdown has one 20-second budget, including at most five seconds of application grace, bounded engine calls, interrupted-create reconciliation and local create/attach client termination/reaping. Repeated signals do not renew the deadline. Only verified owned IDs authorize removal.

Unresolved creation or removal is reported with an ID/session marker for manual engine inspection. Client cancellation does not prove engine request cancellation; engine loss or SIGKILL can leave residual resources. Use `podman ps --all --filter label=io.opencode-container.managed=true` and the reported session label to inspect them; never indiscriminately remove other managed sessions.

### Known portability gaps

- Quoted volume arguments support spaces/commas; colon/CR/LF bind paths are explicitly rejected.
- The npm install selects the x64 AVX2 or baseline OpenCode binary from the build host's CPU; build the image on the host that runs it.
- With keep-id, a caller UID that already exists in the base image (for example 1000, `node`) shows that image user name; `USER` is still set from the host.
- HOME/XDG must be absolute. State storage must enforce private Unix ownership/modes; choose native Linux storage if WSL/DrvFS cannot enforce them.
- Host SELinux policy may require explicit socket-access setup; the wrapper never weakens policy.
