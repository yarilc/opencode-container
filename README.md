# OpenCode CLI in Podman

`opencode-container.sh` runs OpenCode in a rootless Podman container while
preserving the workspace and OpenCode configuration between sessions. The
image filesystem is read-only, with a writable workspace, private OpenCode XDG
state and explicit temporary storage. Every launch selects a network mode:
`offline`, `provider` (only the exact hosts of one provider profile) or
`unrestricted`; see [Network modes](#network-modes). In unrestricted mode,
`OPENCODE_CONTAINER_PODMAN=1` exposes the host Podman socket for container work
inside the session.

## Enable rootless Podman on the host

Requirements:

- Linux or WSL2
- Rootless Podman and GNU coreutils `timeout`
- `systemd --user` is optional and only needed for the Podman API socket

Verify the runtime:

```bash
podman info --format '{{.Host.Security.Rootless}} {{.Host.OS}} {{.Host.ServiceIsRemote}}'
```

The command must return `true linux false` for local Podman, or `true linux true`
when using an explicit same-host Unix service endpoint.

Launch requires a complete Linux rootless engine response and a boolean
`Host.ServiceIsRemote`. Local Podman and explicit same-host absolute Unix
`CONTAINER_HOST` paths beyond slashes are supported. Named connections,
implicit remote contexts, TCP and SSH are rejected. Workspace/state sources
must exist at the same absolute paths on the service host.

## Optional host Podman API access

Session service access is disabled by default. Only exact
`OPENCODE_CONTAINER_PODMAN=1` enables it; every other value disables access.
Disabled sessions omit the socket and explicitly unset `CONTAINER_HOST`, even
if the image defines it. A Unix launch connection remains independent.

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

## First run: guided setup

New users run the guided setup once, from a reviewed checkout, as the non-root
Linux/WSL user who will use the sandbox:

```bash
bash ./opencode-container.sh --container-setup
```

Setup asks for the network mode (default `provider`), the API-key method
(`anthropic`, `openai`, `openrouter` or `opencode-zen`), shared or isolated
state, delegation, YOLO, CA trust, budgets and lifetime. It discloses the
residual exfiltration risk of provider mode, prepares the images and the guard
under explicit maintenance consent, installs a protected release, qualifies it
and runs a credential-free smoke check. It never stores a key; provider mode
ends with `Authentication pending` and the variable to supply. Afterward, launch
from a workspace with the managed command, by default
`~/.local/bin/opencode-container`. See [docs/setup.md](docs/setup.md).

An ordinary launch with an unset or empty `OPENCODE_CONTAINER_NETWORK` stops
with `setup required:` guidance before runtime checks or state creation. Direct
operator launches with an explicit mode remain available (see
[Network modes](#network-modes)).

## Usage

Make the wrapper executable and add an alias to your shell configuration:

```bash
chmod 0755 /mnt/d/Workspace/opencode-container/opencode-container.sh
alias opencode='/mnt/d/Workspace/opencode-container/opencode-container.sh'
```

Reload the shell configuration or open a new session. `opencode-wrapper` remains
as a deprecated alias: it prints one warning and runs `opencode-container.sh`
with the same arguments, so existing aliases keep working. Point them to
`opencode-container.sh` to remove the warning.

The wrapper preserves the normal OpenCode interface:

```bash
cd /home/yari/Workspace/project
opencode
opencode --version
opencode run "Describe this project"
```

Every launch needs `OPENCODE_CONTAINER_NETWORK` (see [Network modes](#network-modes)).
Building the image, including the first build, needs exact
`OPENCODE_CONTAINER_MAINTENANCE=1`. Wrapper options:

| Option | Effect |
| --- | --- |
| `--container-qualify` | qualify a prepared restricted installation with fixed local controls; must be used alone |
| `--container-build` | rebuild the image from the pinned inputs (requires `OPENCODE_CONTAINER_MAINTENANCE=1`), then start the selected session |
| `--container-shell` | bypass the OpenCode entrypoint and open `/bin/bash`, omitting all OpenCode arguments |
| `--container-git-worktree` | expose the physical current directory's entire immediate parent read/write, retaining the original physical working directory and naming basename |
| `--container-help` | wrapper help without engine or state side effects |

Normal `--help` remains an OpenCode argument. Other OpenCode arguments keep
their order and boundaries. The host must provide GNU coreutils `timeout` for
bounded session cleanup.

### Image

`OPENCODE_CONTAINER_IMAGE` selects the image name (default
`localhost/opencode-cli:latest`). One generic image serves every user: the
numeric identity is set at launch with `--userns=keep-id --user UID:GID`, and the
image contains no user name, UID, GID or entrypoint script. A missing image is
built on launch only with exact `OPENCODE_CONTAINER_MAINTENANCE=1`; without it
the wrapper stops before any build or pull. Restricted launches run the
immutable image ID resolved at launch.

OpenCode and OpenSpec versions are pinned in `Containerfile` (see
[Updating pinned image inputs](#updating-pinned-image-inputs)).
`OPENCODE_CONTAINER_VERSION` and the older `OPENCODE_VERSION` are ignored with a
warning.

### YOLO mode

`OPENCODE_CONTAINER_YOLO` auto-approves every OpenCode permission request.
`1`, `true` and `yes` enable it; unset, empty, `0`, `false` and `no` disable it;
words are case-insensitive and other values stop before engine queries. When
enabled, the session receives `OPENCODE_PERMISSION={"*":"allow"}`, which the
pinned OpenCode merges after its configuration files. It therefore overrides
configured `ask` and `deny` rules, like the native bypass flags of the other
wrappers. Setting a host `OPENCODE_PERMISSION` together with YOLO is refused.
YOLO does not change mounts, environment forwarding, delegation or hardening.
When disabled, configured OpenCode permissions apply unchanged.

OpenCode's own `--auto` flag is not used: OpenCode 1.18.3 accepts it only on the
default interface and `run`, and rejects it before other subcommands.

### Container names

The name is derived from the workspace basename:

```text
/home/yari/Workspace/project -> project-0
```

Later instances use the highest existing index plus one. Intermediate indices
are not reused while a higher index exists. Containers are ephemeral and are
removed when the session ends.

### Environment and provider credentials

Environment forwarding passes nonempty inherited values by name
(`--env VARIABLE`), so credentials are absent from generated Podman arguments.
Values remain visible to container processes and engine inspection. HOME/USER/XDG,
the YOLO permission and the enabled delegation endpoint are deliberate nonsecret
assignments; `--env-host` is never used. Three sources are forwarded:

1. The base allowlist: `TERM`, `COLORTERM`, `LANG`, `LC_ALL`, the proxy
   variables, and the OpenCode configuration variables (`OPENCODE_CONFIG`,
   `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`,
   `OPENCODE_SERVER_PASSWORD`, `OPENCODE_SERVER_USERNAME` and the
   `OPENCODE_DISABLE_*` controls).
2. The provider selected with `OPENCODE_CONTAINER_PROVIDER`. Values are
   OpenCode provider IDs; the variable sets come from the provider metadata of
   the pinned OpenCode 1.18.3:

   | Value | Variables |
   | --- | --- |
   | `anthropic` | `ANTHROPIC_API_KEY` |
   | `openai` | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |
   | `google` | `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `GEMINI_API_KEY` |
   | `openrouter` | `OPENROUTER_API_KEY` |
   | `amazon-bedrock` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, `AWS_BEARER_TOKEN_BEDROCK` |
   | `azure` | `AZURE_RESOURCE_NAME`, `AZURE_API_KEY` |
   | `opencode` | `OPENCODE_API_KEY` (OpenCode Zen) |
   | `none` | none |

   Unset means `none`. Any other value, including empty, stops before engine
   queries. Credentials stored with `opencode auth login` live in the mounted
   OpenCode data directory and work without this variable. Google Vertex is not
   supported: its credentials file is not mounted.
3. `OPENCODE_CONTAINER_ENV_VARS`: a space-separated list of extra variable
   names, for example `OPENCODE_CONTAINER_ENV_VARS="GH_TOKEN DATABASE_URL"`.
   Invalid names stop before engine queries. `HOME`, `USER`, the XDG bases,
   `CONTAINER_HOST` and `CONTAINER_CONNECTION` are skipped with a warning.

`GH_TOKEN` and `GITHUB_TOKEN` are never forwarded by default.

### Migrating from earlier releases

Earlier releases used `opencode-wrapper`, `OPENCODE_VERSION`, `Dockerfile`,
`io.opencode.*` labels and per-user `localhost/opencode-sandbox:*` images built
on the Alpine `ghcr.io/anomalyco/opencode` image, with `HOME` set to the host
home path. They also mounted `~/.claude`, `~/.agents` and `/etc/opencode`
whenever they existed, and forwarded every set Anthropic, OpenAI, Google/Gemini,
OpenRouter, AWS, Azure and GitHub variable.

- Point aliases to `opencode-container.sh`; `opencode-wrapper` warns.
- The first launch builds `localhost/opencode-cli:latest`. Remove old per-user
  images when no longer needed: `podman image ls localhost/opencode-sandbox`
  lists them and `podman image rm <image>` removes one.
- Drop `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION`; they are ignored.
- OpenCode state stays in the host XDG directories and is now seen at
  `/opencode-home/...` inside the session; nothing has to be copied.
- Launching from your home directory or a drive root such as `/mnt/d` is now
  refused; launch from a project directory or set exact
  `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1`.
- Sessions now have memory and CPU budgets besides the process limit. Each
  budget is enforced when the rootless engine delegates its cgroup v2
  controller (`cpu`, `memory`, `pids`); see "Session hardening, budgets and
  lifetime".
- Session containers are now labeled `io.opencode-container.*`. Inspect current
  sessions with `podman ps --all --filter label=io.opencode-container.managed=true`
  and containers left by earlier releases with
  `podman ps --all --filter label=io.opencode.managed=true`. The wrapper never
  removes or adopts the older containers; their names stay reserved.
- Set `OPENCODE_CONTAINER_PROVIDER` for the provider you use, or authenticate
  once with `opencode auth login` inside the container.
- While `OPENCODE_CONTAINER_PROVIDER` is unset, the wrapper prints one notice
  naming formerly forwarded variables that are set but no longer forwarded
  (names only). `OPENCODE_CONTAINER_PROVIDER=none` silences it.
- Azure users: OpenCode's `azure` provider reads `AZURE_RESOURCE_NAME` and
  `AZURE_API_KEY`, not the previously forwarded `AZURE_OPENAI_*` names.
- List GitHub tokens or extra provider keys in `OPENCODE_CONTAINER_ENV_VARS`.
- OpenCode no longer sees `~/.claude/CLAUDE.md` or `~/.claude/skills`. Move
  skills to `~/.agents/skills` with `OPENCODE_CONTAINER_AGENTS_DIR=1`, or move
  instructions and skills into the OpenCode configuration directory.
- Set `OPENCODE_CONTAINER_AGENTS_DIR=1` or `OPENCODE_CONTAINER_SYSTEM_CONFIG=1`
  to keep the other integrations.

## Network modes

`OPENCODE_CONTAINER_NETWORK` is required for every launch, either from the
managed launcher or set explicitly; an unset or empty value stops with
`setup required:` guidance before any engine call or state change. Unknown values fail before
image operations, and a failed restricted launch never retries with
unrestricted networking.

| Mode | Agent network | Podman delegation |
| --- | --- | --- |
| `offline` | Own loopback, pipes and connected socket pairs only; no model provider is reachable | Rejected |
| `provider` | As offline, plus the exact HTTPS hosts of one protected provider profile through an external proxy | Rejected |
| `unrestricted` | Ordinary runtime networking, the previous behavior | Exact `OPENCODE_CONTAINER_PODMAN=1` |

The restricted implementation is shared with `claude-container` and copied
unchanged from its tag `sandbox-ref-12`; see
[docs/network-contract.md](docs/network-contract.md) and
[network/README.md](network/README.md).

### Migration

Existing invocations stop until a mode is set. To keep the previous behavior:

```bash
export OPENCODE_CONTAINER_NETWORK=unrestricted
OPENCODE_CONTAINER_MAINTENANCE=1 ./opencode-container.sh --container-build --version
```

Shared state now always uses the fixed paths under `$HOME` (see
[Mounts and security](#mounts-and-security)). If you kept OpenCode state under
a custom `XDG_*_HOME`, move it there, or select it with
`OPENCODE_CONTAINER_CONFIG_DIR` (configuration only) or
`OPENCODE_CONTAINER_STATE_DIR` (an isolated home).

### Restricted prerequisites and qualification

Offline and provider modes require:
- host Python 3;
- a same-host Unix rootless Podman >= 4.9 service with Netavark;
- the standard OCI seccomp profile and usable Landlock ABI >= 3;
- a protected installation outside writable workspace and state trees;
- the static guard and its SHA-256 manifest in `network/bin`;
- a current local qualification report.

Run `--container-qualify` alone after preparation or relevant updates:

```bash
OPENCODE_CONTAINER_NETWORK=offline ./opencode-container.sh --container-qualify
```

Qualification is bound to the boot, engine, security policy, code, images,
policy, profile, CA trust and hardening settings. A reboot therefore requires
requalification. An active SELinux or AppArmor policy that cannot be identified
forces the full gate on every launch. The shipped release acceptance inventory
is empty, so installations report `locally-qualified`, never `release-measured`.

Restricted sessions receive no host proxy or CA variables. The relay sets the
proxy, and `NO_PROXY=localhost,127.0.0.1,::1` keeps OpenTUI's connection to its
local OpenCode server direct. Named Unix sockets, host services and LSP or
plugin downloads are unavailable (see [Plugins and network
modes](#plugins-and-network-modes)). `opencode run`, its tools and the TUI were
verified under the guard; see [the validation record](docs/validation.md).

### Provider mode

Provider mode needs:
- `OPENCODE_CONTAINER_NETWORK_PROFILE`;
- `OPENCODE_CONTAINER_NETWORK_POLICY`, a protected absolute policy path, normally
  `agent/policies/default.json` of the installation;
- `OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR`, a private native directory at its
  host path;
- `OPENCODE_CONTAINER_EGRESS_IMAGE`, the immutable proxy image ID or registry
  digest.

| Profile | Allowed host | Forwarded key |
| --- | --- | --- |
| `anthropic-api` | `api.anthropic.com` | `ANTHROPIC_API_KEY` |
| `openai-api` | `api.openai.com` | `OPENAI_API_KEY` |
| `openrouter-api` | `openrouter.ai` | `OPENROUTER_API_KEY` |
| `opencode-zen` | `opencode.ai` (OpenCode Zen) | `OPENCODE_API_KEY` |

The profile selects the only forwarded credential.
`OPENCODE_CONTAINER_PROVIDER` must be unset, `none` or the matching provider,
and `OPENAI_BASE_URL` is never forwarded. Offline sessions forward no provider
variable. Use API keys: from the environment, or stored with
`opencode auth login`. Browser-callback and OAuth logins, cloud providers,
custom `baseURL` values and local model servers have no profile.

Restricted sessions set `OPENCODE_DISABLE_AUTOUPDATE`,
`OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_DISABLE_LSP_DOWNLOAD`,
`OPENCODE_DISABLE_MODELS_FETCH` and `OPENCODE_DISABLE_SHARE` to `1` after
forwarding. Writable configuration cannot re-enable these features. The
bundled model catalog stays available. The background install of
`@opencode-ai/plugin` has no control: the proxy denies it, and OpenCode only
logs a warning.

### Plugins and network modes

Plugins need `unrestricted` mode. OpenCode installs every plugin named in its
configuration from `registry.npmjs.org` when a session starts. No profile allows
that host, and none will: it would let the agent download and publish arbitrary
packages. In `provider` and `offline` mode, a configuration that names plugins
can stall the session at startup without showing the TUI. The sanitized
diagnostics printed when the session ends then list `policy-denied` entries for
`registry.npmjs.org:443`.

Shared state mounts the host `~/.config/opencode`, so plugins configured for a
host installation of OpenCode also reach restricted sessions. On 2026-11-11, an
operator's earlier host configuration stalled provider mode in this way. A
fresh state started normally.

If you use plugins, manage the switch between modes yourself, and keep a
separate state for each:

- **Restricted sessions** (`provider`, `offline`) use a configuration without
  plugins: the shared state, or an isolated one.
- **Plugin sessions** use `unrestricted` with their own isolated state. That
  state holds the plugin configuration and the installed packages.

Exported variables override the managed launcher's saved choices for one
launch only. For example:

```bash
OPENCODE_CONTAINER_NETWORK=unrestricted \
OPENCODE_CONTAINER_STATE_DIR="$HOME/.local/state/opencode-container-plugins" \
  opencode-container
```

Authenticate once in each isolated state with `opencode auth login`;
credentials are not copied between states. Unrestricted sessions have no egress
filtering, and plugins run with the agent's authority. Do not add plugins to the
state used by restricted sessions, or their next start stalls again. To find an
offending plugin, look for `plugin` entries in `opencode.json` and for a
`package.json` in the configuration directory.

Limits:
- **Residual exfiltration.** The proxy binds the CONNECT host to the TLS server
  name of the initial and retried ClientHello. It cannot tell your credentials
  from an attacker's. An injected agent can therefore send workspace data to
  the allowed host (`api.anthropic.com`, `api.openai.com`, `openrouter.ai` or
  `opencode.ai`) with a foreign key or account. Only offline removes this
  channel.
- **Opaque application routing.** Matching SNI does not prove exclusive
  communication with your account. TLS 1.2 renegotiation is not inspected.
- **Hosted tools.** Provider-hosted tools such as web search run at the
  provider, outside this boundary.
- **Maintenance traffic.** Image pulls and build `RUN` steps happen outside
  runtime filtering.

### Operator build inputs

Guided setup prepares these artifacts. For direct operator workflows, prepare
them manually, under maintenance authorization:

```bash
export OPENCODE_CONTAINER_MAINTENANCE=1
tag=$(python3 -I network/agent_profile.py image toolchain development)
podman build --pull=never --tag "$tag" --file network/guard-build.Containerfile network
bash network/build-guard.sh "$PWD/network/bin"   # a protected native directory
podman build --pull=never --tag localhost/opencode-egress:local --file network/Containerfile network
podman image inspect --format '{{.Id}}' localhost/opencode-egress:local
```

The installation, including `network/bin`, must be on native Linux storage
outside writable workspace and state trees.

### Host CA trust

`OPENCODE_CONTAINER_TRUST_HOST_CA=1` (or `true`/`yes`) mounts one bundle
read-only at `/opencode-home/ca/bundle.pem`. The bundle is
`OPENCODE_CONTAINER_CA_BUNDLE`, or the first of
`/etc/ssl/certs/ca-certificates.crt` and `/etc/pki/tls/certs/ca-bundle.crt`.
The wrapper sets `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE` and
`NODE_EXTRA_CA_CERTS` to it. OpenCode's Bun runtime honors
`NODE_EXTRA_CA_CERTS` and `SSL_CERT_FILE`. Any other value fails before engine
calls.

## Mounts and security

Sessions use the dedicated home `HOME=/opencode-home`, with
`XDG_CONFIG_HOME=/opencode-home/.config`, `XDG_DATA_HOME=/opencode-home/.local/share`,
`XDG_CACHE_HOME=/opencode-home/.cache` and `XDG_STATE_HOME=/opencode-home/.local/state`.
The physical workspace keeps its host absolute path.

By default `/opencode-home` is an ephemeral 512 MiB tmpfs, and the caller's four
host OpenCode XDG directories are mounted read/write below it:

| Host source | Session path |
| --- | --- |
| `$HOME/.config/opencode`, or `OPENCODE_CONTAINER_CONFIG_DIR` | `/opencode-home/.config/opencode` |
| `$HOME/.local/share/opencode` | `/opencode-home/.local/share/opencode` |
| `$HOME/.cache/opencode` | `/opencode-home/.cache/opencode` |
| `$HOME/.local/state/opencode` | `/opencode-home/.local/state/opencode` |

The host paths are fixed below `$HOME`; host `XDG_*_HOME` variables do not
relocate them. This matches the state model of the shared sandbox code, which
checks one configuration directory plus fixed directories below `$HOME`.
`OPENCODE_CONTAINER_CONFIG_DIR`, a private absolute directory, replaces only the
configuration directory. Inside the session, `OPENCODE_CONTAINER_CONFIG_DIR`
is always set to `/opencode-home/.config/opencode`, the effective configuration
directory; the host value is never forwarded. HOME and the override must be
absolute. Other files
written below `/opencode-home` do not survive the session.

Missing state directories are created privately with a scoped umask. Every
resolved state directory must belong to the caller, permit read/write/traverse,
and deny all group/other permissions. Existing insecure directories cause a
preflight failure before image operations: the wrapper never chmods/chowns them
or imports credentials. Correct permissions manually or select private native
Linux storage when WSL/DrvFS does not enforce Unix modes. Symlinked state
directories and differently named symlink targets are resolved physically before
they are mounted at the fixed session paths. Conflicting mount destinations are
rejected.

Guided setup applies the same rule to all four shared directories
(`native.private_shared_dirs: true` in `agent/profile.json`). It stops before
image work, and the refusal names the path, the reason and, for a mode such as
`755` left by a host OpenCode installation, the fix `chmod 700 <path>`.

### Isolated state

`OPENCODE_CONTAINER_STATE_DIR=/absolute/path` replaces the shared host state
for that launch (an empty value selects shared state, like an unset one); it
conflicts with a nonempty `OPENCODE_CONTAINER_CONFIG_DIR`: the directory becomes the persistent `/opencode-home`, and the
four OpenCode directories are created inside it. The wrapper creates it
privately when missing and validates it with the same ownership and mode rules,
before any engine query. It must not equal, contain or lie inside the
workspace mount. The shared host OpenCode directories are not mounted in this mode,
and no credentials are copied: authenticate again with `opencode auth login`.

`$HOME/.agents` and `/etc/opencode` are optional read-only integrations,
mounted only on exact opt-in:

| Variable | Mounts (read-only) |
| --- | --- |
| `OPENCODE_CONTAINER_AGENTS_DIR=1` | `$HOME/.agents` (for example `~/.agents/skills`) |
| `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` | `/etc/opencode` |

Any other value leaves the directory unmounted. An opt-in for a missing
directory stops before any engine query. `$HOME/.claude` is never mounted: it
holds Claude Code credentials and sessions. The entire home, `.ssh`, `.aws`,
`.docker`, global `.gitconfig`, and Podman configuration are not implicitly
mounted.
Quoted bind arguments support spaces and commas. Colon/CR/LF bind paths are
rejected before image operations rather than misinterpreted.

The main container runs with:

- a read-only root filesystem;
- the host user's UID/GID;
- the `keep-id` user namespace;
- all capabilities dropped;
- `no-new-privileges`;
- explicit ephemeral tmpfs mounts with `nosuid,nodev` and mode 1777:
  executable `/tmp` (512 MiB) for OpenTUI shared-library loading, noexec
  `/var/tmp` (512 MiB), and noexec `/run` (32 MiB);
- the engine's `/dev` with a `devpts` at `/dev/pts` that allows
  pseudo-terminals, and an empty read-only `/dev/shm`. Podman 5 with crun
  1.27 cannot attach a terminal to a read-only `/dev`, so automatic
  read-only tmpfs provisioning stays enabled. An explicit `devpts` mount
  would get `ptmxmode=000`, and no pseudo-terminal could be opened. On
  Podman 5, `/dev` is the engine's writable tmpfs, but no device can be
  created without capabilities; on Podman 4.9 it stays read-only. Tools
  that need POSIX shared memory in `/dev/shm` are not supported;
- an empty read-only tmpfs at `/run/secrets`, which masks engine default mounts
  there (for example RHEL subscription certificates from `mounts.conf`);
- memory, CPU and process budgets (see below).

### Session hardening, budgets and lifetime

| Variable | Default | Accepted values |
| --- | --- | --- |
| `OPENCODE_CONTAINER_MEMORY_LIMIT` | `4g` | positive integer with unit `k`, `m` or `g`, up to 1 PiB |
| `OPENCODE_CONTAINER_CPU_LIMIT` | `2` | positive number with at most 3 decimals, up to 1024 |
| `OPENCODE_CONTAINER_PIDS_LIMIT` | `512` | integer from 1 to 4194304 |
| `OPENCODE_CONTAINER_RUN_TIMEOUT` | `0` (disabled) | whole seconds, at most 10 digits |
| `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE` | unset | exactly `1` permits a refused workspace |

Only an unset budget selects its default; no value disables a budget. Invalid
values stop with status 1 before any engine query or state creation. Each budget
is enforced only when the rootless engine delegates its cgroup v2 controller
(`memory`, `cpu`, `pids`), as reported by `podman info`
(`Host.CgroupControllers`). A missing controller leaves that budget unenforced:
the wrapper does not request it, prints a notice such as `opencode-container:
agent CPU budget not enforced: cgroup controller cpu is not delegated to the
rootless engine`, and continues without a question. Provider proxies follow the
same rule for their 128-process and 256 MiB limits. Without the memory or
process budget, a session can exhaust host memory or processes for your user.
After creating the container the wrapper inspects it and starts it only when
every enforced budget equals its selected value and no unenforced budget is
present; otherwise it removes its own container and names the reported
controllers. Restricted qualification records the enforced set, so a change in
delegation requires requalification. Budgets and tmpfs sizes do not limit
workspace or state storage growth.

`OPENCODE_CONTAINER_RUN_TIMEOUT` sets Podman's native container lifetime. When
it stops a session, the wrapper prints a notice and keeps the engine client's
exit status (255 on Podman 4.9.3). The notice compares whole seconds, so with a
1-second limit a fast non-zero exit can print it; the status is never altered.

The writable workspace, or the worktree parent, must not physically be `/`,
`/home`, `/root`, `/etc`, `/usr`, `/var`, `/bin`, `/sbin`, `/lib`, `/lib64`,
`/boot`, `/opt`, `/srv`, `/mnt`, `/media`, `/proc`, `/sys`, `/dev`, `/run`,
`/tmp`, the caller's physical home or a `/mnt/<letter>` drive root.
Descendants such as `/mnt/d/project` are allowed. Exact
`OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1` permits a refused directory with
a warning; it relaxes no other check.

The rootless Podman socket still gives OpenCode full control over the user's
Podman engine. A process deliberately using the API can access host paths that
the user can read. Leave session delegation disabled when it is unnecessary.

## Included Tools

`Containerfile` builds one generic image on
`docker.io/library/node:22-bookworm-slim`, pinned by digest, with OpenCode
(`opencode-ai`) and OpenSpec (`@fission-ai/openspec`) installed from npm at exact
versions, plus `bash`, `bubblewrap`, `bzip2`, `ca-certificates`, `coreutils`,
`curl`, `diffutils`, `file`, `findutils`, `gawk`, `git`, `grep`, `jq`, `less`,
`nano`, `patch`, `podman`, `procps`, `python3`, `ripgrep`, `sed`, `tar`, `unzip`,
`util-linux`, `xz-utils` and `zip`. npm verifies each package's registry
integrity; the platform binary packages are exact-version dependencies of
`opencode-ai`. OpenTUI runs on glibc and needs the executable `/tmp`.

The npm install step selects the x64 AVX2 or baseline OpenCode binary from the
build host's CPU. Build the image on the host that runs it; do not copy an image
built on an AVX2 host to a host without AVX2.

Only image-exists status 1 triggers an automatic build; other engine/storage
errors stop startup. Explicit refresh still performs all preflights first.
Builds use the wrapper's physical recipe directory and pass no build arguments.

The sole `.containerignore` defaults to denying all inputs and allows only root
`Containerfile` and `.containerignore`; the image needs no local COPY input.
Update this allowlist deliberately for any future local input; nested
lookalikes, credentials, state and unrelated files must remain excluded.

### Updating pinned image inputs

`Containerfile` records `OPENCODE_VERSION`, `OPENSPEC_VERSION` and the base
image digest; `tests/test_image_pins.py` rejects floating inputs. To update:

1. Change the recorded version or digest in `Containerfile`.
2. Re-read the provider metadata of the new OpenCode version and update the
   `OPENCODE_CONTAINER_PROVIDER` table if needed.
3. Re-check how the new version merges `OPENCODE_PERMISSION` (YOLO) and parses
   flags such as `--auto`.
4. Re-measure the provider and optional-traffic hosts and the
   `OPENCODE_DISABLE_*` controls, then update `agent/policies/default.json`
   with a new revision and `tested.cli`; the pin test requires the two
   versions to match.
5. Rebuild explicitly with `OPENCODE_CONTAINER_MAINTENANCE=1` and
   `--container-build`, then run `--container-qualify` again.
6. Rerun the credential-free and real-engine checks, including OpenTUI.
7. Record the tested versions with the date in `docs/validation.md`.

Do not run `opencode upgrade` inside the container: the main filesystem is
immutable and automatic updates are disabled.

Image preparation fetches Debian packages over verified HTTPS only and needs
outbound HTTPS (443) to the Debian, npm and container registries, not port 80.
With host CA trust enabled, the selected bundle is also passed to the build as
the `build-ca` secret, so the package fetches verify on TLS-intercepting
networks; it is never stored in a layer. The recipe creates the working
directory `/workspace` in the image, so the engine never creates or chowns it
when a container starts (this fails for large domain UIDs under `keep-id`).

## Session lifecycle

Names use the original physical workspace basename, sanitized, followed by an
index above the highest running/stopped suffix. Parse at most nine digits in
base ten (including `08`); ignore malformed/oversized suffixes. Reserve atomically
with create and retry at most 20 confirmed collisions. Checked enumeration and
collision errors stop startup. Never replace or remove another session to obtain
a name. Private creation records and `io.opencode-container.session` identify
owned full container IDs; stderr warnings must not become part of an ID.

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
label=io.opencode-container.managed=true` and the reported session label to
inspect them; never indiscriminately remove other managed sessions.

## Verification

Run static checks first, then the synthetic suite (Python standard library only):

```bash
bash -n opencode-container.sh
bash -n opencode-wrapper
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Synthetic tests use a fake Podman, disposable HOME/XDG, dummy credential strings,
and filesystem socket fixtures; they do not contact the real engine.
Real rootless acceptance requires the built image and a running rootless
Unix service. `tests/run-runtime.sh` runs the tests through Podman, mounting the
workspace at its host absolute path and a disposable private Linux state volume.
Its tooling image defaults to the OpenCode image itself, which provides Python
3, Bash, GNU coreutils timeout, Git and Podman remote; `OPENCODE_TEST_TOOLS_IMAGE`
selects another one. The runner never imports host application credentials or
changes service/policy setup.

```bash
OPENCODE_CONTAINER_NETWORK=unrestricted OPENCODE_CONTAINER_MAINTENANCE=1 ./opencode-container.sh --container-build --version
bash tests/run-runtime.sh                  # unrestricted runtime suite
bash tests/run-runtime.sh --wrapper        # wrapper contracts with a fake engine
bash tests/run-runtime.sh --shared         # shared suites copied from claude-container
bash tests/run-runtime.sh --setup          # shared setup suite
bash tests/run-runtime.sh --setup-runtime  # guided setup with real rootless Podman
bash tests/run-runtime.sh --network        # restricted modes with real rootless Podman
bash tests/run-runtime.sh --guard          # guard runtime fixtures (needs the toolchain image)
```

Further modes: `--qualification`, `--network-feasibility`, `--network-policy`,
`--mux` and `--guard-idle` (the 305-second idle check).

The real suite exercises mount flags/capacities/lifetime, identity, state,
context filtering, concurrency, signals, stdin, worktrees, delegation and
remapping, version output, the YOLO permission, labels, the deprecated alias,
effective capabilities and cgroup budgets, process-limit enforcement, the
lifetime limit, the refused home workspace, shared and isolated state, the tool
inventory, and actual OpenTUI startup/quit through a PTY.
The renderer uses a disposable home with no provider credentials. Its ignored
`.test-state/renderer-last.txt` transcript is available for local inspection.
Synthetic and runtime results are recorded separately in
[the validation record](docs/validation.md). Version output alone does
not initialize OpenTUI and cannot establish renderer compatibility.

Inspect remaining containers with `podman ps --all --filter
label=io.opencode-container.managed=true`; other users' active sessions must
remain intact.
