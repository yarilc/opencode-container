# OpenCode Sandbox

Wrapper for running OpenCode in a rootless Podman container while preserving
the workspace and configuration between sessions.

## Prerequisites

- Linux or WSL2
- Rootless Podman and GNU coreutils `timeout`
- `systemd --user` is optional and only needed for the Podman API socket

Verify the runtime:

```bash
podman info --format '{{.Host.Security.Rootless}} {{.Host.OS}} {{.Host.ServiceIsRemote}}'
```

The command must return `true linux false` for local Podman, or `true linux true`
when using an explicit same-host Unix service endpoint.

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

## Explicit Podman Delegation

Session service access is disabled by default. Only exact
`OPENCODE_CONTAINER_PODMAN=1` enables it; every other value disables access.
Disabled sessions omit the socket and explicitly unset `CONTAINER_HOST`, even
if the image defines it. A Unix launch connection remains independent.

Launch requires a complete Linux rootless engine response and a boolean
`Host.ServiceIsRemote`. Local Podman and explicit same-host absolute Unix
`CONTAINER_HOST` paths beyond slashes are supported. Named connections,
implicit remote contexts, TCP and SSH are rejected. Workspace/state sources
must exist at the same absolute paths on the service host.

Enabled delegation selects the first nonempty value among
`OPENCODE_CONTAINER_PODMAN_SOCKET`, the Unix launch endpoint, and
`${XDG_RUNTIME_DIR:-/run/user/<uid>}/podman/podman.sock`. The selected socket is
physically resolved, checked for read/write access, and queried explicitly.
The verified rootless service's reported host socket source is mounted at
`/run/podman/podman.sock`; the session endpoint points there. This supports a
containerized caller whose accessible socket path differs from the host path.
Verification failure stops startup before image operations; there is no fallback.
Replies must contain all expected fields/records, at most one final LF, no CR
or extra blank/nonblank records; query failures remain failures.

Prepare the rootless service manually if needed:

```bash
systemctl --user start podman.socket
# Optional, to persist service activation across logins:
systemctl --user enable --now podman.socket
# Without systemd, run in a separate terminal:
podman system service --time=0
```

The wrapper never starts or enables a service. It retains host security policy:
no SELinux label disabling or automatic relabeling. On policy denials, configure
socket access for the invoking user and an appropriate SELinux policy on the
host, then retry explicitly. Delegation grants the service user's Podman
authority, including launching containers with host mounts beyond the workspace.

## State and Mounted Paths

The physical workspace and four OpenCode XDG directories are host-writable:
`$XDG_CONFIG_HOME/opencode`, `$XDG_DATA_HOME/opencode`,
`$XDG_CACHE_HOME/opencode`, and `$XDG_STATE_HOME/opencode`. Unset/empty XDG
bases default to `$HOME/.config`, `$HOME/.local/share`, `$HOME/.cache`, and
`$HOME/.local/state`. HOME and nonempty XDG bases must be absolute.

Missing state directories are created privately with a scoped umask. Every
resolved state directory must belong to the caller, permit read/write/traverse,
and deny all group/other permissions. Existing insecure directories cause a
preflight failure before image operations: the wrapper never chmods/chowns them
or imports credentials. Correct permissions manually or select private native
Linux storage when WSL/DrvFS does not enforce Unix modes.

The entrypoint preserves supplied HOME, including nonstandard homes. XDG bases
are normalized to physical state parents. Symlinked application directories
whose target is differently named bind at `<physical-parent>/opencode` so the
application still finds its validated state. Conflicting mount destinations
are rejected. No writable home outside declared mounts is introduced.

Existing `$HOME/.claude`, `$HOME/.agents`, and `/etc/opencode` are optional
read-only integrations. The entire home, `.ssh`, `.aws`, `.docker`, global
`.gitconfig`, and Podman configuration are not implicitly mounted.
Quoted bind arguments support spaces and commas. Colon/CR/LF bind paths are
rejected before image operations rather than misinterpreted.

Environment forwarding uses the explicit wrapper allowlist and nonempty
inherited values, passed by name (`--env VARIABLE`), so credentials are absent
from generated Podman arguments. Values remain visible to container processes
and engine inspection. HOME/USER/XDG and the enabled delegation endpoint are
deliberate nonsecret assignments; `--env-host` is never used.

## Security

The main container runs with:

- a read-only root filesystem;
- the host user's UID/GID;
- the `keep-id` user namespace;
- all capabilities dropped;
- `no-new-privileges`;
- explicit ephemeral tmpfs mounts with `nosuid,nodev` and mode 1777:
  executable `/tmp` (512 MiB) for OpenTUI shared-library loading, noexec
  `/var/tmp` (512 MiB), and noexec `/run` (32 MiB);
- `--read-only-tmpfs=false` to disable automatic writable temporary mounts;
- a process limit.

The rootless Podman socket still gives OpenCode full control over the user's
Podman engine. A process deliberately using the API can access host paths that
the user can read. Leave session delegation disabled when it is unnecessary.

## Updating

The version is defined in `opencode-wrapper` through `OPENCODE_VERSION` and in
the `Dockerfile` through `ARG OPENCODE_VERSION`.

To update:

1. Change both version values.
2. Remove or rebuild the previous image tag.
3. Verify `opencode --version`.

Do not run `opencode upgrade` inside the container: the main filesystem is
immutable.

## Wrapper Modes

The host must provide GNU coreutils `timeout` for bounded session cleanup.
Use `--container-help` for wrapper help without engine or state side effects;
normal `--help` remains an OpenCode argument. `--container-build` refreshes the
versioned per-user image and then starts the selected session.
`--container-shell` bypasses the OpenCode entrypoint and opens `/bin/bash`,
omitting all OpenCode arguments. `--container-git-worktree` explicitly exposes
the physical current directory's entire immediate parent read/write while
retaining the original physical working directory and naming basename.
Other OpenCode arguments keep their order and boundaries.

## Image Inspection and Build Context

Keep the default OpenCode version `1.18.3` and tags containing version,
username, UID and GID. Only image-exists status 1 triggers an automatic build;
other engine/storage errors stop startup. Explicit refresh still performs all
preflights first. Builds use the wrapper's physical recipe directory.
The sole `.dockerignore` defaults to denying all inputs and allows only root
`Dockerfile`, `opencode-entrypoint`, and `.dockerignore`. Update this allowlist
deliberately for any future local COPY input; nested lookalikes, credentials,
state and unrelated files must remain excluded.

## Session Lifecycle

Names use the original physical workspace basename, sanitized, followed by an
index above the highest running/stopped suffix. Parse at most nine digits in
base ten (including `08`); ignore malformed/oversized suffixes. Reserve atomically
with create and retry at most 20 confirmed collisions. Checked enumeration and
collision errors stop startup. Never replace or remove another session to obtain
a name. Private creation records and `io.opencode.session` identify owned full
container IDs; stderr warnings must not become part of an ID.

Stdin remains interactive for pipes/files as well as terminals; allocate a TTY
only with terminal stdin and stdout. Preserve input/EOF for the attached client.
Forward TERM/INT/HUP explicitly once and return 143/130/129. Preserve application
exit statuses, including 125, and the first interruption status despite cleanup
errors or repeated signals. Shutdown has one 20-second budget, including at most
five seconds of application grace, bounded engine calls, interrupted-create
reconciliation and local create/attach client termination/reaping. Repeated
signals do not renew the deadline. Only verified owned IDs authorize removal.

Unresolved creation or removal is reported with an ID/session marker for manual
engine inspection. Client cancellation does not prove engine request cancellation;
engine loss or SIGKILL can leave residual resources. Use `podman ps --all --filter
label=io.opencode.managed=true` and the reported session label to inspect them;
never indiscriminately remove other managed sessions.

## Verification

Run static checks first, then the synthetic suite (Python standard library only):

```bash
bash -n opencode-wrapper
bash -n opencode-entrypoint
python3 -m unittest discover -s tests -p test_wrapper.py -v
```

Synthetic tests use a fake Podman, disposable HOME/XDG, dummy credential strings,
and filesystem socket fixtures; they do not contact the real engine.
Real rootless acceptance requires the current-user image and a running rootless
Unix service. `tests/run-runtime.sh` runs the tests through Podman, mounting the
workspace at its host absolute path and a disposable private Linux state volume.
It defaults to the neighboring project's `localhost/claude-code:latest` as a
tooling image because the OpenCode production image intentionally lacks Python.
Override `OPENCODE_TEST_TOOLS_IMAGE` with an available Linux image providing
Python 3.11+, Bash, GNU coreutils timeout, Git, Podman remote, and a passwd entry
for the invoking numeric UID/GID. Tests build/check the per-user OpenCode tag
for the username inside that tooling container. The runner never imports host
application credentials or changes service/policy setup.

```bash
podman build \
  --tag localhost/opencode-sandbox:1.18.3-$(id -un)-$(id -u)-$(id -g) \
  --build-arg OPENCODE_VERSION=1.18.3 \
  --build-arg USER_NAME=$(id -un) \
  --build-arg USER_ID=$(id -u) \
  --build-arg GROUP_ID=$(id -g) .
./tests/run-runtime.sh
```

The real suite exercises mount flags/capacities/lifetime, identity, state,
context filtering, concurrency, signals, stdin, worktrees, delegation and
remapping, version output, and actual OpenTUI startup/quit through a PTY.
The renderer uses a disposable home with no provider credentials. Its ignored
`.test-state/renderer-last.txt` transcript is available for local inspection.
Synthetic and runtime results are recorded separately in
[the acceptance report](docs/sandbox-acceptance.md). Version output alone does
not initialize OpenTUI and cannot establish renderer compatibility.

Inspect remaining containers with `podman ps --all --filter
label=io.opencode.managed=true`; other users' active sessions must remain intact.
