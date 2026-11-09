#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: opencode-container.sh [container options] [OpenCode arguments...]

Container options:
  --container-build      build or refresh the container image before starting
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
  OPENCODE_CONTAINER_IMAGE    image name (default: localhost/opencode-cli:latest);
                         OpenCode and OpenSpec versions are pinned in Containerfile
  OPENCODE_CONTAINER_STATE_DIR private host directory used as the persistent
                         /opencode-home (default: unset; the host OpenCode XDG
                         directories are mounted below an ephemeral home)
  OPENCODE_CONTAINER_PODMAN   expose the host Podman socket only when exactly 1
                         (default: disabled; other values also disable access)
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
                         credentials work without it)
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
EOF
}

build_image=0
shell_mode=0
git_worktree=0
agent_args=()
for arg in "$@"; do
    case "$arg" in
        --container-help) usage; exit 0 ;;
        --container-build) build_image=1 ;;
        --container-shell) shell_mode=1 ;;
        --container-git-worktree) git_worktree=1 ;;
        *) agent_args+=("$arg") ;;
    esac
done

SCRIPT_PATH=$(readlink -f -- "${BASH_SOURCE[0]}")
SCRIPT_DIR=$(dirname -- "$SCRIPT_PATH")
readonly SCRIPT_PATH SCRIPT_DIR

die() { printf 'opencode-container: %s\n' "$*" >&2; exit 1; }

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
readonly AUTHORITATIVE_NAMES=' HOME USER XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME CONTAINER_HOST CONTAINER_CONNECTION '
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
extra_names=()
read -r -a requested_extra_names <<< "${OPENCODE_CONTAINER_ENV_VARS:-}"
for variable_name in "${requested_extra_names[@]}"; do
    [[ "$variable_name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] \
        || die "OPENCODE_CONTAINER_ENV_VARS contains an invalid variable name: $variable_name"
    if [[ "$AUTHORITATIVE_NAMES" == *" $variable_name "* ]]; then
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
if ((provider_selected == 0)); then
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
if [[ -n "${OPENCODE_CONTAINER_STATE_DIR+x}" ]]; then
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
    if [[ ! -e "$state_request" && ! -L "$state_request" ]]; then
        (umask 077; mkdir -p -- "$state_request") || die "cannot create OPENCODE_CONTAINER_STATE_DIR: $state_request"
    fi
    state_home=$(check_private_dir OPENCODE_CONTAINER_STATE_DIR "$state_request") || exit 1
    for relative in .config/opencode .local/share/opencode .cache/opencode .local/state/opencode; do
        (umask 077; mkdir -p -- "$state_home/$relative") || die "cannot create private state: $state_home/$relative"
    done
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
    || die 'cannot query launch engine'
engine_response=${engine_response%$'\n'}
[[ "$engine_response" != *$'\n'* && "$engine_response" != *$'\r'* ]] || die 'invalid launch engine records'
launch_pattern='^[[:blank:]]*true[[:blank:]]+linux[[:blank:]]+(true|false)[[:blank:]]*$'
[[ "$engine_response" =~ $launch_pattern ]] || die 'a complete Linux rootless engine response is required'
[[ "${BASH_REMATCH[1]}" == false || "${CONTAINER_HOST:-}" == unix:///* ]] \
    || die 'remote launch engine requires explicit same-host Unix CONTAINER_HOST'

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
)
private_xdg() {
    local variable=$1 fallback=$2 base path resolved
    base=${!variable:-$HOME/$fallback}
    [[ "$base" == /* ]] || die "$variable must be absolute: $base"
    path=${base%/}/opencode
    if [[ ! -e "$path" && ! -L "$path" ]]; then
        (umask 077; mkdir -p -- "$path") || die "cannot create private state: $path"
    fi
    resolved=$(check_private_dir state "$path") || exit 1
    add_bind "$resolved" "$CONTAINER_HOME/$fallback/opencode" rw
}
if [[ -n "$state_home" ]]; then
    # Isolated mode: the private directory is the persistent home.
    valid_bind_path "$state_home"
    home_args=(--volume "$state_home:$CONTAINER_HOME:rw")
else
    home_args=(--tmpfs "$CONTAINER_HOME:rw,exec,nosuid,nodev,mode=1777,size=512m")
    private_xdg XDG_CONFIG_HOME .config
    private_xdg XDG_DATA_HOME .local/share
    private_xdg XDG_CACHE_HOME .cache
    private_xdg XDG_STATE_HOME .local/state
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
    if [[ -n "${!variable_name:-}" && "$forwarded" != *" $variable_name "* ]]; then
        forwarded+="$variable_name "
        run_args+=(--env "$variable_name")
    fi
done

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

if ((shell_mode)); then
    run_args+=(--entrypoint /bin/bash)
    agent_args=()
fi

build_current_image() {
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

# Lifecycle state belongs exclusively to this invocation.
container_id=''
create_pid=''
client_pid=''
session_dir=''
session_token=''
creation_pending=0
shutdown_deadline=0
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
        if ((creation_pending)) && [[ -z "$container_id" ]]; then
            recover_container
            if [[ -n "$container_id" ]]; then
                control rm --force --ignore --time 0 "$container_id" >/dev/null || cleanup_warning 'cannot remove recovered owned container'
            else
                cleanup_warning 'creation outcome unresolved; client cancellation does not prove request cancellation'
            fi
        fi
        rm -rf -- "$session_dir"
    fi
    exit "$primary_status"
}
trap 'shutdown "$?"' EXIT
trap 'shutdown 143 TERM' TERM
trap 'shutdown 130 INT' INT
trap 'shutdown 129 HUP' HUP
session_dir=$(umask 077; mktemp -d) || die 'cannot create private session records'
session_token=${session_dir##*/}
cid_file=$session_dir/cid
create_output=$session_dir/output
create_error=$session_dir/error
(umask 077; : > "$create_output"; : > "$create_error")

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
        "${run_args[@]}" "$IMAGE" "${agent_args[@]}" </dev/null >"$create_output" 2>"$create_error") &
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
podman start --attach --interactive --sig-proxy=false "$container_id" <&0 &
client_pid=$!
status=0
wait "$client_pid" || status=$?
client_pid=''
if ((run_timeout > 0 && status != 0 && SECONDS - started_at >= run_timeout)); then
    printf 'opencode-container: session lifetime limit reached (%s s); exit status %s\n' "$run_timeout" "$status" >&2
fi
exit "$status"
