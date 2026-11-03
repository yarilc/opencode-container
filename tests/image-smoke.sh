#!/usr/bin/env bash
set -euo pipefail
[[ $(id -u) != 0 ]]
[[ $(id -un) == "$USER" ]]
for tool in opencode bash curl git jq podman rg; do command -v "$tool" >/dev/null; done
[[ $(opencode --version) == 1.18.3 ]]
[[ -z ${CONTAINER_HOST+x} ]]
[[ ! -S /run/podman/podman.sock ]]
[[ $(awk '$2=="/" {print $4}' /proc/mounts) == ro,* ]]
grep -q 'CapEff:[[:space:]]*0000000000000000' /proc/self/status
grep -q 'NoNewPrivs:[[:space:]]*1' /proc/self/status
for path in /tmp /run /var/tmp; do
    options=$(awk -v p="$path" '$2==p {print $4}' /proc/mounts)
    [[ ,$options, == *,nosuid,* && ,$options, == *,nodev,* ]]
    [[ $(stat -c %a "$path") == 1777 ]]
    capacity=$(df -Pk "$path" | awk 'NR==2 {print $2}')
    expected=524288
    [[ $path != /run ]] || expected=32768
    [[ $capacity == "$expected" ]]
    if [[ $path == /tmp ]]; then [[ ,$options, != *,noexec,* ]]; else [[ ,$options, == *,noexec,* ]]; fi
    printf '#!/bin/sh\nexit 0\n' > "$path/exec-probe"
    chmod +x "$path/exec-probe"
    if [[ $path == /tmp ]]; then "$path/exec-probe"; elif "$path/exec-probe" 2>/dev/null; then exit 10; fi
    printf temporary > "$path/opencode-ephemeral"
done
if touch /usr/opencode-write-probe 2>/dev/null; then exit 11; fi
for name in XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME; do
    base=${!name}
    [[ -d $base/opencode && -w $base/opencode ]]
    printf persistent > "$base/opencode/sentinel"
done
printf 'Image smoke checks passed.\n'
