# OpenCode CLI in Podman

`opencode-container.sh` runs OpenCode in a rootless Podman container while
preserving the workspace and OpenCode configuration between sessions. The
image filesystem is read-only, with a writable workspace, private OpenCode XDG
state and explicit temporary storage. Every launch runs in one network mode:
`provider` (the default; only the exact hosts of one provider profile),
`offline` or `unrestricted`; see [Network modes](#network-modes). Sessions never
receive a host Podman socket; when the toolchain library holds container images,
each session gets a private, rootless container engine for container-based tests
([Container tests](#container-tests)).

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
implicit remote contexts, TCP and SSH (including the Podman machine connection
that `podman.exe` uses) are rejected. On Windows, the PowerShell entry runs the
sandbox inside the Podman machine instead; see
[Windows with Podman machine](#windows-with-podman-machine). Workspace/state sources
must exist at the same absolute paths on the service host.

## Enable the launch service

Restricted networking currently requires a same-host Unix launch service. An
unrestricted local session needs no API service. Host Podman is always required
for image operations and launch.

Every session verifies that its launch engine is Linux and rootless before
image inspection, build, or launch. An explicit same-host Unix `CONTAINER_HOST`
is also supported, including when this wrapper runs inside another container;
launch verification then queries that service, which never reaches the session.
Replies must contain one complete record, with no terminator or one final LF,
and no CR or extra blank/nonblank records; query failures remain failures.

Host Podman delegation (`OPENCODE_CONTAINER_PODMAN=1`, with
`OPENCODE_CONTAINER_PODMAN_SOCKET`) was removed in every mode. Exact
`OPENCODE_CONTAINER_PODMAN=1` stops every launch and build-only operation
before engine queries with migration guidance pointing to image toolchains
(`--container-toolchain add`); other values and `OPENCODE_CONTAINER_PODMAN_SOCKET`
are ignored. Without image toolchains in the library, no session engine starts
and both `CONTAINER_HOST` and `DOCKER_HOST` are unset. See
[Container tests](#container-tests).

Prepare the rootless launch service manually if needed:

```bash
systemctl --user start podman.socket
# Optional, to persist service activation across logins:
systemctl --user enable --now podman.socket
# Without systemd, run in a separate terminal:
podman system service --time=0
```

The wrapper never starts or enables a service on ordinary launches (guided
setup can enable `podman.socket` after separate confirmation) and retains host
security policy on session containers: no SELinux label disabling or automatic
relabeling.

## First run: guided setup

New users run the guided setup once, from a reviewed checkout, as the non-root
Linux/WSL user who will use the sandbox:

```bash
bash ./opencode-container.sh --container-setup
```

Setup asks for the network mode (default `provider`), the API-key method
(`anthropic`, `openai`, `openrouter` or `opencode-zen`), shared or isolated
state, YOLO, CA trust, budgets and lifetime. It discloses the
residual exfiltration risk of provider mode, prepares the runtime image, the
session container engine image (`localhost/opencode-cli-engine:latest`) and, in
restricted modes, the guard and proxy image under explicit maintenance consent,
installs a protected release, saves schema 3 preferences (migrating saved
schema 1/2 delegation preferences automatically), qualifies it and runs a
credential-free smoke check. It never stores a key; provider mode
ends with `Authentication pending` and the variable to supply. Afterward, launch
from a workspace with the managed command, by default
`~/.local/bin/opencode-container`. See [docs/setup.md](docs/setup.md).

A launch with an unset or empty `OPENCODE_CONTAINER_NETWORK` selects
`provider`; without a protected installation or the provider settings that
setup saves, it stops with `setup required:` guidance before any engine call or
state creation. Direct operator launches with an explicit mode remain available
(see [Network modes](#network-modes)).

## Usage

Make the wrapper executable and add an alias to your shell configuration:

```bash
chmod 0755 /mnt/d/Workspace/opencode-container/opencode-container.sh
alias opencode='/mnt/d/Workspace/opencode-container/opencode-container.sh'
```

Reload the shell configuration or open a new session.

The wrapper preserves the normal OpenCode interface:

```bash
cd /home/yari/Workspace/project
opencode
opencode --version
opencode run "Describe this project"
```

A direct launch from a checkout selects a mode explicitly, usually
`OPENCODE_CONTAINER_NETWORK=unrestricted` (see [Network modes](#network-modes)).
Building the image, including the first build, needs exact
`OPENCODE_CONTAINER_MAINTENANCE=1`. Wrapper options:

| Option | Effect |
| --- | --- |
| `--container-qualify` | qualify a prepared restricted installation with fixed local controls; must be used alone |
| `--container-build` | rebuild the image from the pinned inputs (requires `OPENCODE_CONTAINER_MAINTENANCE=1`); with OpenCode arguments it then starts the session, without them (also with `--container-shell` or `--container-git-worktree`) it validates every setting, builds and exits |
| `--container-shell` | bypass the OpenCode entrypoint and open `/bin/bash` with the remaining arguments, for example `--container-shell -c 'make test'`; YOLO never applies |
| `--container-git-worktree` | expose the physical current directory's entire immediate parent read/write, retaining the original physical working directory and naming basename |
| `--container-toolchain` | manage the shared read-only toolchain library; must be the first argument (see [Toolchains](#toolchains)) |
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
the wrapper stops before any build or pull. Every image carries a
`build-inputs-hash` label over `Containerfile`, `.containerignore`,
`network/relay.py` and `network/mux.py`; a launch refuses an image built from
other inputs, or without the label, and names the rebuild command. Restricted
launches run the immutable image ID resolved at launch.

OpenCode and OpenSpec versions are pinned in `Containerfile` (see
[Updating pinned image inputs](#updating-pinned-image-inputs)).

### YOLO mode

`OPENCODE_CONTAINER_YOLO` auto-approves every OpenCode permission request.
`1`, `true` and `yes` enable it; unset, empty, `0`, `false` and `no` disable it;
words are case-insensitive and other values stop before engine queries. When
enabled, the session receives `OPENCODE_PERMISSION={"*":"allow"}`, which the
pinned OpenCode merges after its configuration files. It therefore overrides
configured `ask` and `deny` rules, like the native bypass flags of the other
wrappers. Setting a host `OPENCODE_PERMISSION` together with YOLO is refused.
Shell mode and the qualification probe never apply YOLO. YOLO does not change
mounts, environment forwarding, the session container engine or hardening.
When disabled, configured OpenCode permissions apply unchanged.

The wrapper implements YOLO through `OPENCODE_PERMISSION`. OpenCode 1.19.5
accepts its native `--auto` option on the default interface and `run`. Native
`--auto` leaves explicit deny rules in effect.

### Container names

The name is derived from the workspace basename:

```text
/home/yari/Workspace/project -> project-0
```

A basename with no usable character falls back to `opencode-container`.
Later instances use the highest existing index plus one. Intermediate indices
are not reused while a higher index exists. Containers are ephemeral and are
removed when the session ends.

### Environment and provider credentials

Environment forwarding passes nonempty inherited values by name
(`--env VARIABLE`), so credentials are absent from generated Podman arguments.
Values remain visible to container processes and engine inspection. `HOME`,
`USER`, `EDITOR=nano`, `VISUAL=nano`, the XDG bases, the YOLO permission and
(when library images are present) the session engine endpoint (`CONTAINER_HOST`
and `DOCKER_HOST`) are deliberate nonsecret assignments; `--env-host`
is never used. Unrestricted sessions run with `--init` and see their container
name as `CONTAINER_NAME`. In offline and provider sessions the confined guard
plays the role of `--init`: Ctrl+C and the shutdown signals reach OpenCode, and
the session ends with OpenCode's status. Three sources are forwarded:

1. The base allowlist: `TERM`, `COLORTERM`, `LANG`, `LC_ALL`, in unrestricted
   mode `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY` and their lowercase
   forms, and the OpenCode configuration variables (`OPENCODE_CONFIG`,
   `OPENCODE_CONFIG_DIR`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`,
   `OPENCODE_SERVER_PASSWORD`, `OPENCODE_SERVER_USERNAME`, and in unrestricted
   mode the `OPENCODE_DISABLE_*` controls).
2. In unrestricted mode, the provider selected with `OPENCODE_CONTAINER_PROVIDER`.
   Values are OpenCode provider IDs. The table lists the variables the wrapper
   forwards. The four provider-mode credentials match the OpenCode 1.19.5
   catalog.

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
3. `OPENCODE_CONTAINER_ENV_VARS`: extra variable names separated by
   whitespace, for example `OPENCODE_CONTAINER_ENV_VARS="GH_TOKEN DATABASE_URL"`.
   Invalid names stop before engine queries. Names the launcher sets itself
   (`HOME`, `USER`, `TERM`, `EDITOR`, `VISUAL`, the XDG bases, `CONTAINER_HOST`,
   `CONTAINER_CONNECTION`, the CA variables and
   `OPENCODE_CONTAINER_CONFIG_DIR`) are skipped with one notice each;
   restricted modes also skip the proxy, CA and `OPENCODE_DISABLE_*` names, and
   provider mode another profile's key. From the Windows entry, the OpenCode
   configuration variables of source 1 and the provider variables of source 2
   need this list too; see
   [Windows with Podman machine](#windows-with-podman-machine).

`GH_TOKEN` and `GITHUB_TOKEN` are never forwarded by default.

The `opencode-wrapper` shim and the `OPENCODE_CONTAINER_VERSION` and
`OPENCODE_VERSION` variables are gone; the earlier names have no effect and
print no notice.

## Network modes

An unset or empty `OPENCODE_CONTAINER_NETWORK` selects `provider`; without a
protected installation or the provider settings that setup saves, the launch
stops with `setup required:` guidance before any engine call or state change.
The managed launcher supplies the saved mode. Unknown values fail before image
operations, and a failed restricted launch never retries with unrestricted
networking.

| Mode | Agent network | Session container engine |
| --- | --- | --- |
| `offline` | Own loopback, pipes and connected socket pairs only; no model provider is reachable | Private rootless engine when library holds images (offline network); `OPENCODE_CONTAINER_PODMAN=1` refused |
| `provider` (default) | As offline, plus the exact HTTPS hosts of one protected provider profile through an external proxy | Private rootless engine when library holds images (provider boundary); `OPENCODE_CONTAINER_PODMAN=1` refused |
| `unrestricted` (explicit only) | Ordinary runtime networking | Private rootless engine when library holds images (session network); `OPENCODE_CONTAINER_PODMAN=1` refused |

The restricted implementation is shared with `sandbox-container` and copied
unchanged from its tag `sandbox-ref-36`; see
[docs/network-contract.md](docs/network-contract.md) and
[network/README.md](network/README.md).

Shared state always uses the fixed paths under `$HOME` (see
[Mounts and security](#mounts-and-security)); `OPENCODE_CONTAINER_CONFIG_DIR`
selects another configuration directory and `OPENCODE_CONTAINER_STATE_DIR` an
isolated home.

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

Qualification is bound to the boot, engine, security policy, code (including
`launcher/core.sh` and `agent/launcher.sh`), images, policy, profile, CA trust
and hardening settings, and to the resolved mode, including the provider
default. A reboot therefore requires
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
`opencode auth login`. `OPENCODE_CONTAINER_ENV_VARS` cannot forward another
profile's key in provider mode. Browser-callback and OAuth logins, cloud providers,
custom `baseURL` values and local model servers have no profile.

Offline and provider sessions set `OPENCODE_DISABLE_AUTOUPDATE`,
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

With a Podman machine on Windows, the host is the machine: it must first
import the CAs that Windows trusts
([Trusting a host CA on Windows](#trusting-a-host-ca-on-windows)).

## Windows with Podman machine

On Windows, `opencode-container.ps1` starts the sandbox from PowerShell on the
rootless engine of a Podman machine that Podman Desktop created with the WSL
provider. The session runs inside the machine's WSL distribution
(`podman-machine-default`, user `user`), in the PID and mount namespaces where
the machine runs systemd and its Podman service, as the machine's own login
shells do. The entry uses neither `podman.exe` nor the machine's SSH or
Windows API connection, so it works while other WSL distributions, such as
Ubuntu, are running.

Prerequisites:

- Windows PowerShell 5.1 or PowerShell 7, with a policy that allows local
  scripts, for example `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`;
- a rootless Podman machine with the WSL provider, created with Podman
  Desktop, and started by Podman (Podman Desktop or `podman machine start`)
  before setup and sessions;
- `sudo` without a password for the machine's user, which Podman machines
  provide: sessions and setup enter the machine's systemd namespaces with
  `sudo nsenter`, as its login shells do (`/usr/local/bin/enterns`);
- a checkout of this repository in a folder on a Windows drive, with LF line
  endings. The repository's `.gitattributes` keeps them LF even with
  `core.autocrlf=true`; [docs/setup.md](docs/setup.md) explains how to fix an
  older CRLF checkout.

Run setup once from the checkout, in an interactive PowerShell window:

```powershell
cd C:\Work\opencode-container
.\opencode-container.ps1 --container-setup
```

Setup runs the guided setup inside the machine distribution. The release,
preferences and images are installed there, in
`~/.local/lib/opencode-container`. Its output leaves out the Linux shell
guidance; the entry prints how to start sessions. Setup finds the machine's
own Podman service, so it offers provider networking, the default, with the
four API key methods, and offline and unrestricted networking, as on Linux.

Every method uses an API key. Set `$env:ANTHROPIC_API_KEY = '...'` in
PowerShell before `opencode-container.ps1`, or `OPENAI_API_KEY`,
`OPENROUTER_API_KEY` or `OPENCODE_API_KEY` for the `openai`, `openrouter` and
`opencode-zen` methods; setup names the variable of the method it saved. The
entry forwards the key by name, and setup stores none. A key stored with
`opencode-container.ps1 auth login` stays in OpenCode's data directory in the
machine (`~/.local/share/opencode` in shared state mode), separate from
OpenCode on Windows, and works without the variable. Rerun setup after
updating the checkout, and after the machine is recreated. To run the sandbox
as a command without keeping the checkout, install it instead
([Install as a command](#install-as-a-command)).

Start sessions from a project directory on a Windows drive:

```powershell
cd C:\Work\my-project
C:\Work\opencode-container\opencode-container.ps1
C:\Work\opencode-container\opencode-container.ps1 --container-shell -c 'git status'
C:\Work\opencode-container\opencode-container.ps1 --container-help
```

The project is mounted at its drive path, for example `/mnt/c/Work/my-project`.
A launch is refused before any engine query in these cases:

- the machine is stopped: the entry does not start its distribution, because
  `wsl.exe` would start it without the user's runtime directory
  `/run/user/<uid>`, where no `podman` command works. Start the machine with
  Podman Desktop or `podman machine start`;
- the distribution runs without that directory, because `wsl.exe` alone
  started it. Run `wsl --terminate podman-machine-default`, then start the
  machine with Podman. Setup refuses both states too;
- `sudo` asks the machine's user for a password, so the entry cannot enter the
  machine's systemd namespaces. Setup refuses it too;
- the location is a network share, a path inside a WSL distribution, a drive
  the distribution does not mount, or not a file system path;
- the project or the worktree parent contains the checkout, or lies inside it;
- the project is a Windows system or profile folder (see
  [Session hardening, budgets and lifetime](#session-hardening-budgets-and-lifetime)).

The exit status, the terminal and Ctrl+C work as on Linux. Closing the window
also ends the session and removes its container. The machine's engine uses
the `cgroupfs` manager: the memory and CPU budgets are not enforced, and the
process budget uses the process rlimit, as the launch notices state (see
[Session hardening, budgets and lifetime](#session-hardening-budgets-and-lifetime)).

| Variable | Meaning |
| --- | --- |
| `OPENCODE_CONTAINER_NETWORK` | `provider`, `offline` or `unrestricted` for one launch (default: the mode setup saved); a restricted mode needs a setup that prepared it |
| `OPENCODE_CONTAINER_WSL_DISTRO` | WSL distribution (default `podman-machine-default`) |
| `OPENCODE_CONTAINER_WSL_USER` | user in the distribution (default `user`) |
| `OPENCODE_CONTAINER_WSL_INSTALLATION` | absolute installation path in the distribution, when setup used another one |

Set them with `$env:NAME = 'value'`. The entry forwards to the launcher in the
distribution, by name, the other `OPENCODE_CONTAINER_*` variables whose names
use only letters, digits and `_`, such as `OPENCODE_CONTAINER_YOLO` and
`OPENCODE_CONTAINER_PROVIDER`, the four method keys `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `OPENROUTER_API_KEY` and `OPENCODE_API_KEY`, and the names
listed in `OPENCODE_CONTAINER_ENV_VARS`. `OPENCODE_CONTAINER_CONFIG_DIR` is
forwarded only when it holds a distribution path (starting with `/`): a
Windows path is skipped with a notice, and the directory saved by setup
applies. It forwards no other Windows variable.

OpenCode's native variables (`OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`,
`OPENCODE_CONFIG_CONTENT`, `OPENCODE_PERMISSION`, `OPENCODE_SERVER_USERNAME`,
`OPENCODE_SERVER_PASSWORD` and the `OPENCODE_DISABLE_*` controls) and the
variables of `OPENCODE_CONTAINER_PROVIDER` (see
[Environment and provider credentials](#environment-and-provider-credentials))
therefore reach a session from Windows only when `OPENCODE_CONTAINER_ENV_VARS`
lists them, for example
`$env:OPENCODE_CONTAINER_ENV_VARS = 'OPENCODE_CONFIG_CONTENT GEMINI_API_KEY'`.
A listed name then reaches the session as on Linux, under the same
reserved-name rules. Path values, such as `OPENCODE_CONFIG`,
`OPENCODE_CONFIG_DIR` and `OPENCODE_CONTAINER_STATE_DIR`, are distribution
paths, such as `/home/user/...`. `OPENCODE_CONTAINER_AGENTS_DIR=1` and
`OPENCODE_CONTAINER_SYSTEM_CONFIG=1` mount the machine's `~/.agents` and
`/etc/opencode`, not Windows folders.

Limits on Windows:

- No host Podman delegation, as on Linux: `OPENCODE_CONTAINER_PODMAN=1` is
  refused with migration guidance, and a release whose setup saved delegation
  asks to rerun setup from Windows. Sessions with image toolchains get their
  private container engine in the machine ([Container tests](#container-tests)).
- PowerShell pipeline input, such as
  `'x' | .\opencode-container.ps1 --container-shell -c cat`, is refused, because
  PowerShell alters it. Redirect a file from `cmd.exe` instead:
  `cmd /c "powershell -File C:\Work\opencode-container\opencode-container.ps1 --container-shell -c cat < input.txt"`.
- PowerShell parses the arguments first. Quote a `--` meant for OpenCode or Bash
  (`'--'`), values with commas (`'a,b'`), numbers whose spelling matters
  (`'007'`) and arguments of the form `-x:y`. The encoded arguments are
  limited to 32766 characters.
- A variable with an empty value counts as unset.
- `podman machine stop` (`wsl --terminate`) ends running sessions.
- After the machine starts, the folder of its first session may stay in use
  by a WSL process until `wsl --shutdown`, so Windows cannot delete that
  folder meanwhile.
- Projects on a Windows drive go through drvfs, which is slow on large trees.
  Git for Windows clones with `core.autocrlf=true` look modified to Git in the
  session: set `core.autocrlf=false` for the project, or give it a
  `.gitattributes`.
- Bitdefender's Advanced Threat Control (`Atc4.Detection`) has blocked the
  operator validation script `tools/windows-validate.ps1` of
  `sandbox-container`, and quarantined files while validation bundles were
  extracted with `tar`, for example `tests/fixtures/shell-agent/launcher.sh`,
  which only the Linux tests use. Setup, the installer and sessions ran with it
  active, and another Windows system with other antivirus products ran the
  validation without problems. Run the validation script with the checkout
  folder excluded, or with the protection paused for the run, as your
  administrator allows. Setup and the entry fail when a file they need is
  missing: restore it from the quarantine, and report the false positive to
  the vendor.

### Trusting a host CA on Windows

Setup and sessions run in the machine, so host CA trust uses a bundle of the
machine, not the Windows certificate store. On a network that intercepts TLS
(a corporate proxy that re-signs certificates), the machine trusts the
interception CA only when Podman imports the Windows store into it. Without
it, image pulls and builds in the machine and HTTPS requests in sessions fail
with a certificate verification error. With Podman 6.0 or later, enable the
import once. `podman machine set` fails while the machine runs, so stop it
first:

```powershell
podman machine stop
podman machine set --import-native-ca
podman machine start
```

The import happens at every machine start: Podman copies the CAs that Windows
trusts into the machine and runs `update-ca-trust`, so the machine's system
bundle contains them. Restart the machine after Windows gains a new CA.

Then run setup and answer yes to "Trust a host CA bundle?". Keep the bundle
setup proposes, the machine's system bundle (see
[Host CA trust](#host-ca-trust)): setup passes it to the image builds and saves
it for sessions. Rerun setup after the machine is recreated, and enable the
import again on the new machine.

### Toolchains on Windows

The [toolchain](#toolchains) commands run from PowerShell like the other
options, from any directory outside the checkout:

```powershell
opencode-container --container-toolchain add java21
opencode-container --container-toolchain add C:\Users\me\recipes\x.json
opencode-container --container-toolchain list
```

- **Location:** the library lives inside the Podman machine's distribution, in
  `~/.local/share/sandbox-toolchains` of the machine user, or in
  `OPENCODE_CONTAINER_TOOLCHAINS_DIR` (a distribution path). Every wrapper that
  runs in the machine shares it. Recreating the machine removes it: after the
  new setup, add the toolchains again.
- **Windows paths:** a recipe path or a local archive path in a recipe written
  as a Windows drive path (`C:\...` or `C:/...`) is translated to its drive
  mount in the machine. Network shares, paths inside a WSL distribution and
  drives that the distribution does not mount are refused. Keep your recipes
  outside project folders (see [Managing the library](#managing-the-library)).
- **Network:** pulls and downloads run inside the machine. On a network that
  re-signs TLS, they trust the CA that `podman machine set --import-native-ca`
  adds to the machine (see [Trusting a host CA on Windows](#trusting-a-host-ca-on-windows)).

### Install as a command

Instead of setup from the checkout, you can install the entry for your
Windows account:

```powershell
cd C:\Work\opencode-container
.\opencode-container.ps1 --container-install
```

The install copies the entry, the Windows scripts and every file that setup
needs into `%LOCALAPPDATA%\Programs\opencode-container`. It then adds that
folder to your user `PATH` (`HKCU\Environment`, no administrator rights; the
other entries and their `%VAR%` references stay as they are) and runs setup
from the copy. The installer announces the `PATH` change before making it;
nothing is written to the PowerShell profile or system-wide. Afterwards the
checkout can be deleted, and a new PowerShell window runs the command from any
project directory:

```powershell
cd C:\Work\my-project
opencode-container
opencode-container --container-shell -c 'git status'
opencode-container --container-setup
```

New PowerShell windows and new Windows Terminal tabs find the command; the
window or tab that ran the install may not. When setup fails after the copy,
the copy and the `PATH` entry stay; finish with
`opencode-container --container-setup`.

To update, run `--container-install` again from a newer checkout or download.
It replaces the installed files, removes the ones the new version no longer
has, and runs setup. Do not update while a setup runs from the installed
copy. The installed command refuses to install itself. An
interrupted install leaves the copy marked incomplete: the command then
refuses to start sessions until the next install completes. Two installs never
run at once.

`opencode-container --container-uninstall` (also from a checkout) removes the
`PATH` entry and the installed copy. The installation inside the Podman machine
stays until the machine is reset. A folder still used by a WSL process is
reported; `wsl --shutdown` releases it.

The scripts are not signed. The installer writes new local files, so the
installed command runs under the default `RemoteSigned` policy. A downloaded
zip keeps the Mark of the Web on its files: run its first install as
`powershell -ExecutionPolicy Bypass -File .\opencode-container.ps1 --container-install`,
or `Unblock-File` its files first. Running the installer is your decision to
trust that source. Policies stricter than `RemoteSigned`, such as `AllSigned`,
are unsupported.

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
before any engine query. The value must be absolute, without colon, CR or LF.
Every child the launcher uses below it, and the CA mount parent, must stay
inside it and be private. It must not equal, contain or lie inside the
workspace mount. The shared host OpenCode directories are not mounted in this mode,
and no credentials are copied: authenticate again with `opencode auth login`.

### Read-only state

`OPENCODE_CONTAINER_READONLY_STATE` (`1`, `true` or `yes`, any case) mounts the
existing configuration directory and the three shared OpenCode directories
read-only below the ephemeral home, from shared state or from an isolated home.
They must already exist and be readable; nothing is created, and OpenCode cannot
save sessions or sign-ins in such a launch.

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
rejected before any build or container creation rather than misinterpreted.

The main container runs with:

- a read-only root filesystem;
- the host user's UID/GID;
- the `keep-id` user namespace;
- all capabilities dropped;
- `no-new-privileges`;
- explicit ephemeral tmpfs mounts with `nosuid,nodev`: executable `/tmp`
  (512 MiB, mode 1777) for OpenTUI shared-library loading, noexec `/var/tmp`
  (512 MiB, mode 1777), and noexec `/run` (32 MiB, not writable by the session
  user); the profile declares executable temporary storage
  (`native.exec_tmp: true`);
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
same rule for their 128-process and 256 MiB limits. After creating the
container the wrapper inspects it and starts it only when every enforced budget
equals its selected value and no unenforced budget is present; otherwise it
removes its own container and names the reported controllers. Restricted
qualification records the enforced set, so a change in delegation requires
requalification. Budgets and tmpfs sizes do not limit workspace or state
storage growth.

A rootless engine applies cgroup limits only through the `systemd` cgroup
manager (`podman info --format '{{.Host.CgroupManager}}'`). With `cgroupfs`,
for example on a Podman machine on WSL, the engine reports every controller but
ignores the limits. The sandbox therefore treats no controller as delegated: it
prints `agent memory budget not enforced: the rootless engine uses the cgroupfs
cgroup manager, which applies no cgroup limits` and the matching CPU line, and
the process budget uses the fallback below.

The process budget has a fallback. Without the `pids` controller, the agent
container's first process sets its soft and hard process rlimit to the
selected budget, and the notice reads `agent process budget enforced through the
process rlimit (512 tasks of the session user, threads included)`:
- **Where it is set.** The container starts with a fixed `/bin/sh` step,
  `{ ulimit -u N 2>/dev/null || ulimit -p N; } && exec <program>`, before
  OpenCode, the shell or, in restricted modes, the guard runs (dash names the
  limit `-p`). If the limit cannot be set, the container stops before anything
  else runs, and each launch checks that the created container starts with this
  step.
- **Per session.** Linux 5.14 and later count the limit per user namespace, and
  the step sets it inside the container's own. The wrapper never uses
  `--ulimit nproc`: the engine applies that limit before it creates the
  container's user namespace, and the kernel then checks every fork against
  the processes of all your containers together.
- **Not raisable.** The session cannot raise the limit, because it has no
  capabilities. Its own shell and init process count against it, so slightly
  fewer than `N` processes are left for commands.
- **Availability.** The fallback applies only when the engine reports kernel
  5.14 or later (`podman info --format '{{.Host.Kernel}}'`). Older or
  unrecognized kernels may count every process of your user, so the process
  budget then stays unenforced, and the notice names the reason. The memory and
  CPU budgets have no fallback. The provider proxy's and session engine's
  process budgets use the same fallback. Which mechanism enforces each process
  budget is part of the restricted qualification identity, and each launch
  checks the created container's startup step and absence of an engine-applied
  process rlimit.

Risk: without the memory or process budget, a session can exhaust host memory
or processes for your user; without a CPU budget it can saturate every CPU.
Delegating the controllers (for example a systemd
`Delegate=cpu cpuset io memory pids` drop-in for `user@.service`) restores full
enforcement, but the sandbox never requires it.

`OPENCODE_CONTAINER_RUN_TIMEOUT` sets Podman's native container lifetime. When
it stops a session, the wrapper prints a notice and keeps the engine client's
exit status (255 on Podman 4.9.3). The notice compares whole seconds, so with a
1-second limit a fast non-zero exit can print it; the status is never altered.

The writable workspace, or the worktree parent, must not physically be `/`,
`/home`, `/root`, `/etc`, `/usr`, `/var`, `/bin`, `/sbin`, `/lib`, `/lib64`,
`/boot`, `/opt`, `/srv`, `/mnt`, `/media`, `/proc`, `/sys`, `/dev`, `/run`,
`/tmp`, the caller's physical home or a `/mnt/<letter>` drive root.
Descendants such as `/mnt/d/project` are allowed.

On a WSL drive mount, it also must not be one of these Windows folders, in any
letter case, because drvfs ignores case:

- `/mnt/<drive>/Users`;
- a profile, `/mnt/<drive>/Users/<name>`, its `Documents`, its `OneDrive`
  (also `OneDrive - <organization>`) or `OneDrive/Documents`, which hold the
  PowerShell profile and modules;
- anything inside the profile's `AppData`, which holds the startup folder;
- `/mnt/<drive>/Windows`;
- `/mnt/<drive>/Program Files` or `/mnt/<drive>/Program Files (x86)`;
- `/mnt/<drive>/ProgramData`.

Apart from `AppData`, only these exact folders are refused. A project below
them, such as `/mnt/c/Users/me/projects/app` or
`/mnt/c/Users/me/Documents/GitHub/app`, is accepted. In worktree mode, however, a
project placed directly in a profile is refused, because its parent is the
profile.

Exact `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1` permits a refused directory with
a warning; it relaxes no other check.

No session receives a host Podman socket. A session's private container engine
mounts only the workspace and the library's read-only image store, so its
containers stay inside the project-only filesystem boundary and the session's
network boundary ([Container tests](#container-tests)).

## Toolchains

Sessions can use extra toolchains, such as Java, Go or Python, without host
Podman access, an unrestricted network or a rebuilt image. The operator keeps a
toolchain library on the host. Every session sees it read-only, with `nosuid`
and `nodev`, at `/toolchains`. The library is shared by the Claude, Codex,
OpenCode, Pi and Antigravity wrappers and the reference shell. A toolchain adds
no network, IPC or privilege capability: it runs under the same restrictions as
the rest of the session.

- **Location:** `${XDG_DATA_HOME:-~/.local/share}/sandbox-toolchains`, or
  `OPENCODE_CONTAINER_TOOLCHAINS_DIR`. Unlike OpenCode state, the library
  follows the host `XDG_DATA_HOME`, so all wrappers find the same library. The
  launcher creates it private (`0700`) when it is missing. It must stay
  outside the workspace, the OpenCode state directories and the installation.
  A home directory exposed as the workspace with
  `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1` contains the default library, so
  that launch stops. Move the library with `OPENCODE_CONTAINER_TOOLCHAINS_DIR`,
  or omit it.
- **Disable:** `OPENCODE_CONTAINER_TOOLCHAINS=0` (or `false`, `no`) starts a
  session without the mount and without a session container engine.
- **Live updates:** a toolchain added or removed on the host appears in
  running sessions without a restart.

### Managing the library

The operator runs these commands on the host; `--container-toolchain` must be
the first argument:

```bash
opencode-container --container-toolchain add java21            # install or replace a catalog recipe
opencode-container --container-toolchain add ~/recipes/x.json  # install or replace an operator recipe
opencode-container --container-toolchain list                  # installed toolchains, then the catalog
opencode-container --container-toolchain remove java21
opencode-container --container-toolchain verify [java21]       # rerun the checks on the current runtime image
```

An argument without `/` that does not end in `.json` names a recipe of the
release's catalog (see [Recipes](#recipes)); any other argument is a recipe
file. `list` shows the name, version, default flag, size, requirements and
verified base of each installed toolchain, then the catalog recipes that are
not installed.

- **Sources:** a toolchain is a relocatable directory tree, assembled from one
  or more sources: a path inside an OCI image referenced by `@sha256:` digest,
  an HTTPS archive URL with its SHA-256, or a local archive with its SHA-256.
  A toolchain can also, or only, provide container images for the session
  container engine (see [Images](#images)); `list` shows them with the others,
  and `remove` deletes images no other toolchain lists, once no session engine
  runs.
- **Operator recipes:** keep them outside project directories, for example in
  `~/recipes`. A session can write its workspace and state directories, so an
  agent could have written a recipe found there: `add` refuses a recipe file
  inside the directory it runs from (its parent, when setup saved the worktree
  scope) or inside a state directory, before fetching anything. Catalog names
  are not affected, and neither are the local archives that a recipe pins by
  SHA-256.
- **Fetching:** `add` fetches what the recipe names by itself and prints each
  image and URL first. It pulls a missing image and downloads archive URLs
  without `OPENCODE_CONTAINER_MAINTENANCE`, because the content is fixed by its
  digest or SHA-256 and no code runs while it is fetched and extracted.
  Downloads use HTTPS only and follow redirects only to HTTPS. They trust the
  host CA bundle that setup saved when host CA trust is enabled, and the system
  trust otherwise, and they use the host's proxy variables. Like image builds,
  pulls and downloads happen on the host, outside runtime filtering. `add`
  never builds an image; image builds still require maintenance.
- **Extraction:** every archive is checked against its SHA-256 before anything
  is extracted, and is extracted from a private copy in the library, so a local
  archive changed afterwards cannot reach the toolchain. Extraction rejects
  absolute paths, `..`, device nodes and links that leave the toolchain, and
  clears setuid and setgid bits. A file that two sources provide fails the
  command.
- **Atomic changes:** changes take a library lock and replace directories
  atomically.
- **Check:** before accepting a toolchain, `add` runs the recipe's `check`
  command in the OpenCode runtime image, without network and with the
  session's identity and hardening (starting in `/` so no working-directory
  chown occurs). A toolchain that needs a newer C library than the image's
  glibc fails here. The manifest records the base image from the installed
  `Containerfile`.
- **After an update:** when `--container-setup` selects a new release, it
  reruns the check of every installed toolchain verified on another base,
  records the new base when the check passes, and prints any failure without
  blocking setup. Until a toolchain passes `verify` on the new base, it stays
  visible but loses its default environment, and the launcher prints one
  warning naming it. All five wrappers build from the same base, so a toolchain
  verified by another wrapper keeps its default environment here.

### Recipes

A recipe is a JSON file in the shipped release catalog (`setup/toolchain-catalog/`)
or kept and reviewed by the operator outside writable mounts:

| Key | Meaning |
| --- | --- |
| `schema`, `name`, `version` | `2` (schema `1` with single `source` still supported); `[a-z0-9][a-z0-9._-]*`; free version text |
| `sources` | ordered list of `{"image": "<ref>@sha256:<digest>", "path": "/abs/path"}`, `{"url": "https://...", "sha256": "<hex>", ...}`, or `{"archive": "/abs/file.tar.xz", "sha256": "<hex>", ...}` (with optional `strip_components`, `subpath`, `into`) |
| `images` | container images for the session container engine (see [Images](#images)) |
| `path` | directories relative to the toolchain, added to `PATH` (default `["bin"]` when `sources` are present) |
| `env` | variables: `{"toolchain": "<relative path>"}` or `{"value": "<literal>"}` |
| `requires` | other toolchains whose environment is loaded first |
| `notes` | short instructions shown to the agent in `toolchains.md` |
| `check` | command run in the runtime image before the toolchain is accepted |
| `default` | `true` adds the toolchain to new sessions' environment (`false` required for image-only recipes) |

- **Protected variables:** recipes cannot set `PATH`, `HOME`, loader, proxy
  or CA variables, any `XDG_` variable or `DBUS_SESSION_BUS_ADDRESS` (no
  session has a bus). OpenCode places its state with `XDG_CONFIG_HOME`,
  `XDG_DATA_HOME`, `XDG_CACHE_HOME` and `XDG_STATE_HOME`, so a toolchain can
  never move it. These rules are the same in every wrapper. Each wrapper also
  protects its own variables: its prefix, configuration, approval and
  credential variables, such as `OPENCODE_CONTAINER_*`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `OPENROUTER_API_KEY` and `OPENCODE_API_KEY` here, and
  the agent's own variables that its profile lists in `native.protected_env`.
  For OpenCode these are every `OPENCODE_`, `ANTHROPIC_`, `OPENAI_`,
  `OPENROUTER_` and `GEMINI_` variable, `GOOGLE_API_KEY`,
  `GOOGLE_GENERATIVE_AI_API_KEY`, the five `AWS_` Bedrock variables and
  `AZURE_RESOURCE_NAME` and `AZURE_API_KEY`. `add` rejects them. If another
  wrapper installed a toolchain that sets one, this wrapper leaves that
  variable out of its sessions and prints a warning naming the toolchain;
  the rest of the toolchain stays available.
- **Order:** toolchain variables are set before the forwarded variables and
  the protected values, so they never override them. To pass a provider
  variable on purpose, forward it from the host with
  `OPENCODE_CONTAINER_ENV_VARS`.
- **Default toolchains:** in new sessions, their `PATH` entries come **after**
  the image's. They never replace the runtime's own `node` or `python3`, which
  OpenCode and the image tools use.
- **Conflicts:** two default toolchains cannot share a command or a variable.
  Install a second version with `"default": false` and use it through its
  `env.sh`.
- **Writable locations:** `/tmp` is writable and executable, `/var/tmp` is
  writable but `noexec`, and both are discarded with the container; `/run` is
  not writable by the session user. In shared-state mode `/opencode-home` is an executable tmpfs, and
  only the four OpenCode directories below it persist. Point caches to `/tmp`
  with literal values. Recipes shared with other wrappers keep notes such as
  `GOTMPDIR` under the workspace, because `/tmp` is `noexec` in some of them.
- **Dependency downloads** (Maven, npm, pip, Cargo, Go modules) need network
  access that provider and offline modes do not grant. Provide dependencies in
  the workspace, or use an unrestricted session.

#### Images

A recipe can also list container images. Sessions started while the library
holds at least one image get a private container engine that runs them
([Container tests](#container-tests)). Each image is one of:

| Image | Form |
| --- | --- |
| Registry image | `"<ref>@sha256:<digest>"`; a reference without a digest is refused |
| Local image | `{"local": "sha256:<full image ID>", "name": "localhost/<name>[:tag]"}` |

```json
{"schema": 2, "name": "postgres16", "version": "16.4", "default": false,
 "images": ["docker.io/library/postgres@sha256:<digest>"],
 "check": ["podman", "run", "--rm", "--network=none", "docker.io/library/postgres@sha256:<digest>", "postgres", "--version"]}
```

- **Store:** `add` keeps the images in the library's image store, `.images`,
  through a helper container of the engine image (`localhost/opencode-cli-engine:latest`).
  Registry images are pulled on the host, with host CA trust when setup enabled
  it, and keep both their index and platform digests. A local image is copied
  from the host engine by its full ID (`podman image inspect --format '{{.Id}}' <image>`)
  and named as the recipe says; `add` fails if the host engine has no image with
  that ID. An image several toolchains list is stored once.
- **Image-only recipes** have no `sources`, `path` or `env`, and `default` must
  be `false`; `toolchains.md` lists their images with a `podman run` example.
- **Check:** for a recipe with images, `check` runs in the runtime image against
  a temporary engine like a session's, without network, so a check that runs
  the image proves it runs offline.
- **Live updates:** an image added while sessions run is usable by their engines
  at once. Removing an image, or replacing a toolchain with one that drops an
  image, waits until no session engine runs: the command fails and names the
  running sessions.
- **Catalog recipes** never list local images.
- **Cleanup:** image layers in `.images` can belong to your subordinate IDs, as in
  any rootless Podman storage. Remove image toolchains with `remove`, which
  deletes their layers through the helper; deleting the directory directly needs
  `podman unshare rm -rf`.

The shipped catalog recipes (`setup/toolchain-catalog/`) pin these versions and
sources:

| Name | Version | Source | Default | Notes |
| --- | --- | --- | --- | --- |
| `java21` | Temurin 21.0.13 | image `eclipse-temurin@sha256:0a3f3298…`, `/opt/java/openjdk` | yes | `JAVA_HOME` |
| `maven3.9` | 3.9.16 | image `maven@sha256:99e61abc…`, `/usr/share/maven` | yes | requires `java21`; local repository in `/tmp/m2`; harmless jansi warning |
| `go` | 1.27.4 | image `golang@sha256:4fa7c968…`, `/usr/local/go` | yes | `GOTOOLCHAIN=local`; caches in `/tmp`; `go test` needs `GOTMPDIR` in the workspace |
| `node24` | 24.22.3 | archive `node-v24.22.3-linux-x64.tar.xz` from `nodejs.org` | no | the image's Node.js 22 stays first |
| `python3.13` | 3.13.18 | python-build-standalone `20261110` `install_only` archive from GitHub | no | the image's `python3` stays first; virtual environments in the workspace |
| `rust` | 1.100.0 | `rustc`, `cargo` and `rust-std` (host and `x86_64-unknown-linux-musl`) archives from `static.rust-lang.org` | yes | target `x86_64-unknown-linux-musl` linked by `rust-lld`; crates with build scripts or procedural macros fail |

### Telling the agent

The wrapper never edits `AGENTS.md` or other instruction files. The library
contains a generated `/toolchains/toolchains.md` with the usage rules and every
installed toolchain (including image references and `podman run` examples), plus
a machine-readable `/toolchains/index.json`. Add one line to the project's
`AGENTS.md`, or to `~/.config/opencode/AGENTS.md`
(`/opencode-home/.config/opencode/AGENTS.md` in the session):

```markdown
Read /toolchains/toolchains.md before using or looking for build tools.
```

The agent then runs a toolchain in one command with
`. /toolchains/<name>/env.sh && <command>`. This form also works for
toolchains added after the session started.

SELinux and AppArmor enforcement were not tested with the library mount. On
hosts that enforce them, profile the tools you add.

## Container tests

Sessions never receive the host Podman API. When the toolchain library holds at
least one image toolchain, every session instead gets a private, rootless
Podman engine of its own (`localhost/opencode-cli-engine:latest`), in every
network mode. The engine shares the session's network namespace, so its
containers have the session's egress: an offline session's containers reach
nothing outside, and a provider session's containers reach only what the proxy
policy allows. The session reaches its engine at
`CONTAINER_HOST=tcp://127.0.0.1:2375`, also given as `DOCKER_HOST` for
Docker-API clients such as Testcontainers. The engine runs the library's images
offline by their pinned references, mounts only the workspace (at the same
path) and the library's read-only image store, holds no secrets, and is removed
with its storage when the session ends. Without images in the library, or with
`OPENCODE_CONTAINER_TOOLCHAINS=0`, there is no engine and `CONTAINER_HOST` and
`DOCKER_HOST` are absent from the session, including image or engine defaults.

```bash
opencode-container --container-toolchain add ~/recipes/postgres16.json   # see Images
opencode-container --container-shell -c 'podman run --rm --network=none docker.io/library/postgres@sha256:<digest> postgres --version'
```

- **Engine image preparation:** guided setup builds the engine image from
  `launcher/engine/Containerfile` and writes the derived seccomp profile to
  `launcher/engine/seccomp.json` in the release. For direct checkout runs,
  prepare the engine image under maintenance:
  `podman build --pull=never --tag localhost/opencode-cli-engine:latest launcher/engine`.
- **Images:** add them as toolchains ([Images](#images)). In offline and
  provider sessions the engine pulls nothing; in unrestricted sessions it can
  also pull, and pulled or built images stay in the session's storage. An image
  added during a session is usable at once; the first image needs a new
  session, because a session without library images starts without an engine.
- **Workspace:** a container that bind-mounts a path inside the workspace sees
  the workspace files, and files its root creates there belong to you. Any
  other path a nested container mounts is the engine's own file system, never
  the host's.
- **Isolation:** each nested container has its own process view and host name
  (its container ID). Two sessions have separate engines and never see each
  other's containers.
- **Lifetime:** the launcher starts the engine before OpenCode, waits until it
  answers as a rootless engine, and removes it with its storage when the
  session ends, also after a signal. A later launch removes the engine of a
  launch that was killed.
- **Budgets:** the engine gets the session's memory, CPU and process budgets,
  checked like the agent's; together the session can therefore use twice the
  agent's budget, and the launch says so. On the process rlimit fallback the
  engine's first process sets the limit before anything else, and the launch
  reads it from that process before the session starts; the engine and
  everything it runs share that one limit. Explicit `--memory` or
  `--pids-limit` limits on nested containers apply for every cgroup controller
  the engine has (see **Systemd containers and nested limits** below); a limit
  that needs a controller the engine lacks fails, and the container does not
  start.
- **Hardening exceptions:** the engine container is the one container that
  relaxes the standard policy, only as nested rootless containers and image
  operations need: `SETUID` and `SETGID` for the user-namespace helpers and
  `SYS_CHROOT` for layer extraction and builds (with no-new-privileges kept
  on), the FUSE and TUN devices, an unmasked procfs, SELinux labelling
  disabled, a seccomp profile derived from the host's default that also allows
  `sethostname` and `setdomainname`, and a startup step that delegates the
  engine's own cgroup subtree. That step is the engine's first process: it
  starts as the root of the engine's user namespace (never you) with `CHOWN` as
  well, hands the subtree to the unprivileged `podman` user, and then runs
  everything else as that user. Afterwards no engine process runs as root, and
  `CHOWN` stays only in the bounding set, where no-new-privileges keeps it
  unreachable. The engine user is mapped to you (`--userns=keep-id:uid=1000,gid=1000`),
  which needs 65535 subordinate IDs in one contiguous range. The engine image
  declares these four capabilities (`SETUID`, `SETGID`, `SYS_CHROOT` and
  `CHOWN`) in its `io.containers.capabilities` label, so Podman starts the
  engine without a capability error. A tool that needs more privilege is
  unsupported.
- **Systemd containers and nested limits:** on an eligible engine, nested
  containers get cgroups of their own, so an image that starts systemd runs it
  as PID 1:

  ```bash
  # an image toolchain whose image starts /sbin/init, such as a Rocky Linux 9 init image
  podman run --detach --name target --systemd=always docker.io/rockylinux/rockylinux@sha256:<digest>
  podman exec target timeout 120 sh -c 'until systemctl is-system-running | grep -qE "^(running|degraded)$"; do sleep 1; done'
  podman exec target systemd-run --unit=probe --property=Type=oneshot /bin/true
  ```

  An engine is eligible when its cgroup namespace is private and its cgroup v2
  root is mounted read-write with `nsdelegate` and belongs to the root of its
  user namespace. This holds for native Linux with the `systemd` cgroup manager
  and for the Windows Podman machine (`cgroupfs`); no host change is needed.
  Explicit nested limits apply for each controller the engine has: `memory` and
  `pids` where the rootless engine delegates them (native Linux with `systemd`);
  the Windows Podman machine delegates none, so explicit nested limits fail
  there and systemd resource-control unit settings (such as `MemoryMax=` or
  `TasksMax=`) have no effect. The engine's own limit files, and so the session
  budgets, stay unwritable from the engine and from nested containers. When an
  engine is ineligible (for example on a host with cgroup v1), the launch
  announces `systemd containers and explicit limits for nested containers are
  unavailable` with the reason, and the session starts without them. Systemd
  containers and cgroup delegation are untested under enforcing SELinux or
  active AppArmor profiles.
- **Host `/sys` in the session:** the session joins the engine's network
  namespace, and a rootless container that joins another namespace cannot mount
  a sysfs of its own: Podman bind-mounts the host's `/sys` read-only instead. A
  session with an engine therefore sees the host's network interfaces in
  `/sys/class/net` (names, MAC addresses, link state and counters), while its
  network namespace still has only loopback, as `/proc/net/dev` shows.

Migration: host Podman delegation (`OPENCODE_CONTAINER_PODMAN=1`, with
`OPENCODE_CONTAINER_PODMAN_SOCKET`) was removed. Exact `OPENCODE_CONTAINER_PODMAN=1`
stops every launch with migration guidance, other values are ignored, and
`--container-setup` drops saved delegation settings. Add the images your tests
need as toolchains ([Images](#images)); the next session has its engine.

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
Builds use the wrapper's physical recipe directory and pass no build arguments;
they pull the exact base first, then run with `--pull=never` and the docker
format, without a timeout.

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
owned full container IDs; stderr warnings must not become part of an ID, and
the create client's stderr is shown when create fails. Each session container
carries only the `io.opencode-container.session` label.

Stdin remains interactive for pipes/files as well as terminals; allocate a TTY
only with terminal stdin and stdout. Preserve input/EOF for the attached client.
Forward TERM/INT/HUP explicitly once and return 143/130/129. Preserve application
exit statuses, including 125, and the first interruption status despite cleanup
errors or repeated signals. A signal starts shutdown at once, also during
creation. Shutdown has one 20-second budget, including at most
five seconds of application grace, bounded engine calls, interrupted-create
reconciliation and local create/attach client termination/reaping. Repeated
signals do not renew the deadline. Only verified owned IDs authorize removal.

Unresolved creation or removal is reported with an ID/session marker for manual
engine inspection. Client cancellation does not prove engine request cancellation;
engine loss or SIGKILL can leave residual resources. Use `podman ps --all --filter
label=io.opencode-container.session` and the reported session label to inspect
them; never indiscriminately remove other managed sessions.

## Shared sandbox components and the agent profile

`network/`, `setup/`, `launcher/` and the shared tests come unchanged from the
reference repository `sandbox-container` (tag `sandbox-ref-36`) and are shared
with the Claude, Codex, Antigravity and Pi wrappers. They contain no
OpenCode-specific names. `launcher/core.sh` is the whole launcher:
`opencode-container.sh` is the thin entry script every wrapper shares, and
`agent/launcher.sh` holds the profile values the core needs, the fixed XDG bases
and restricted switches, and OpenCode's five hooks (`docs/launcher-contract.md`
in `sandbox-container`):

- `agent_validate` checks `OPENCODE_CONTAINER_PROVIDER`, the integration
  opt-ins and YOLO with a host `OPENCODE_PERMISSION` before any engine or state
  operation;
- `agent_mounts` adds the opted-in read-only `~/.agents` and `/etc/opencode`;
- `agent_environment` forwards the OpenCode native variables and, in
  unrestricted mode, the selected provider's variables;
- `agent_approval_bypass` sets `OPENCODE_PERMISSION={"*":"allow"}`;
- `agent_help` documents these variables and the provider keys.

The shared launcher tests (`tests/test_launcher.py`, with the fake engine
`tests/fake_podman.py`, plus `tests/test_engine.py`, `tests/test_toolchains.py`,
`tests/test_windows_bootstrap.py` and `tests/test_windows_enter.py`) run the
shared components against fixture agent parts; `tests/test_wrapper.py` and
`tests/test_setup_wrapper.py` cover only OpenCode's part. Every other
agent-specific value is declared in `agent/profile.json`.

## Verification

Run static checks first, then the synthetic suite (Python standard library only):

```bash
bash -n opencode-container.sh agent/launcher.sh
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
OPENCODE_CONTAINER_NETWORK=unrestricted OPENCODE_CONTAINER_MAINTENANCE=1 ./opencode-container.sh --container-build
bash tests/run-runtime.sh                  # unrestricted runtime suite
bash tests/run-runtime.sh --wrapper        # shared launcher and OpenCode wrapper tests (fake engine)
bash tests/run-runtime.sh --shared         # shared suites copied from sandbox-container
bash tests/run-runtime.sh --setup          # shared setup suite
bash tests/run-runtime.sh --setup-runtime  # guided setup with real rootless Podman
bash tests/run-runtime.sh --network        # restricted modes with real rootless Podman
bash tests/run-runtime.sh --guard          # guard runtime fixtures (needs the toolchain image)
```

Further modes: `--qualification`, `--network-feasibility`, `--network-policy`,
`--mux` and `--guard-idle` (the 305-second idle check).

The real suite exercises mount flags/capacities/lifetime, identity, state,
context filtering, concurrency, signals, stdin, worktrees, the private session
container engine, leftover delegation refusal, version output, the YOLO permission, the session label, read-only state,
effective capabilities and cgroup/rlimit budgets, process-limit enforcement, the
lifetime limit, the refused home workspace, shared and isolated state, the tool
inventory, and actual OpenTUI startup/quit through a PTY.
The renderer uses a disposable home with no provider credentials. Its ignored
`.test-state/renderer-last.txt` transcript is available for local inspection.
Synthetic and runtime results are recorded separately in
[the validation record](docs/validation.md). Version output alone does
not initialize OpenTUI and cannot establish renderer compatibility.

Inspect remaining containers with `podman ps --all --filter
label=io.opencode-container.session`; other users' active sessions must
remain intact.
