#!/usr/bin/env bash
# Run tooling in a container with private native Linux state and preserved paths.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
tools_image=${OPENCODE_TEST_TOOLS_IMAGE:-localhost/claude-code:latest}
[[ $(podman info --format '{{.Host.Security.Rootless}}') == true ]]
socket=$(podman info --format '{{.Host.RemoteSocket.Path}}')
[[ $socket == /* ]]
volume=''
cleanup() { [[ -z "$volume" ]] || podman volume rm "$volume" >/dev/null; }
trap cleanup EXIT
volume=$(podman volume create --label io.opencode.acceptance=runner)
state_root=$(podman volume inspect --format '{{.Mountpoint}}' "$volume")
podman run --rm --label io.opencode.acceptance=runner --interactive --userns=keep-id --user "$(id -u):$(id -g)" \
    --volume "$root:$root:rw" --volume "$state_root:$state_root:rw" \
    --volume "$socket:/run/podman/podman.sock:rw" --workdir "$root" \
    --env CONTAINER_HOST=unix:///run/podman/podman.sock \
    --env OPENCODE_RUNTIME_TESTS=1 --env "OPENCODE_TEST_STATE_ROOT=$state_root" \
    --env "OPENCODE_TEST_TOOLS_IMAGE=$tools_image" --entrypoint python3 "$tools_image" \
    -m unittest discover -s tests -p test_runtime.py -v "$@"
