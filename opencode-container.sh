#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: opencode-container.sh [container options] [OpenCode arguments...]

Container options:
  --container-setup      interactively prepare a complete user installation and
                         its managed launcher; must be used alone
  --container-qualify    verify a prepared restricted installation with fixed
                         local controls; must be used alone
  --container-build      build or refresh the container image before starting
                         (requires OPENCODE_CONTAINER_MAINTENANCE=1)
  --container-shell      open Bash instead of starting OpenCode (OpenCode
                         arguments are omitted)
  --container-git-worktree mount the parent of the current physical directory
                         read/write; the container starts in the current directory
  --container-help       show this wrapper help without engine or state changes

All other arguments, including --help, are passed to OpenCode unchanged.
TERM/INT/HUP are forwarded once to the owned session; interruption exits are
143/130/129. Shutdown has one 20-second budget, including five seconds of
application grace. Only this invocation's verified container is removed;
SIGKILL or engine loss can leave residual containers requiring inspection.

Environment:
  OPENCODE_CONTAINER_NETWORK  offline, provider, or unrestricted; required for
                         every launch (unrestricted is the previous behavior)
  OPENCODE_CONTAINER_NETWORK_PROFILE protected provider policy profile name
                         (anthropic-api, openai-api, openrouter-api or opencode-zen)
  OPENCODE_CONTAINER_NETWORK_POLICY absolute operator policy JSON path
  OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR private native directory at its host path
  OPENCODE_CONTAINER_EGRESS_IMAGE immutable proxy image ID or registry digest
  OPENCODE_CONTAINER_MAINTENANCE authorize image builds and proxy pulls only with
                         exact value 1, including the build of a missing image
  OPENCODE_CONTAINER_IMAGE    image name (default: localhost/opencode-cli:latest);
                         OpenCode and OpenSpec versions are pinned in Containerfile
  OPENCODE_CONTAINER_STATE_DIR private host directory used as the persistent
                         /opencode-home (default: unset or empty; the shared OpenCode
                         directories ~/.config/opencode, ~/.local/share/opencode,
                         ~/.cache/opencode and ~/.local/state/opencode are
                         mounted below an ephemeral home; host XDG_*_HOME
                         variables do not relocate them)
  OPENCODE_CONTAINER_CONFIG_DIR private host directory replacing only the shared
                         configuration directory; conflicts with
                         OPENCODE_CONTAINER_STATE_DIR
  OPENCODE_CONTAINER_TRUST_HOST_CA trust a host CA bundle: 1, true, or yes
                         (default: disabled)
  OPENCODE_CONTAINER_CA_BUNDLE CA bundle file to trust (default: first of
                         /etc/ssl/certs/ca-certificates.crt and
                         /etc/pki/tls/certs/ca-bundle.crt)
  OPENCODE_CONTAINER_PODMAN   expose the host Podman socket only when exactly 1
                         (default: disabled; other values also disable access);
                         rejected in offline and provider modes
  OPENCODE_CONTAINER_PODMAN_SOCKET absolute socket override for enabled access
                         (then Unix CONTAINER_HOST, then XDG_RUNTIME_DIR or
                         /run/user/<uid>, with /podman/podman.sock appended)
  OPENCODE_CONTAINER_YOLO     auto-approve every OpenCode permission request,
                         including configured ask/deny rules (default: disabled)
                         1/true/yes enable; empty/0/false/no disable
                         words are case-insensitive; other values are errors
  OPENCODE_CONTAINER_PROVIDER forward one provider's variables by name:
                         anthropic, openai, google, openrouter,
                         amazon-bedrock, azure, opencode or none
                         (default: none; stored `opencode auth login`
                         credentials work without it); in provider mode the
                         network profile selects the only forwarded key and
                         this value must be unset, none or the matching provider;
                         offline mode forwards no provider variable
  OPENCODE_CONTAINER_ENV_VARS space-separated extra variable names to forward
                         by name, e.g. "GH_TOKEN" (default: none)
  OPENCODE_CONTAINER_AGENTS_DIR exactly 1 mounts ~/.agents read-only
                         (default: not mounted)
  OPENCODE_CONTAINER_SYSTEM_CONFIG exactly 1 mounts /etc/opencode read-only
                         (default: not mounted)
  OPENCODE_CONTAINER_MEMORY_LIMIT session memory, integer with k/m/g unit (default: 4g)
  OPENCODE_CONTAINER_CPU_LIMIT    session CPUs, up to 3 decimals (default: 2)
  OPENCODE_CONTAINER_PIDS_LIMIT   session process limit (default: 512)
                         Budgets cannot be disabled; they require delegated
                         rootless cgroup v2 cpu/memory/pids controllers
  OPENCODE_CONTAINER_RUN_TIMEOUT  session container lifetime in whole seconds
                         (default: 0, disabled by default)
  OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE exact 1 permits a refused sensitive
                         workspace with a warning (default: disabled)

Values are forwarded by name and never placed in engine arguments.
~/.claude is never mounted. GitHub tokens are never forwarded by default.
Socket access permits new host mounts beyond the workspace with the service
user's authority. YOLO and socket access are independent. Every session drops
all capabilities and sets no-new-privileges; no security-policy overrides are
added. Budgets and tmpfs sizes do not limit workspace or state storage growth.
When the lifetime limit stops a session, a notice is printed and the engine
client's exit status is kept.
The writable workspace (or worktree parent) must not physically be /, /home,
/root, /etc, /usr, /var, /bin, /sbin, /lib, /lib64, /boot, /opt, /srv, /mnt,
/media, /proc, /sys, /dev, /run, /tmp, the caller's home or a /mnt/<letter>
drive root; descendants such as /mnt/d/project are allowed.
Worktree mode exposes the entire parent beyond the workspace.
Linux rootless Podman and host GNU coreutils timeout are required.
opencode-wrapper is a deprecated alias of this script.

New users must first run: bash ./opencode-container.sh --container-setup
Then use the managed launch command printed by setup (by default
~/.local/bin/opencode-container) from your workspace. An ordinary launch with an
unset or empty OPENCODE_CONTAINER_NETWORK stops with setup guidance before
runtime checks or state creation.

Direct operator launches remain available with an explicit mode.
Migration: every direct launch needs an explicit OPENCODE_CONTAINER_NETWORK. Set
OPENCODE_CONTAINER_NETWORK=unrestricted to keep the previous networking
behavior, and add OPENCODE_CONTAINER_MAINTENANCE=1 to commands that build the
image, e.g.:
  OPENCODE_CONTAINER_NETWORK=unrestricted OPENCODE_CONTAINER_MAINTENANCE=1 bash ./opencode-container.sh --container-build
Shared state now uses the fixed paths above; move OpenCode directories kept
under a custom XDG_*_HOME, or use OPENCODE_CONTAINER_CONFIG_DIR or
OPENCODE_CONTAINER_STATE_DIR. Offline sessions cannot reach any model provider.
Restricted failures never retry unrestricted networking.

Restricted modes (offline, provider) require host Python 3, a same-host Unix
rootless Netavark service with Podman >= 4.9, standard OCI seccomp, usable
Landlock ABI >= 3, a protected installation outside writable workspace/state
trees, a static guard and SHA-256 manifest in network/bin, and a current local
qualification report (run --container-qualify alone after preparation or
relevant updates). Changed boot, engine/backend/security, code/images,
policy/profile, CA trust or hardening invalidates the report; an unidentifiable
active LSM policy requires the gate on each launch. Locally-qualified
installations are distinguished from release-measured acceptance records.
Restricted sessions do not receive host proxy or CA variables; the relay sets
the proxy and NO_PROXY=localhost,127.0.0.1,::1 keeps the local OpenCode server
reachable. Named Unix sockets, host services and LSP downloads are unavailable.
Provider mode uses an external CONNECT proxy that binds the TLS server name
(initial and retried ClientHello) to the CONNECT host before forwarding; it
does not prove exclusive communication with your provider account. Allowed
services can receive data: an injected agent can send workspace data to an
allowed host (anthropic-api: api.anthropic.com; openai-api: api.openai.com;
openrouter-api: openrouter.ai; opencode-zen: opencode.ai) with an attacker's
key or account. Only offline removes this. Provider-hosted tools such as web
search run at the provider, outside this boundary. Restricted sessions set
OPENCODE_DISABLE_AUTOUPDATE, _DEFAULT_PLUGINS, _LSP_DOWNLOAD, _MODELS_FETCH and
_SHARE to 1 after forwarding; writable configuration cannot re-enable them.
Browser-callback logins are unsupported; use API keys. See network/README.md
and docs/network-contract.md.
EOF
}

die() { printf 'opencode-container: %s\n' "$*" >&2; exit 1; }

# Help takes precedence regardless of option order and never needs Podman.
for arg in "$@"; do
    [[ "$arg" != --container-help ]] || { usage; exit 0; }
done
for arg in "$@"; do
    if [[ "$arg" == --container-qualify ]]; then
        [[ $# == 1 ]] || die '--container-qualify must be used alone'
        command -v python3 >/dev/null || die 'host Python 3 is required for qualification'
        qualify_dir=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
        exec python3 -I "$qualify_dir/network/qualify.py" qualify
    fi
done

for arg in "$@"; do
    if [[ "$arg" == --container-setup ]]; then
        [[ $# == 1 ]] || die '--container-setup must be used alone'
        [[ -t 0 && -t 1 ]] || die '--container-setup requires an interactive terminal'
        command -v python3 >/dev/null || die 'host Python 3 is required for interactive setup'
        setup_script=$(readlink -f -- "${BASH_SOURCE[0]}")
        exec python3 -I "$(dirname -- "$setup_script")/setup/setup.py"
    fi
done

build_image=0
qualification_probe=0
shell_mode=0
git_worktree=0
agent_args=()
for arg in "$@"; do
    case "$arg" in
        --container-qualify-probe)
            [[ $# == 1 ]] || die 'the fixed qualification probe must be used alone'
            qualification_probe=1 ;;
        --container-build) build_image=1 ;;
        --container-shell) shell_mode=1 ;;
        --container-git-worktree) git_worktree=1 ;;
        *) agent_args+=("$arg") ;;
    esac
done

# An explicit or managed mode precedes every other check, engine query and
# state operation. Files in the current directory never supply it.
if [[ -z "${OPENCODE_CONTAINER_NETWORK:-}" ]]; then
    setup_wrapper=${BASH_SOURCE[0]}
    [[ "$setup_wrapper" == /* ]] || setup_wrapper="$PWD/$setup_wrapper"
    printf -v setup_command 'bash %q --container-setup' "$setup_wrapper"
    die "setup required: run $setup_command; use the managed launcher afterward or explicitly set OPENCODE_CONTAINER_NETWORK for an operator workflow (offline, provider, or unrestricted; unrestricted keeps the previous networking behavior)"
fi
network_mode=$OPENCODE_CONTAINER_NETWORK
case "$network_mode" in
    offline|provider|unrestricted) ;;
    *) die 'OPENCODE_CONTAINER_NETWORK must be offline, provider, or unrestricted' ;;
esac
restricted=0
[[ "$network_mode" == unrestricted ]] || restricted=1
if ((restricted)) && [[ "${OPENCODE_CONTAINER_PODMAN:-}" == 1 ]]; then
    die 'restricted networking rejects OPENCODE_CONTAINER_PODMAN=1: the host API bypasses egress enforcement; select explicit unrestricted mode for delegation'
fi
if [[ "$network_mode" == provider ]]; then
    [[ -n "${OPENCODE_CONTAINER_NETWORK_PROFILE:-}" && -n "${OPENCODE_CONTAINER_NETWORK_POLICY:-}" ]] \
        || die 'provider mode requires OPENCODE_CONTAINER_NETWORK_PROFILE and OPENCODE_CONTAINER_NETWORK_POLICY'
    [[ -n "${OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR:-}" && -n "${OPENCODE_CONTAINER_EGRESS_IMAGE:-}" ]] \
        || die 'provider mode requires a private host-path OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR and immutable OPENCODE_CONTAINER_EGRESS_IMAGE'
fi
trust_host_ca=0
case "${OPENCODE_CONTAINER_TRUST_HOST_CA:-}" in
    [Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|1) trust_host_ca=1 ;;
    ''|0|[Ff][Aa][Ll][Ss][Ee]|[Nn][Oo]) ;;
    *) die 'OPENCODE_CONTAINER_TRUST_HOST_CA must be 0, 1, true, false, yes, or no' ;;
esac
config_override=${OPENCODE_CONTAINER_CONFIG_DIR:-}
if [[ -n "$config_override" ]]; then
    [[ -z "${OPENCODE_CONTAINER_STATE_DIR:-}" ]] \
        || die 'OPENCODE_CONTAINER_STATE_DIR conflicts with OPENCODE_CONTAINER_CONFIG_DIR; unset OPENCODE_CONTAINER_CONFIG_DIR to isolate state, or unset OPENCODE_CONTAINER_STATE_DIR to keep shared state'
    [[ "$config_override" == /* && "$config_override" != *:* && "$config_override" != *$'\n'* && "$config_override" != *$'\r'* ]] \
        || die "OPENCODE_CONTAINER_CONFIG_DIR must be an absolute path without colon, CR or LF: $config_override"
fi

SCRIPT_PATH=$(readlink -f -- "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(dirname -- "$SCRIPT_PATH")
readonly SCRIPT_PATH SCRIPT_DIR

# Wrapper settings are validated before any engine query or state creation.
yolo=0
yolo_value=${OPENCODE_CONTAINER_YOLO:-}
case "${yolo_value,,}" in
    1|true|yes) yolo=1 ;;
    ''|0|false|no) ;;
    *) die 'OPENCODE_CONTAINER_YOLO must be 0, 1, true, false, yes, or no' ;;
esac
if ((yolo)) && [[ -n "${OPENCODE_PERMISSION:-}" ]]; then
    die 'OPENCODE_CONTAINER_YOLO cannot be combined with OPENCODE_PERMISSION; unset one of them'
fi
# The OpenCode version is pinned in Containerfile; version variables are ignored.
for variable_name in OPENCODE_CONTAINER_VERSION OPENCODE_VERSION; do
    if [[ -n "${!variable_name+x}" ]]; then
        printf 'opencode-container: %s is ignored; the OpenCode version is pinned in Containerfile\n' "$variable_name" >&2
    fi
done
image_override=${OPENCODE_CONTAINER_IMAGE:-}
[[ "$image_override" != *[[:space:][:cntrl:]]* ]] \
    || die 'OPENCODE_CONTAINER_IMAGE must not contain whitespace or control characters'

# Exposure controls are validated before any engine query or state creation.
readonly AUTHORITATIVE_NAMES=' HOME USER XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME OPENCODE_CONTAINER_CONFIG_DIR CONTAINER_HOST CONTAINER_CONNECTION '
readonly ALL_PROFILE_NAMES='ANTHROPIC_API_KEY OPENAI_API_KEY OPENAI_BASE_URL GOOGLE_API_KEY GOOGLE_GENERATIVE_AI_API_KEY GEMINI_API_KEY OPENROUTER_API_KEY AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_REGION AWS_BEARER_TOKEN_BEDROCK AZURE_RESOURCE_NAME AZURE_API_KEY OPENCODE_API_KEY'
provider_selected=0
provider_names=()
if [[ -n "${OPENCODE_CONTAINER_PROVIDER+x}" ]]; then
    provider_selected=1
    # Variable sets follow the provider metadata of the pinned OpenCode 1.18.3.
    case "$OPENCODE_CONTAINER_PROVIDER" in
        anthropic) provider_names=(ANTHROPIC_API_KEY) ;;
        openai) provider_names=(OPENAI_API_KEY OPENAI_BASE_URL) ;;
        google) provider_names=(GOOGLE_API_KEY GOOGLE_GENERATIVE_AI_API_KEY GEMINI_API_KEY) ;;
        openrouter) provider_names=(OPENROUTER_API_KEY) ;;
        amazon-bedrock) provider_names=(AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_REGION AWS_BEARER_TOKEN_BEDROCK) ;;
        azure) provider_names=(AZURE_RESOURCE_NAME AZURE_API_KEY) ;;
        opencode) provider_names=(OPENCODE_API_KEY) ;;
        none) ;;
        *) die 'OPENCODE_CONTAINER_PROVIDER must be one of: anthropic, openai, google, openrouter, amazon-bedrock, azure, opencode, none' ;;
    esac
fi
# Restricted sessions forward no provider variable except the credential of the
# selected network profile (mirrors the auth methods in agent/profile.json).
if ((restricted)); then
    profile_provider=''
    profile_credential=''
    if [[ "$network_mode" == provider ]]; then
        case "$OPENCODE_CONTAINER_NETWORK_PROFILE" in
            anthropic-api) profile_provider=anthropic profile_credential=ANTHROPIC_API_KEY ;;
            openai-api) profile_provider=openai profile_credential=OPENAI_API_KEY ;;
            openrouter-api) profile_provider=openrouter profile_credential=OPENROUTER_API_KEY ;;
            opencode-zen) profile_provider=opencode profile_credential=OPENCODE_API_KEY ;;
        esac
        if ((provider_selected)) && [[ "$OPENCODE_CONTAINER_PROVIDER" != none \
            && "$OPENCODE_CONTAINER_PROVIDER" != "$profile_provider" ]]; then
            die "OPENCODE_CONTAINER_PROVIDER=$OPENCODE_CONTAINER_PROVIDER does not match OPENCODE_CONTAINER_NETWORK_PROFILE=$OPENCODE_CONTAINER_NETWORK_PROFILE; unset it or select the matching provider"
        fi
    fi
    provider_names=()
    [[ -z "$profile_credential" ]] || provider_names=("$profile_credential")
fi
# Restricted modes own the proxy, CA and optional-traffic settings.
readonly PROXY_NAMES='HTTP_PROXY HTTPS_PROXY ALL_PROXY NO_PROXY http_proxy https_proxy all_proxy no_proxy'
readonly CA_NAMES='SSL_CERT_FILE REQUESTS_CA_BUNDLE CURL_CA_BUNDLE NODE_EXTRA_CA_CERTS'
readonly PROTECTED_FLAGS='OPENCODE_DISABLE_AUTOUPDATE OPENCODE_DISABLE_DEFAULT_PLUGINS OPENCODE_DISABLE_LSP_DOWNLOAD OPENCODE_DISABLE_MODELS_FETCH OPENCODE_DISABLE_SHARE'
reserved_names=$AUTHORITATIVE_NAMES
((restricted == 0)) || reserved_names+="$PROXY_NAMES $CA_NAMES $PROTECTED_FLAGS "
extra_names=()
read -r -a requested_extra_names <<< "${OPENCODE_CONTAINER_ENV_VARS:-}"
for variable_name in "${requested_extra_names[@]}"; do
    [[ "$variable_name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] \
        || die "OPENCODE_CONTAINER_ENV_VARS contains an invalid variable name: $variable_name"
    if [[ "$reserved_names" == *" $variable_name "* ]]; then
        printf 'opencode-container: OPENCODE_CONTAINER_ENV_VARS: skipping %s, which the wrapper sets itself\n' "$variable_name" >&2
        continue
    fi
    extra_names+=("$variable_name")
done
integration_sources=()
integration_destinations=()
opt_in_integration() {
    local variable=$1 path=$2 destination=$3 source
    [[ "${!variable:-}" == 1 ]] || return 0
    [[ "$path" == /* ]] || die "$variable requires an absolute path: $path"
    [[ -d "$path" ]] || die "$variable=1 but the directory does not exist: $path"
    source=$(cd -- "$path" && pwd -P) || die "$variable: cannot resolve $path"
    integration_sources+=("$source")
    integration_destinations+=("$destination")
}
opt_in_integration OPENCODE_CONTAINER_AGENTS_DIR "${HOME:-}/.agents" /opencode-home/.agents
opt_in_integration OPENCODE_CONTAINER_SYSTEM_CONFIG /etc/opencode /etc/opencode
if ((provider_selected == 0 && restricted == 0)); then
    unforwarded=()
    for variable_name in $ALL_PROFILE_NAMES AZURE_OPENAI_API_KEY AZURE_OPENAI_ENDPOINT GH_TOKEN GITHUB_TOKEN; do
        [[ -n "${!variable_name:-}" ]] || continue
        [[ " ${extra_names[*]} " != *" $variable_name "* ]] || continue
        unforwarded+=("$variable_name")
    done
    if ((${#unforwarded[@]})); then
        printf 'opencode-container: not forwarding %s; set OPENCODE_CONTAINER_PROVIDER=<provider> or list names in OPENCODE_CONTAINER_ENV_VARS (OPENCODE_CONTAINER_PROVIDER=none silences this notice)\n' "${unforwarded[*]}" >&2
    fi
fi
USER_NAME="$(id -un)"
readonly USER_NAME
USER_ID="$(id -u)"
readonly USER_ID
GROUP_ID="$(id -g)"
readonly GROUP_ID
WORKSPACE="$(pwd -P)"
readonly WORKSPACE
WORKSPACE_NAME="$(basename -- "${WORKSPACE}")"
readonly WORKSPACE_NAME
readonly RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/${USER_ID}}"
readonly PODMAN_SOCKET="${RUNTIME_DIR}/podman/podman.sock"
IMAGE=${image_override:-localhost/opencode-cli:latest}
readonly IMAGE
readonly CONTAINER_HOME=/opencode-home

# Session budgets and lifetime, validated before any engine or state operation.
# Same rules and messages as the claude-container reference (sandbox-ref-2).
# Only an unset budget selects its default; no value disables a budget.
memory_text=${OPENCODE_CONTAINER_MEMORY_LIMIT-4g}
cpu_text=${OPENCODE_CONTAINER_CPU_LIMIT-2}
pids_text=${OPENCODE_CONTAINER_PIDS_LIMIT-512}
timeout_text=${OPENCODE_CONTAINER_RUN_TIMEOUT:-0}
memory_bytes=0
if [[ "$memory_text" =~ ^([1-9][0-9]{0,15})([kmgKMG])$ ]]; then
    case "${BASH_REMATCH[2],,}" in
        k) unit=1024 ;;
        m) unit=1048576 ;;
        *) unit=1073741824 ;;
    esac
    ((10#${BASH_REMATCH[1]} > (1 << 50) / unit)) || memory_bytes=$((10#${BASH_REMATCH[1]} * unit))
fi
((memory_bytes > 0)) || die 'OPENCODE_CONTAINER_MEMORY_LIMIT must be a positive integer with unit k, m or g, for example 4g'
cpu_nano=0
if [[ "$cpu_text" =~ ^([0-9]{1,4})(\.([0-9]{1,3}))?$ ]]; then
    fraction=${BASH_REMATCH[3]}000
    cpu_nano=$((10#${BASH_REMATCH[1]} * 1000000000 + 10#${fraction:0:3} * 1000000))
    ((cpu_nano <= 1024000000000)) || cpu_nano=0
fi
((cpu_nano > 0)) || die 'OPENCODE_CONTAINER_CPU_LIMIT must be a positive number of CPUs with at most 3 decimals, for example 2 or 1.5'
# shellcheck disable=SC2015 # die must run when either test fails.
[[ "$pids_text" =~ ^(0|[1-9][0-9]{0,9})$ ]] && ((pids_text > 0 && pids_text <= 4194304)) \
    || die 'OPENCODE_CONTAINER_PIDS_LIMIT must be a positive integer process count up to 4194304'
# shellcheck disable=SC2015 # die must run when either test fails.
[[ "$timeout_text" =~ ^(0|[1-9][0-9]{0,9})$ ]] && ((timeout_text <= 2147483647)) \
    || die 'OPENCODE_CONTAINER_RUN_TIMEOUT must be whole seconds; 0 disables the lifetime limit'
pids_limit=$((10#$pids_text))
run_timeout=$((10#$timeout_text))

# Refuse sensitive writable workspaces before any engine or state operation.
[[ "${HOME:-}" == /* ]] || die 'HOME must be absolute'
workspace_mount=$WORKSPACE
((git_worktree == 0)) || workspace_mount=$(dirname -- "$WORKSPACE")
# A missing home cannot be a workspace, so its lexical path is sufficient then.
physical_home=$(cd -- "$HOME" 2>/dev/null && pwd -P) || physical_home=$HOME
unsafe_workspace=0
case "$workspace_mount" in
    /|/home|/root|/etc|/usr|/var|/bin|/sbin|/lib|/lib64|/boot|/opt|/srv|/mnt|/media|/proc|/sys|/dev|/run|/tmp)
        unsafe_workspace=1 ;;
esac
[[ "$workspace_mount" != "$physical_home" && ! "$workspace_mount" =~ ^/mnt/[A-Za-z]$ ]] || unsafe_workspace=1
if ((unsafe_workspace)); then
    [[ "${OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE:-}" == 1 ]] \
        || die "refusing sensitive workspace $workspace_mount; launch from a project subdirectory or set exact OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1"
    printf 'opencode-container: WARNING: sensitive workspace explicitly exposed read/write: %s\n' "$workspace_mount" >&2
fi

# Validate a private state directory with the same rules as the shared state.
check_private_dir() {
    local label=$1 path=$2 resolved owner mode
    [[ -d "$path" ]] || die "$label is not a directory: $path"
    resolved=$(cd -- "$path" && pwd -P) || die "cannot resolve $label: $path"
    [[ -r "$resolved" && -w "$resolved" && -x "$resolved" ]] || die "$label is not accessible: $path"
    owner=$(stat -c '%u' -- "$resolved") || die "cannot inspect $label owner: $path"
    mode=$(stat -c '%a' -- "$resolved") || die "cannot inspect $label mode: $path"
    [[ "$owner" == "$USER_ID" ]] || die "$label must belong to caller: $path"
    [[ "$mode" =~ ^[0-7]{3,4}$ ]] || die "invalid $label mode: $path"
    (( (8#$mode & 077) == 0 )) || die "$label must be private: $path; correct permissions manually or choose native Linux storage"
    printf '%s' "$resolved"
}
state_home=''
state_request=''
# An empty value selects shared state, like an unset one (as in the other wrappers).
if [[ -n "${OPENCODE_CONTAINER_STATE_DIR:-}" ]]; then
    state_request=$OPENCODE_CONTAINER_STATE_DIR
    [[ "$state_request" == /* && "$state_request" != *:* && "$state_request" != *$'\n'* && "$state_request" != *$'\r'* ]] \
        || die "OPENCODE_CONTAINER_STATE_DIR must be an absolute path without colon, CR or LF: $state_request"
    # Compare physical paths; a missing directory is resolved through its parent.
    state_parent=$(dirname -- "$state_request")
    state_physical=$state_request
    if [[ -d "$state_parent" ]]; then
        state_physical=$(cd -- "$state_parent" && pwd -P)/$(basename -- "$state_request")
        [[ ! -e "$state_request" ]] || state_physical=$(cd -- "$state_request" 2>/dev/null && pwd -P) || state_physical=$state_request
    fi
    state_physical=${state_physical%/}
    [[ "$state_physical/" != "$workspace_mount/"* && "$workspace_mount/" != "$state_physical/"* ]] \
        || die "OPENCODE_CONTAINER_STATE_DIR must not overlap the workspace: $state_request"
fi

if ! command -v podman >/dev/null 2>&1; then
    printf 'error: podman is required to run the OpenCode sandbox\n' >&2
    exit 127
fi

command -v timeout >/dev/null && [[ $(timeout --version) == *'GNU coreutils'* ]] \
    || die 'host GNU coreutils timeout is required'

# Preserve all output bytes representable in Bash, including trailing records,
# without replacing a failed query status with the sentinel printf status.
capture_response() {
    local destination=$1 captured query_status
    shift
    if captured=$("$@"; query_status=$?; printf '\034'; exit "$query_status"); then
        printf -v "$destination" '%s' "${captured%$'\034'}"
    else
        return "$?"
    fi
}
[[ -z "${CONTAINER_CONNECTION:-}" ]] || die 'named Podman connections are unsupported'
case "${CONTAINER_HOST:-}" in
    '') ;;
    unix://*)
        launch_socket=${CONTAINER_HOST#unix://}
        [[ "$launch_socket" == /* && -n "${launch_socket//\//}" ]] \
            || die 'CONTAINER_HOST requires an absolute Unix socket pathname beyond slashes'
        ;;
    *) die 'use local Podman or an explicit same-host Unix CONTAINER_HOST; TCP/SSH is unsupported' ;;
esac
capture_response engine_response podman info --format '{{.Host.Security.Rootless}} {{.Host.OS}} {{.Host.ServiceIsRemote}}' \
    || die 'cannot query Podman or invalid engine response; check local rootless Podman or the same-host Unix service'
engine_response=${engine_response%$'\n'}
[[ "$engine_response" != *$'\n'* && "$engine_response" != *$'\r'* ]] || die 'invalid launch engine records'
launch_pattern='^[[:blank:]]*true[[:blank:]]+linux[[:blank:]]+(true|false)[[:blank:]]*$'
[[ "$engine_response" =~ $launch_pattern ]] || die 'a complete Linux rootless engine response is required'
service_remote=${BASH_REMATCH[1]}
runtime_info=$engine_response
[[ "$service_remote" == false || "${CONTAINER_HOST:-}" == unix:///* ]] \
    || die 'remote launch engine requires explicit same-host Unix CONTAINER_HOST'
if ((restricted)); then
    command -v python3 >/dev/null || die 'host Python 3 is required for restricted network policy validation'
    [[ "$service_remote" == true ]] \
        || die 'restricted networking currently requires the tested same-host Unix service; local-engine enforcement is unverified'
    capture_response network_backend podman info --format '{{.Host.NetworkBackend}}' \
        || die 'cannot verify restricted network backend'
    network_backend=${network_backend%$'\n'}
    capture_response network_version podman version --format '{{.Server.Version}}' \
        || die 'cannot verify restricted network server version'
    network_version=${network_version%$'\n'}
    capture_response network_platform podman info --format '{{json .Host}}' \
        || die 'cannot verify restricted platform security policy'
    network_platform=${network_platform%$'\n'}
elif ((qualification_probe)); then
    die 'qualification probes require restricted networking'
fi

delegate=0
if [[ "${OPENCODE_CONTAINER_PODMAN:-}" == 1 ]]; then
    delegate=1
    socket=${OPENCODE_CONTAINER_PODMAN_SOCKET:-}
    if [[ -z "$socket" && "${CONTAINER_HOST:-}" == unix:///* ]]; then
        socket=${CONTAINER_HOST#unix://}
    fi
    socket=${socket:-$PODMAN_SOCKET}
    [[ "$socket" == /* && -n "${socket//\//}" ]] || die 'Podman socket override must be absolute'
    socket=$(readlink -f -- "$socket") || die 'cannot resolve selected Podman socket'
    [[ -S "$socket" && -r "$socket" && -w "$socket" ]] \
        || die "Podman socket inaccessible: $socket; manually run systemctl --user start podman.socket or podman system service --time=0; check permissions and SELinux policy"
    capture_response socket_response podman --remote --url "unix://$socket" info \
        --format '{{.Host.Security.Rootless}}{{"\n"}}{{.Host.RemoteSocket.Path}}' \
        || die 'cannot query selected Podman socket; check service, permissions and SELinux policy'
    socket_response=${socket_response%$'\n'}
    [[ "$socket_response" != *$'\r'* && "$socket_response" == true$'\n'/* ]] \
        || die 'invalid rootless socket response'
    host_socket=${socket_response#*$'\n'}
    [[ "$host_socket" != *$'\n'* && -n "${host_socket//\//}" ]] \
        || die 'socket must report one absolute host pathname beyond slashes'
fi

sanitize_name() {
    local value="$1"
    value="${value//[^a-zA-Z0-9_.-]/-}"
    while [[ "$value" == [-._]* ]]; do value=${value:1}; done
    while [[ "$value" == *[-._] ]]; do value=${value:0:-1}; done
    value="${value:-workspace}"
    printf '%s' "${value}"
}

NAME_PREFIX="$(sanitize_name "${WORKSPACE_NAME}")"
readonly NAME_PREFIX

# Validate all paths and mount destinations before state-dependent engine calls.
valid_bind_path() {
    [[ "$1" == /* && "$1" != *:* && "$1" != *$'\n'* && "$1" != *$'\r'* ]] \
        || die "bind paths must be absolute and contain no colon, CR or LF: $1"
}
mount_args=()
mount_sources=()
mount_destinations=()
mount_modes=()
add_bind() {
    local source=$1 destination=$2 access=$3 index previous
    valid_bind_path "$source"
    valid_bind_path "$destination"
    # A bind may live below an ephemeral mount, but must never shadow it.
    for previous in /tmp /var/tmp /run "$CONTAINER_HOME"; do
        [[ "$previous/" != "$destination/"* ]] || die "bind shadows temporary storage: $destination"
    done
    for index in "${!mount_destinations[@]}"; do
        previous=${mount_destinations[index]}
        if [[ "$previous" == "$destination" && "${mount_sources[index]}" == "$source" && "${mount_modes[index]}" == "$access" ]]; then
            return
        fi
        [[ "$previous/" != "$destination/"* && "$destination/" != "$previous/"* ]] \
            || die "conflicting mount destinations: $previous and $destination"
    done
    mount_sources+=("$source")
    mount_destinations+=("$destination")
    mount_modes+=("$access")
    mount_args+=(--volume "$source:$destination:$access")
}
add_bind "$workspace_mount" "$workspace_mount" rw
# The container home is dedicated; OpenCode state lives at fixed XDG paths below it.
home_args=()
xdg_args=(
    --env "XDG_CONFIG_HOME=$CONTAINER_HOME/.config"
    --env "XDG_DATA_HOME=$CONTAINER_HOME/.local/share"
    --env "XDG_CACHE_HOME=$CONTAINER_HOME/.cache"
    --env "XDG_STATE_HOME=$CONTAINER_HOME/.local/state"
    # The profile's configuration variable names the effective directory in the
    # session, as CODEX_HOME does for Codex; the host value is never forwarded.
    --env "OPENCODE_CONTAINER_CONFIG_DIR=$CONTAINER_HOME/.config/opencode"
)
# State is created and validated after engine verification, as in the reference
# order; only lexical checks precede the engine.
if [[ -n "${OPENCODE_CONTAINER_STATE_DIR:-}" ]]; then
    if [[ ! -e "$state_request" && ! -L "$state_request" ]]; then
        (umask 077; mkdir -p -- "$state_request") || die "cannot create OPENCODE_CONTAINER_STATE_DIR: $state_request"
    fi
    state_home=$(check_private_dir OPENCODE_CONTAINER_STATE_DIR "$state_request") || exit 1
    for relative in .config/opencode .local/share/opencode .cache/opencode .local/state/opencode; do
        (umask 077; mkdir -p -- "$state_home/$relative") || die "cannot create private state: $state_home/$relative"
    done
fi

# Shared state uses fixed host paths below HOME (host XDG_*_HOME variables do
# not relocate it); only the configuration directory has an override.
writable_state=()
shared_state() {
    local relative=$1 path=$2 resolved
    if [[ ! -e "$path" && ! -L "$path" ]]; then
        (umask 077; mkdir -p -- "$path") || die "cannot create private state: $path"
    fi
    resolved=$(check_private_dir state "$path") || exit 1
    add_bind "$resolved" "$CONTAINER_HOME/$relative" rw
    writable_state+=("$resolved")
}
if [[ -n "$state_home" ]]; then
    # Isolated mode: the private directory is the persistent home.
    valid_bind_path "$state_home"
    home_args=(--volume "$state_home:$CONTAINER_HOME:rw")
    writable_state+=("$state_home")
    if ((trust_host_ca)); then
        # Resolve first so an existing symlink cannot move the CA mount parent.
        ca_parent=$(readlink -m -- "$state_home/ca")
        [[ "$ca_parent" == "$state_home/ca" ]] || die "isolated CA mount parent escapes the state home: $state_home/ca"
        if [[ ! -e "$ca_parent" ]]; then
            (umask 077; mkdir -- "$ca_parent") || die "cannot create private state: $ca_parent"
        fi
        check_private_dir state "$ca_parent" >/dev/null || exit 1
    fi
else
    home_args=(--tmpfs "$CONTAINER_HOME:rw,exec,nosuid,nodev,mode=1777,size=512m")
    shared_state .config/opencode "${config_override:-$HOME/.config/opencode}"
    shared_state .local/share/opencode "$HOME/.local/share/opencode"
    shared_state .cache/opencode "$HOME/.cache/opencode"
    shared_state .local/state/opencode "$HOME/.local/state/opencode"
fi
ca_bundle=''
if ((trust_host_ca)); then
    if [[ -n "${OPENCODE_CONTAINER_CA_BUNDLE:-}" ]]; then
        [[ -f "$OPENCODE_CONTAINER_CA_BUNDLE" ]] || die "OPENCODE_CONTAINER_CA_BUNDLE is not a file: $OPENCODE_CONTAINER_CA_BUNDLE"
        ca_bundle=$(readlink -f -- "$OPENCODE_CONTAINER_CA_BUNDLE")
    else
        for candidate in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt; do
            if [[ -f "$candidate" ]]; then
                ca_bundle=$candidate
                break
            fi
        done
        [[ -n "$ca_bundle" ]] || die 'no default CA bundle found; set OPENCODE_CONTAINER_CA_BUNDLE to a bundle file'
    fi
    add_bind "$ca_bundle" "$CONTAINER_HOME/ca/bundle.pem" ro
fi

# Optional integrations are mounted only on exact opt-in; ~/.claude never is.
for index in "${!integration_sources[@]}"; do
    add_bind "${integration_sources[index]}" "${integration_destinations[index]}" ro
done
if ((delegate)); then
    add_bind "$host_socket" /run/podman/podman.sock rw
fi

run_args=(
    --rm --interactive --read-only --read-only-tmpfs=false
    --userns=keep-id --user "$USER_ID:$GROUP_ID"
    --cap-drop=all --security-opt=no-new-privileges
    --memory="$memory_bytes" --cpus="$cpu_text" --pids-limit="$pids_limit"
    --tmpfs "/tmp:rw,exec,nosuid,nodev,mode=1777,size=512m"
    --tmpfs "/run:rw,nosuid,nodev,noexec,mode=1777,size=32m"
    --tmpfs "/var/tmp:rw,nosuid,nodev,noexec,mode=1777,size=512m"
    "${home_args[@]}" "${mount_args[@]}" "${xdg_args[@]}"
    --env "HOME=$CONTAINER_HOME" --env "USER=$USER_NAME"
    --workdir "$WORKSPACE"
    --label io.opencode-container.managed=true
    --label "io.opencode-container.workspace=$WORKSPACE"
    --label "io.opencode-container.workspace-name=$NAME_PREFIX"
)

# Forward by name: base allowlist, selected provider profile, operator names.
forwarded=' '
for variable_name in \
    TERM COLORTERM LANG LC_ALL \
    HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy \
    OPENCODE_CONFIG OPENCODE_CONFIG_DIR OPENCODE_CONFIG_CONTENT \
    OPENCODE_PERMISSION OPENCODE_SERVER_PASSWORD OPENCODE_SERVER_USERNAME \
    OPENCODE_DISABLE_AUTOUPDATE OPENCODE_DISABLE_DEFAULT_PLUGINS \
    OPENCODE_DISABLE_LSP_DOWNLOAD OPENCODE_DISABLE_MODELS_FETCH \
    "${provider_names[@]}" "${extra_names[@]}"; do
    if ((restricted)) && [[ " $PROXY_NAMES $PROTECTED_FLAGS " == *" $variable_name "* ]]; then
        continue
    fi
    if [[ -n "${!variable_name:-}" && "$forwarded" != *" $variable_name "* ]]; then
        forwarded+="$variable_name "
        run_args+=(--env "$variable_name")
    fi
done
# Protected literals follow forwarding; writable configuration cannot re-enable
# these features (measured on OpenCode 1.18.3, see docs/validation.md).
if ((restricted)); then
    for variable_name in $PROTECTED_FLAGS; do
        run_args+=(--env "$variable_name=1")
    done
fi
if ((trust_host_ca)); then
    for variable_name in $CA_NAMES; do
        run_args+=(--env "$variable_name=$CONTAINER_HOME/ca/bundle.pem")
    done
fi

# YOLO is a nonsecret literal added after forwarding so it wins.
if ((yolo)); then
    run_args+=(--env 'OPENCODE_PERMISSION={"*":"allow"}')
fi

if ((delegate)); then
    run_args+=(
        --env CONTAINER_HOST=unix:///run/podman/podman.sock
    )
else
    run_args+=(--unsetenv CONTAINER_HOST)
fi

if ((run_timeout > 0)); then
    run_args+=(--timeout "$run_timeout")
fi

if [[ -t 0 && -t 1 ]]; then
    run_args+=(--tty)
fi

if ((qualification_probe)); then
    agent_args=()  # The shared helper supplies the fixed probe command.
elif ((shell_mode)); then
    ((restricted)) || run_args+=(--entrypoint /bin/bash)
    agent_args=()
fi

# Restricted sessions use the shared helper; this wrapper keeps only the
# agent-specific command, environment, state and credentials.
session_helper=(python3 -I "$SCRIPT_DIR/network/session.py")
network_inputs=()
qualification_inputs=()
guard_digest=''
if ((restricted)); then
    network_inputs=(--installation "$SCRIPT_DIR" --writable "$workspace_mount"
        --mount-target "$workspace_mount" --mount-target "$CONTAINER_HOME")
    for state_path in "${writable_state[@]}"; do
        network_inputs+=(--writable "$state_path")
    done
    if [[ "$network_mode" == provider ]]; then
        network_inputs+=(--policy "$OPENCODE_CONTAINER_NETWORK_POLICY"
            --profile "$OPENCODE_CONTAINER_NETWORK_PROFILE" --proxy-image "$OPENCODE_CONTAINER_EGRESS_IMAGE"
            --runtime "$OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR")
    fi
    prepare_inputs=(--mode "$network_mode" --server-version "$network_version"
        --backend "$network_backend" --endpoint "${CONTAINER_HOST:-}" --engine "$runtime_info")
    if ((qualification_probe)); then
        prepare_inputs+=(--probe --qualification-input "${OPENCODE_CONTAINER_QUALIFICATION_INPUT:-}"
            --workspace "$WORKSPACE")
    fi
    prepared=$(printf '%s\n' "$network_platform" | "${session_helper[@]}" prepare "${network_inputs[@]}" "${prepare_inputs[@]}") \
        || exit 1
    read -r guard_digest qualification_token qualification_tls <<< "$prepared"
    if ((qualification_probe)); then
        qualification_inputs=(--probe --token "$qualification_token" --workspace "$WORKSPACE"
            --qualification-input "${OPENCODE_CONTAINER_QUALIFICATION_INPUT:-}")
        [[ "$qualification_tls" != 1 ]] || qualification_inputs+=(--tls)
    fi
fi

# Every build, including the automatic build of a missing image, is maintenance.
maintenance=0
[[ "${OPENCODE_CONTAINER_MAINTENANCE:-}" != 1 ]] || maintenance=1
build_current_image() {
    ((maintenance)) || die "image $IMAGE needs a build; prepare it with exact OPENCODE_CONTAINER_MAINTENANCE=1 (host pulls and build RUN steps are outside runtime filtering)"
    podman build --tag "$IMAGE" --file "$SCRIPT_DIR/Containerfile" "$SCRIPT_DIR"
}
if ((build_image)); then
    build_current_image
elif podman image exists "$IMAGE"; then
    :
else
    image_status=$?
    if ((image_status != 1)); then
        printf 'opencode-container: cannot inspect image %s (status %s)\n' "$IMAGE" "$image_status" >&2
        exit "$image_status"
    fi
    build_current_image
fi
if [[ "$network_mode" == provider ]]; then
    if podman image exists "$OPENCODE_CONTAINER_EGRESS_IMAGE"; then
        :
    else
        image_status=$?
        [[ "$image_status" == 1 ]] || die 'cannot inspect immutable egress proxy image'
        ((maintenance)) && [[ "$OPENCODE_CONTAINER_EGRESS_IMAGE" == *@sha256:* ]] \
            || die 'proxy image is absent; prepare the pinned artifact under explicit operator maintenance authorization (OPENCODE_CONTAINER_MAINTENANCE=1 and a registry digest)'
        podman pull "$OPENCODE_CONTAINER_EGRESS_IMAGE"
    fi
fi
# Restricted sessions and their qualification bind the immutable image ID.
session_image=$IMAGE
if ((restricted)); then
    capture_response session_image podman image inspect --format '{{.Id}}' "$IMAGE" \
        || die 'cannot resolve restricted runtime image identity'
    session_image=${session_image%$'\n'}
    [[ "$session_image" =~ ^(sha256:)?[a-f0-9]{64}$ ]] || die 'invalid restricted runtime image identity'
fi

# Lifecycle state belongs exclusively to this invocation.
container_id=''
create_pid=''
client_pid=''
session_dir=''
session_token=''
creation_pending=0
shutdown_deadline=0
qualification_check_pid=''
session_start_pid=''
diagnostics_pid=''
diagnostics_fd=''
ownership_label=io.opencode-container.session

cleanup_warning() {
    printf 'opencode-container: cleanup %s (container=%s session=%s); inspect the engine explicitly\n' \
        "$*" "${container_id:-unknown}" "${session_token:-unknown}" >&2
}
# shellcheck disable=SC2329 # Reached through EXIT/signal cleanup or indirect capture.
control() {
    local remaining=$((shutdown_deadline - SECONDS - 3)) duration status
    ((remaining >= 2)) || { cleanup_warning "deadline exhausted before $1"; return 124; }
    duration=$((remaining - 1))
    ((duration <= 2)) || duration=2
    if timeout --kill-after=1s "${duration}s" podman "$@"; then
        return 0
    else
        status=$?
        cleanup_warning "$1 failed or timed out (status $status)"
        return "$status"
    fi
}
# shellcheck disable=SC2329 # Reached through EXIT/signal cleanup or indirect capture.
child_running() {
    local child=$1 running
    [[ -n "$child" ]] || return 1
    while IFS= read -r running; do
        [[ "$running" != "$child" ]] || return 0
    done < <(jobs -pr)
    return 1
}
# shellcheck disable=SC2329 # Reached through EXIT/signal cleanup or indirect capture.
reap_client() {
    local child=$1 until
    [[ -n "$child" ]] || return 0
    if child_running "$child"; then
        kill -TERM "$child" 2>/dev/null || true
        until=$((SECONDS + 1))
        while child_running "$child" && ((SECONDS < until && SECONDS < shutdown_deadline - 1)); do sleep 0.05; done
        child_running "$child" && kill -KILL "$child" 2>/dev/null
    fi
    while child_running "$child" && ((SECONDS < shutdown_deadline)); do sleep 0.05; done
    if child_running "$child"; then
        cleanup_warning "client $child could not be reaped within deadline"
    else
        wait "$child" 2>/dev/null || true
    fi
}
# Restricted helpers: TERM, a bounded grace period, then KILL and reap.
# shellcheck disable=SC2329 # Reached through EXIT/signal cleanup.
reap_helper() {
    local child=$1 grace=$2 until
    child_running "$child" || { wait "$child" 2>/dev/null || true; return 0; }
    kill -TERM "$child" 2>/dev/null || true
    until=$((SECONDS + grace))
    while child_running "$child" && ((SECONDS < until)); do sleep 0.05; done
    if child_running "$child"; then
        cleanup_warning "restricted helper $child did not confirm cleanup before the deadline"
        kill -KILL "$child" 2>/dev/null || true
    fi
    until=$((SECONDS + 1))
    while child_running "$child" && ((SECONDS < until)); do sleep 0.05; done
    if child_running "$child"; then
        cleanup_warning "restricted helper $child could not be reaped within deadline"
    else
        wait "$child" 2>/dev/null || true
    fi
}
# Read exact record boundaries, rejecting NUL and additional final LF bytes.
read_cid() {
    local file=$1 candidate='' has_nul=0
    [[ -s "$file" ]] || return 1
    IFS= read -r -d '' candidate < "$file" && has_nul=1
    candidate=${candidate%$'\n'}
    ((has_nul == 0)) && [[ "$candidate" =~ ^[a-f0-9]{64}$ ]] || return 1
    printf '%s' "$candidate"
}
# shellcheck disable=SC2329 # Reached through EXIT/signal cleanup or indirect capture.
recover_container() {
    local candidate='' owner=''
    [[ -z "$container_id" && "$creation_pending" == 1 ]] || return 0
    candidate=$(read_cid "$cid_file") || candidate=''
    if [[ -z "$candidate" ]]; then
        # Only label-selected IDs can recover a missing/delayed creation record.
        capture_response candidate control ps --all --no-trunc --filter "label=$ownership_label=$session_token" --format '{{.ID}}' || return 1
        candidate=${candidate%$'\n'}
    fi
    [[ -n "$candidate" ]] || return 0
    [[ "$candidate" =~ ^[a-f0-9]{64}$ ]] || { cleanup_warning 'invalid or multiple recovered IDs'; return 1; }
    capture_response owner control inspect --type container --format "{{index .Config.Labels \"$ownership_label\"}}" "$candidate" || return 1
    owner=${owner%$'\n'}
    if [[ "$owner" == "$session_token" ]]; then
        container_id=$candidate
    else
        cleanup_warning 'recovered identity ownership mismatch'
        return 1
    fi
}
# shellcheck disable=SC2329 # Reached through EXIT/signal cleanup or indirect capture.
shutdown() {
    local primary_status=$1 signal=${2:-} graceful_until create_until
    trap - EXIT
    trap '' TERM INT HUP
    set +e
    shutdown_deadline=$((SECONDS + 20))
    if [[ -n "$qualification_check_pid" ]]; then
        reap_helper "$qualification_check_pid" 13
        qualification_check_pid=''
    fi
    if [[ -n "$session_start_pid" ]]; then
        # The session helper owns a separate process group. Reap the whole
        # group before its leader, including an engine client that ignores TERM.
        kill -TERM -- "-$session_start_pid" 2>/dev/null || true
        sleep 0.1
        kill -KILL -- "-$session_start_pid" 2>/dev/null || true
        reap_helper "$session_start_pid" 1
        session_start_pid=''
    fi
    if [[ -n "$session_dir" ]]; then
        if ((creation_pending)); then
            create_until=$((SECONDS + 1))
            while child_running "$create_pid" && ((SECONDS < create_until)); do sleep 0.05; done
        fi
        recover_container
        if [[ -n "$signal" && -n "$container_id" && -n "$client_pid" ]]; then
            if control kill --signal "$signal" "$container_id" >/dev/null; then
                graceful_until=$((SECONDS + 5))
                while child_running "$client_pid" && ((SECONDS < graceful_until && SECONDS < shutdown_deadline - 8)); do sleep 0.05; done
            else
                cleanup_warning "cannot forward $signal"
            fi
        fi
        if [[ -n "$container_id" ]]; then
            control rm --force --ignore --time 0 "$container_id" >/dev/null || cleanup_warning 'cannot remove owned container'
        fi
        reap_client "$create_pid"
        reap_client "$client_pid"
        if [[ -n "$diagnostics_fd" ]]; then
            exec {diagnostics_fd}>&-
            diagnostics_fd=''
        fi
        if [[ -n "$diagnostics_pid" ]]; then
            # Drain the final client output before reaping the stderr filter.
            drain_until=$((SECONDS + 1))
            while child_running "$diagnostics_pid" && ((SECONDS < drain_until)); do sleep 0.01; done
            reap_helper "$diagnostics_pid" 1
            diagnostics_pid=''
        fi
        if ((creation_pending)) && [[ -z "$container_id" ]]; then
            recover_container
            if [[ -n "$container_id" ]]; then
                control rm --force --ignore --time 0 "$container_id" >/dev/null || cleanup_warning 'cannot remove recovered owned container'
            else
                cleanup_warning 'creation outcome unresolved; client cancellation does not prove request cancellation'
            fi
        fi
        if [[ "$network_mode" == provider ]]; then
            # Owned proxy recovery/removal and diagnostics share the remaining budget.
            "${session_helper[@]}" stop --session "$session_dir" --deadline "$((shutdown_deadline - SECONDS))" \
                --container "${container_id:-unknown}" || true
        fi
        rm -rf -- "$session_dir"
    fi
    exit "$primary_status"
}
trap 'shutdown "$?"' EXIT
trap 'shutdown 143 TERM' TERM
trap 'shutdown 130 INT' INT
trap 'shutdown 129 HUP' HUP
if [[ "$network_mode" == provider ]]; then
    session_dir=$(umask 077; mktemp -d -- "$OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR/session.XXXXXXXXXXXX") \
        || die 'cannot create private session directory in OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR'
else
    session_dir=$(umask 077; mktemp -d) || die 'cannot create private session records'
fi
session_token=${session_dir##*/}
cid_file=$session_dir/cid
create_output=$session_dir/output
create_error=$session_dir/error
(umask 077; : > "$create_output"; : > "$create_error")
printf 'opencode-container: network mode=%s\n' "$network_mode" >&2
if ((restricted && qualification_probe == 0)); then
    OPENCODE_CONTAINER_IMAGE="$session_image" python3 -I "$SCRIPT_DIR/network/qualify.py" check &
    qualification_check_pid=$!
    qualification_status=0
    wait "$qualification_check_pid" || qualification_status=$?
    qualification_check_pid=''
    ((qualification_status == 0)) || exit "$qualification_status"
fi
if [[ "$network_mode" == provider ]]; then
    "${session_helper[@]}" start "${network_inputs[@]}" "${qualification_inputs[@]}" --session "$session_dir" \
        --guard-digest "$guard_digest" >"$session_dir/policy.identity" &
    session_start_pid=$!
    start_status=0
    wait "$session_start_pid" || start_status=$?
    session_start_pid=''
    ((start_status == 0)) || exit "$start_status"
fi
if ((restricted)); then
    application=()
    if ((shell_mode)); then
        application=(/bin/bash)
    elif ((qualification_probe == 0)); then
        application=(/usr/local/bin/opencode "${agent_args[@]}")
    fi
    "${session_helper[@]}" agent-args --installation "$SCRIPT_DIR" --mode "$network_mode" \
        --session "$session_dir" --guard-digest "$guard_digest" "${qualification_inputs[@]}" \
        -- "${application[@]}" >"$session_dir/agent.args"
    mapfile -d '' -t restricted_args <"$session_dir/agent.args"
    [[ "${restricted_args[0]:-}" =~ ^[0-9]+$ ]] || die 'invalid restricted session arguments'
    run_args+=("${restricted_args[@]:1:${restricted_args[0]}}")
    agent_args=("${restricted_args[@]:$((1 + restricted_args[0]))}")
fi

# Listing and collision queries are tracked clients too, so signals can cancel them.
creation_lookup() {
    local lookup_status=0
    podman "$@" </dev/null > "$session_dir/lookup" &
    create_pid=$!
    wait "$create_pid" || lookup_status=$?
    create_pid=''
    return "$lookup_status"
}
creation_lookup ps --all --format '{{.Names}}' || die 'cannot list container names'
names=$(<"$session_dir/lookup")
next_index=0
while IFS= read -r existing_name; do
    [[ "$existing_name" == "$NAME_PREFIX-"* ]] || continue
    suffix=${existing_name#"$NAME_PREFIX-"}
    [[ "$suffix" =~ ^[0-9]{1,9}$ ]] || continue
    numeric=$((10#$suffix))
    ((numeric < next_index)) || next_index=$((numeric + 1))
done <<< "$names"
for ((attempt=0; attempt<20; attempt++)); do
    name=$NAME_PREFIX-$next_index
    rm -f -- "$cid_file"
    creation_pending=1
    (umask 077; exec podman create --name "$name" --cidfile "$cid_file" \
        --label "$ownership_label=$session_token" --label "io.opencode-container.instance=$next_index" \
        "${run_args[@]}" "$session_image" "${agent_args[@]}" </dev/null >"$create_output" 2>"$create_error") &
    create_pid=$!
    create_status=0
    wait "$create_pid" || create_status=$?
    create_pid=''
    cat -- "$create_error" >&2
    if ((create_status == 0)); then
        container_id=$(read_cid "$cid_file") || die 'invalid or missing private creation ID'
        stdout_id=$(read_cid "$create_output") || stdout_id=''
        if [[ -n "$stdout_id" && "$stdout_id" != "$container_id" ]]; then
            die 'inconsistent creation IDs'
        fi
        creation_pending=0
        break
    fi
    # A returned ID on a failed request is reconciled by ownership during EXIT.
    if [[ -s "$cid_file" || -s "$create_output" ]]; then
        exit "$create_status"
    fi
    exists_status=0
    creation_lookup container exists "$name" || exists_status=$?
    case "$exists_status" in
        0) creation_pending=0; next_index=$((next_index + 1)) ;;
        1) creation_pending=0; exit "$create_status" ;;
        *) creation_pending=0; cleanup_warning "cannot confirm name collision (status $exists_status)"; exit "$create_status" ;;
    esac
done
[[ -n "$container_id" ]] || die 'cannot reserve container name after 20 confirmed collisions'
# Engine flags alone are not evidence: require the created configuration to
# carry every selected budget before the application starts.
configured_budgets=$(timeout --kill-after=1s 10s podman inspect --type container \
    --format '{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}} {{.HostConfig.PidsLimit}}' "$container_id") \
    || die 'cannot inspect session resource budgets; session not started'
[[ "$configured_budgets" == "$memory_bytes $cpu_nano $pids_limit" ]] \
    || die "session resource budgets were not applied (expected memory=$memory_bytes nano_cpus=$cpu_nano pids=$pids_limit); check rootless cgroup v2 cpu/memory/pids controller delegation; session not started"
started_at=$SECONDS
# Explicit redirection keeps Bash from replacing background-client stdin.
if [[ -f "$SCRIPT_DIR/setup/diagnostics.py" ]] && command -v python3 >/dev/null; then
    # Optional for unrestricted installs without host Python. Only the exact
    # successful Podman 4.3 restart-check line changes level; errors pass.
    mkfifo -- "$session_dir/diagnostics.pipe"
    python3 -I "$SCRIPT_DIR/setup/diagnostics.py" <"$session_dir/diagnostics.pipe" >&2 &
    diagnostics_pid=$!
    exec {diagnostics_fd}>"$session_dir/diagnostics.pipe"
    podman start --attach --interactive --sig-proxy=false "$container_id" <&0 2>&"$diagnostics_fd" {diagnostics_fd}>&- &
    client_pid=$!
    exec {diagnostics_fd}>&-
    diagnostics_fd=''
else
    podman start --attach --interactive --sig-proxy=false "$container_id" <&0 &
    client_pid=$!
fi
status=0
wait "$client_pid" || status=$?
client_pid=''
if ((run_timeout > 0 && status != 0 && SECONDS - started_at >= run_timeout)); then
    printf 'opencode-container: session lifetime limit reached (%s s); exit status %s\n' "$run_timeout" "$status" >&2
fi
exit "$status"
