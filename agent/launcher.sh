# OpenCode agent part for the shared launcher core (launcher/core.sh). It
# mirrors agent/profile.json and agent/policies/default.json;
# tests/test_alignment.py compares them. See docs/launcher-contract.md in
# sandbox-container.
# The core sources this file: it reads the AGENT_* data and hook outputs and
# defines the core state the hooks read.
# shellcheck shell=bash disable=SC2034,SC2154
AGENT_NAME=opencode-container
AGENT_DISPLAY_NAME=OpenCode
AGENT_WRAPPER=opencode-container.sh
AGENT_ENV_PREFIX=OPENCODE_CONTAINER
AGENT_LABEL_NAMESPACE=io.opencode-container
AGENT_IMAGE=localhost/opencode-cli
AGENT_PROXY_IMAGE=localhost/opencode-egress
AGENT_HOME=/opencode-home
AGENT_COMMAND=opencode
AGENT_EXEC=/usr/local/bin/opencode
AGENT_CONFIG_DIR_ENV=OPENCODE_CONTAINER_CONFIG_DIR
AGENT_CONFIG_HOME=.config/opencode
AGENT_SHARED_DIRS=(.local/share/opencode .cache/opencode .local/state/opencode)
AGENT_PRIVATE_SHARED_DIRS=1
AGENT_APPROVAL_BYPASS_ENV=OPENCODE_CONTAINER_YOLO
# OpenTUI extracts and loads its native renderer from /tmp (contract U7).
AGENT_EXEC_TMP=1
AGENT_INSTALL_FILES=()
AGENT_CREDENTIALS=(anthropic-api=ANTHROPIC_API_KEY openai-api=OPENAI_API_KEY openrouter-api=OPENROUTER_API_KEY
    opencode-zen=OPENCODE_API_KEY)
AGENT_POLICY_HOSTS=("anthropic-api=api.anthropic.com" "openai-api=api.openai.com" "openrouter-api=openrouter.ai"
    "opencode-zen=opencode.ai")
# OpenCode state lives at fixed XDG bases below the home; host values never
# relocate it, and the forwarding list cannot replace them.
AGENT_SESSION_ENV=(XDG_CONFIG_HOME=/opencode-home/.config XDG_DATA_HOME=/opencode-home/.local/share
    XDG_CACHE_HOME=/opencode-home/.cache XDG_STATE_HOME=/opencode-home/.local/state)
# Optional traffic stays off in offline and provider sessions. The core sets
# these after toolchain and forwarded variables and reserves them in those modes.
AGENT_RESTRICTED_ENV=(OPENCODE_DISABLE_AUTOUPDATE=1 OPENCODE_DISABLE_DEFAULT_PLUGINS=1
    OPENCODE_DISABLE_LSP_DOWNLOAD=1 OPENCODE_DISABLE_MODELS_FETCH=1 OPENCODE_DISABLE_SHARE=1)
AGENT_PROVIDER_ENV=()
AGENT_UNSET_ENV=()
AGENT_RESERVED_ENV=(XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME)

# The physical opted-in integration directories, set by agent_validate.
opencode_agents_dir=''
opencode_system_config=''

# The variables one OPENCODE_CONTAINER_PROVIDER value forwards (the provider
# metadata of the pinned OpenCode release).
opencode_provider_names() {
    case "$1" in
        anthropic) printf '%s\n' ANTHROPIC_API_KEY ;;
        openai) printf '%s\n' OPENAI_API_KEY OPENAI_BASE_URL ;;
        google) printf '%s\n' GOOGLE_API_KEY GOOGLE_GENERATIVE_AI_API_KEY GEMINI_API_KEY ;;
        openrouter) printf '%s\n' OPENROUTER_API_KEY ;;
        amazon-bedrock) printf '%s\n' AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_REGION \
            AWS_BEARER_TOKEN_BEDROCK ;;
        azure) printf '%s\n' AZURE_RESOURCE_NAME AZURE_API_KEY ;;
        opencode) printf '%s\n' OPENCODE_API_KEY ;;
        none) ;;
        *) return 1 ;;
    esac
}

opencode_opt_in() {
    local variable=$1 path=$2 resolved
    [[ "${!variable:-}" == 1 ]] || return 0
    resolved=$(cd -- "$path" 2>/dev/null && pwd -P) && [[ "$path" == /* && -d "$resolved" ]] \
        || { printf '%s: %s=1 but the directory does not exist: %s\n' "$AGENT_NAME" "$variable" "$path" >&2; return 1; }
    printf '%s' "$resolved"
}

# Runs before any engine query or state operation.
agent_validate() {
    local mode=$1 profile_provider=''
    if [[ -n "${OPENCODE_CONTAINER_PROVIDER+x}" ]]; then
        opencode_provider_names "$OPENCODE_CONTAINER_PROVIDER" >/dev/null || {
            printf '%s: OPENCODE_CONTAINER_PROVIDER must be one of: anthropic, openai, google, openrouter, amazon-bedrock, azure, opencode, none\n' \
                "$AGENT_NAME" >&2
            return 1
        }
        if [[ "$mode" == provider && "$OPENCODE_CONTAINER_PROVIDER" != none ]]; then
            case "$network_profile" in
                anthropic-api) profile_provider=anthropic ;;
                openai-api) profile_provider=openai ;;
                openrouter-api) profile_provider=openrouter ;;
                opencode-zen) profile_provider=opencode ;;
            esac
            [[ "$OPENCODE_CONTAINER_PROVIDER" == "$profile_provider" ]] || {
                printf '%s: OPENCODE_CONTAINER_PROVIDER=%s does not match OPENCODE_CONTAINER_NETWORK_PROFILE=%s; unset it or select the matching provider\n' \
                    "$AGENT_NAME" "$OPENCODE_CONTAINER_PROVIDER" "$network_profile" >&2
                return 1
            }
        fi
    fi
    opencode_agents_dir=$(opencode_opt_in OPENCODE_CONTAINER_AGENTS_DIR "${HOME:-}/.agents") || return 1
    opencode_system_config=$(opencode_opt_in OPENCODE_CONTAINER_SYSTEM_CONFIG /etc/opencode) || return 1
    case "${OPENCODE_CONTAINER_YOLO,,}" in
        1|true|yes)
            if ((! shell_mode)) && [[ -n "${OPENCODE_PERMISSION:-}" ]]; then
                printf '%s: OPENCODE_CONTAINER_YOLO cannot be combined with OPENCODE_PERMISSION; unset one of them\n' \
                    "$AGENT_NAME" >&2
                return 1
            fi
            ;;
    esac
}

# The opted-in integrations, read-only from their physical directories.
agent_mounts() {
    local home=$2
    [[ -z "$opencode_agents_dir" ]] || agent_mount_specs+=("ro:$opencode_agents_dir:$home/.agents")
    [[ -z "$opencode_system_config" ]] || agent_mount_specs+=("ro:$opencode_system_config:/etc/opencode")
}

# OpenCode's native variables, forwarded by name when set; in unrestricted mode
# also the forwarded optional-traffic switches and the selected provider's set.
# Restricted modes get the selected profile's credential from the core.
agent_environment() {
    local mode=$1 name
    agent_env=(OPENCODE_CONFIG OPENCODE_CONFIG_DIR OPENCODE_CONFIG_CONTENT OPENCODE_PERMISSION
        OPENCODE_SERVER_USERNAME OPENCODE_SERVER_PASSWORD)
    [[ "$mode" == unrestricted ]] || return 0
    agent_env+=(OPENCODE_DISABLE_AUTOUPDATE OPENCODE_DISABLE_DEFAULT_PLUGINS OPENCODE_DISABLE_LSP_DOWNLOAD
        OPENCODE_DISABLE_MODELS_FETCH)
    if [[ -n "${OPENCODE_CONTAINER_PROVIDER:-}" ]]; then
        while IFS= read -r name; do
            agent_env+=("$name")
        done < <(opencode_provider_names "$OPENCODE_CONTAINER_PROVIDER")
    fi
}

# OPENCODE_CONTAINER_YOLO: allow every OpenCode permission request; the core
# skips it in shell mode and the qualification probe.
agent_approval_bypass() {
    agent_bypass_env=('OPENCODE_PERMISSION={"*":"allow"}')
}

agent_help() {
    printf '  OPENCODE_CONTAINER_YOLO auto-approve every OpenCode permission request,\n'
    printf '                          including configured ask/deny rules: 1, true or yes\n'
    printf '                          (case-insensitive; default: disabled; never applied in\n'
    printf '                          shell mode; refused with a host OPENCODE_PERMISSION)\n'
    printf '  OPENCODE_CONTAINER_PROVIDER forward one provider'"'"'s variables by name in\n'
    printf '                          unrestricted sessions: anthropic (ANTHROPIC_API_KEY),\n'
    printf '                          openai (OPENAI_API_KEY, OPENAI_BASE_URL), google\n'
    printf '                          (GOOGLE_API_KEY, GOOGLE_GENERATIVE_AI_API_KEY,\n'
    printf '                          GEMINI_API_KEY), openrouter (OPENROUTER_API_KEY),\n'
    printf '                          amazon-bedrock (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,\n'
    printf '                          AWS_SESSION_TOKEN, AWS_REGION, AWS_BEARER_TOKEN_BEDROCK),\n'
    printf '                          azure (AZURE_RESOURCE_NAME, AZURE_API_KEY), opencode\n'
    printf '                          (OPENCODE_API_KEY) or none (default); in provider mode\n'
    printf '                          unset, none or the network profile'"'"'s provider\n'
    printf '  OPENCODE_CONTAINER_AGENTS_DIR exactly 1 mounts ~/.agents read-only\n'
    printf '                          (default: not mounted)\n'
    printf '  OPENCODE_CONTAINER_SYSTEM_CONFIG exactly 1 mounts /etc/opencode read-only\n'
    printf '                          (default: not mounted)\n'
    printf '  ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, OPENCODE_API_KEY\n'
    printf '                          forwarded by name only to provider sessions using\n'
    printf '                          anthropic-api, openai-api, openrouter-api or opencode-zen\n'
    printf '                          respectively; credentials stored by opencode auth login\n'
    printf '                          work without them\n'
    printf '\nOPENCODE_CONFIG, OPENCODE_CONFIG_DIR, OPENCODE_CONFIG_CONTENT, OPENCODE_PERMISSION\n'
    printf 'and OPENCODE_SERVER_USERNAME/PASSWORD are forwarded by name when set. Offline and\n'
    printf 'provider sessions set OPENCODE_DISABLE_AUTOUPDATE, _DEFAULT_PLUGINS, _LSP_DOWNLOAD,\n'
    printf '_MODELS_FETCH and _SHARE to 1; forwarded variables and settings cannot override them.\n'
}
