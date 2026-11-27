#!/usr/bin/env bash
# Same-host service runner with disposable state on native Linux volume storage.
set -Eeuo pipefail
project_root=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
image=${OPENCODE_CONTAINER_IMAGE:-localhost/opencode-cli:latest}
# The runner image needs Python 3.11+, Bash, GNU timeout, Git and Podman remote.
tools_image=${OPENCODE_TEST_TOOLS_IMAGE:-$image}
# The launch service's socket: a Unix CONTAINER_HOST, else the runtime directory's.
# Host Podman delegation was removed, so no delegation override applies.
socket=''
if [[ "${CONTAINER_HOST:-}" == unix:///?* ]]; then
    socket=${CONTAINER_HOST#unix://}
fi
socket=${socket:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/podman/podman.sock}
host_socket=$(podman --remote --url "unix://$socket" info --format '{{.Host.RemoteSocket.Path}}')
[[ "$host_socket" == /* ]] || { printf 'Runtime tests require an absolute host socket path\n' >&2; exit 1; }
pattern=test_runtime.py
guard_environment=()
# The default runtime suite and the guarded Windows-workspace check write below
# the checkout's .test-state.
project_mode=ro
# Shared suites copied from the reference, run without real-engine opt-ins: every
# shared test module of tests/test_alignment.py except test_setup, which --setup
# runs with a writable checkout, plus OpenCode's image-pin checks.
shared=(test_reference_copy test_alignment test_launcher test_agent_profile test_network_policy test_mux test_tls_client_hello
    test_tls_proxy test_platform test_qualification test_guard test_session test_network_feasibility
    test_engine test_toolchains test_windows_bootstrap test_windows_enter test_image_pins)
case "${1:-}" in
    # The shared launcher tests and this wrapper's own: test_launcher.py, test_wrapper.py.
    --wrapper) pattern='test_[lw][ar][au]*.py' ;;
    --shared) pattern='' ;;
    --setup) pattern=test_setup.py; project_mode=rw ;;
    --setup-runtime) pattern=test_setup_runtime.py; project_mode=rw ;;
    --qualification) pattern=test_qualification.py ;;
    --network-feasibility) pattern=test_network_feasibility.py ;;
    --network) pattern=test_network_runtime.py; project_mode=rw ;;
    --network-policy) pattern=test_network_policy.py ;;
    --mux) pattern=test_mux.py ;;
    --guard|--guard-idle)
        pattern=test_guard.py
        guard_toolchain=$(podman image inspect --format '{{.Id}}' \
            "${SANDBOX_GUARD_TOOLCHAIN:-localhost/opencode-guard-toolchain:development}")
        guard_environment=(--env SANDBOX_GUARD_TESTS=1 --env "SANDBOX_GUARD_TOOLCHAIN=$guard_toolchain")
        if [[ "$1" == --guard-idle ]]; then
            guard_environment+=(--env SANDBOX_IDLE_TESTS=1)
            set -- "$1" -k test_guarded_multiplex_idle_resume "${@:2}"
        fi
        ;;
    *) set -- '' "$@"; project_mode=rw ;;
esac
shift
volume=$(podman volume create --label io.opencode-container.acceptance=runner)
cleanup() { podman volume rm --force "$volume" >/dev/null; }
trap cleanup EXIT
native_root=$(podman volume inspect --format '{{.Mountpoint}}' "$volume")
if [[ -n "$pattern" ]]; then
    selection=(discover -s tests -p "$pattern" -v)
    runtime_environment=(--env OPENCODE_RUNTIME_TESTS=1 --env SANDBOX_RUNTIME_TESTS=1)
else
    selection=(-v "${shared[@]/#/tests.}")
    runtime_environment=()
fi
# Wrapper fixtures need private, executable temporary storage: the runner's
# /tmp is world-writable, and the toolchain library refuses such ancestors.
podman run --rm --interactive --label io.opencode-container.acceptance=runner \
    --userns=keep-id --user "$(id -u):$(id -g)" \
    --volume "$project_root:$project_root:$project_mode" \
    --volume "$native_root:$native_root:rw" \
    --volume "$host_socket:/run/podman/podman.sock:rw" \
    --tmpfs /tmp:rw,exec,nosuid,nodev,mode=1777 \
    --mount type=tmpfs,destination=/sandbox-test-tmp,tmpfs-mode=0700,U=true,tmpfs-size=1g \
    --env SANDBOX_TEST_TMPDIR=/sandbox-test-tmp \
    --workdir "$project_root" \
    --env HOME=/tmp \
    --env CONTAINER_HOST=unix:///run/podman/podman.sock \
    "${runtime_environment[@]}" \
    --env "OPENCODE_CONTAINER_IMAGE=$image" --env "OPENCODE_TEST_TOOLS_IMAGE=$tools_image" \
    --env "OPENCODE_TEST_STATE_ROOT=$native_root" --env "SANDBOX_TEST_STATE_ROOT=$native_root" \
    "${guard_environment[@]}" \
    --entrypoint python3 "$tools_image" \
    -B -m unittest "${selection[@]}" "$@"
