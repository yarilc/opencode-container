# Repository Guidance

## Sources Of Truth

- `opencode-wrapper` owns runtime policy: mounts, hardening, environment forwarding, socket handling, naming, and cleanup.
- `Dockerfile` owns the pinned OpenCode default (`1.18.3`), installed tools, and per-user image creation.
- `opencode-entrypoint` derives `USER` and `HOME` before executing OpenCode.
- Keep `README.md` synchronized with runtime behavior; trust the scripts when they disagree.

## Required Behavior

- Use rootless Podman only. Docker and Compose support are intentionally out of scope.
- The host Podman CLI is required, but the user API socket is optional. Never start or enable `podman.socket` from the wrapper; warn with the manual `systemctl --user` commands and continue without nested-container support.
- Preserve the host workspace at the same absolute path inside the container so containers launched through `podman-remote` can bind it correctly.
- Keep the root filesystem read-only. Only the workspace and OpenCode XDG directories are host-writable; `.claude`, `.agents`, and `/etc/opencode` are optional read-only mounts.
- Keep `/tmp` as an ephemeral `tmpfs` with `nosuid,nodev`, but never add `noexec`: OpenTUI extracts a shared library there and loads it at startup.
- Do not replace existing containers. Names are `<sanitized-workspace-basename>-N`, where `N` is one greater than the highest existing suffix; reserve names atomically with `podman create`.
- Image tags include OpenCode version, username, UID, and GID. The process inside the image must have the host user's numeric identity and username.
- Forward environment variables through the explicit allowlist only; never introduce `--env-host`.

## Verification

Run static shell checks first:

```bash
bash -n opencode-wrapper
bash -n opencode-entrypoint
```

Build the current-user image with rootless Podman:

```bash
podman build \
  --tag localhost/opencode-sandbox:1.18.3-$(id -un)-$(id -u)-$(id -g) \
  --build-arg OPENCODE_VERSION=1.18.3 \
  --build-arg USER_NAME=$(id -un) \
  --build-arg USER_ID=$(id -u) \
  --build-arg GROUP_ID=$(id -g) .
```

Focused smoke test:

```bash
./opencode-wrapper --version
./opencode-wrapper
podman ps --all --filter label=io.opencode.managed=true
```

The first command must print `1.18.3`. Start and quit the second command interactively; `--version` does not initialize OpenTUI and cannot catch renderer failures. The final command must show no leftover wrapper container. ShellCheck is not currently installed on the host.

## Known Portability Gaps

- Bind mounts use comma-delimited `--mount`; workspace or XDG paths containing commas currently fail.
- Image creation currently fails when the host GID already exists in the Alpine base image (for example GID `100`).
- `opencode-entrypoint` assumes `/home/<username>` and does not preserve a nonstandard host home.
- `--security-opt=label=disable` is added when exposing the Podman socket; this weakens SELinux confinement on SELinux-enabled hosts, though the current WSL2 environment has no SELinux.
