# OpenCode Sandbox

Wrapper for running OpenCode in a rootless Podman container while preserving
the workspace and configuration between sessions.

## Prerequisites

- Linux or WSL2
- Rootless Podman
- `systemd --user` is optional and only needed for the Podman API socket

Verify the runtime:

```bash
podman info --format '{{.Host.Security.Rootless}}'
```

The command must return `true`.

## Installation

Make the wrapper executable:

```bash
chmod 0755 /mnt/d/Workspace/opencode-container/opencode-wrapper
```

Add the alias to your shell configuration:

```bash
alias opencode='/mnt/d/Workspace/opencode-container/opencode-wrapper'
```

Reload the shell configuration or open a new session.

## Usage

The wrapper preserves the normal OpenCode interface:

```bash
cd /home/yari/Workspace/project
opencode
opencode --version
opencode run "Describe this project"
```

The first invocation builds the image. The default version is `1.18.3`; it can
be overridden for one session:

```bash
OPENCODE_VERSION=1.18.3 opencode --version
```

## Container Names

The name is derived from the workspace basename:

```text
/home/yari/Workspace/project -> project-0
```

Later instances use the highest existing index plus one. Intermediate indices
are not reused while a higher index exists.

Containers are ephemeral and are removed when the session ends.

## Optional Podman Socket

OpenCode starts normally without the Podman API socket. In that case it cannot
launch nested containers, and the wrapper prints the commands needed to enable
the socket.

The image includes `podman-remote`, exposed as the `podman` command. It works
only when the API socket is mounted.

Enable the socket for the current session:

```bash
systemctl --user start podman.socket
```

Enable it now and automatically at login:

```bash
systemctl --user enable --now podman.socket
```

The wrapper never runs these commands automatically.

## Mounted Paths

Writable mounts:

- current workspace;
- `~/.config/opencode`;
- `~/.local/share/opencode`;
- `~/.cache/opencode`;
- `~/.local/state/opencode`.

Optional read-only mounts:

- `~/.claude`;
- `~/.agents`;
- `/etc/opencode`.

The full home directory, `.ssh`, `.aws`, `.docker`, the global `.gitconfig`,
and the user's Podman configuration are not mounted.

## Security

The main container runs with:

- a read-only root filesystem;
- the host user's UID/GID;
- the `keep-id` user namespace;
- all capabilities dropped;
- `no-new-privileges`;
- an ephemeral `/tmp` with `nosuid` and `nodev`; it must remain executable
  because OpenTUI loads a shared library from there at startup;
- a process limit.

The rootless Podman socket still gives OpenCode full control over the user's
Podman engine. A process deliberately using the API can access host paths that
the user can read. For maximum isolation, do not enable the socket.

## Updating

The version is defined in `opencode-wrapper` through `OPENCODE_VERSION` and in
the `Dockerfile` through `ARG OPENCODE_VERSION`.

To update:

1. Change both version values.
2. Remove or rebuild the previous image tag.
3. Verify `opencode --version`.

Do not run `opencode upgrade` inside the container: the main filesystem is
immutable.
