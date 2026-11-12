# Repository Guidelines

## Project Structure & Module Organization

- `opencode-container.sh` owns runtime policy: network mode admission, mounts, hardening, environment forwarding, YOLO, socket handling, naming, labels, and cleanup. Restricted preparation, proxy lifecycle and restricted container arguments come from `network/session.py` (`prepare`, `start`, `agent-args`, `stop`); never re-implement them inline.
- `agent/profile.json` and `agent/policies/default.json` hold every OpenCode-specific value used by the shared network code: identity, images, state layout and the four provider profiles.
- `opencode-wrapper` is a deprecated shim that warns once and execs `opencode-container.sh` with unchanged arguments; keep it until the final cleanup.
- `Containerfile` owns the generic image: the digest-pinned base, the common toolset, and the pinned OpenCode (`1.18.3`) and OpenSpec (`1.16.0`) npm packages; `.containerignore` is its default-deny build-context allowlist. The image contains no caller identity and its entrypoint is `opencode`.
- `tests/test_image_pins.py` rejects floating image inputs, a missing toolset package and an OpenCode version that differs from the policy's `tested.cli`.
- `README.md` documents setup, usage and security; keep it synchronized with runtime behavior and trust the scripts when they disagree.
- `openspec/specs/` contains current behavior contracts; `openspec/changes/` holds active proposals and dated archives.
- `tests/` contains synthetic wrapper tests and opted-in real Podman checks; `docs/validation.md` records verification results and limitations.

## Shared and agent-specific files

`network/`, `setup/` and the shared tests listed in `tests/test_alignment.py`
(`sandbox_profile.py`, `test_alignment.py`, `test_setup.py`, `test_agent_profile.py`, `test_network_policy.py`, `test_mux.py`,
`test_tls_client_hello.py`, `test_tls_proxy.py`, `test_platform.py`,
`test_qualification.py`, `test_guard.py`, `test_session.py`,
`test_network_feasibility.py` and their fixtures) are copied unchanged from
`claude-container` at tag `sandbox-ref-11`. Never edit them here, and never add
an agent identifier (`opencode`, `anthropic`, `openai`, `openrouter`) to them.
Fix a defect in `claude-container` first, then copy the files again and update
the manifest in `tests/test_reference_copy.py`. OpenCode values come only from:
- `agent/`, the wrapper, `Containerfile` and `.containerignore`;
- the per-agent tests: `test_wrapper.py`, `test_runtime.py`,
  `test_network_runtime.py`, `network_tls_fixture.py`, `test_setup_runtime.py`,
  `test_image_pins.py`, `test_reference_copy.py` and `run-runtime.sh`.

`tests/test_alignment.py` enforces the identifier scan and wrapper/profile
consistency; `tests/test_reference_copy.py` enforces byte identity with the tag.
New users run `bash ./opencode-container.sh --container-setup`
(`docs/setup.md`).

## Build, Test, and Development Commands

Run static shell checks first:

```bash
bash -n opencode-container.sh
bash -n opencode-wrapper
```

Build the image with rootless Podman (builds through the wrapper need exact `OPENCODE_CONTAINER_MAINTENANCE=1`):

```bash
podman build --tag localhost/opencode-cli:latest --file Containerfile .
```

Every launch needs `OPENCODE_CONTAINER_NETWORK` (`offline`, `provider` or `unrestricted`). Focused smoke test:

```bash
export OPENCODE_CONTAINER_NETWORK=unrestricted
./opencode-container.sh --version
./opencode-container.sh
podman ps --all --filter label=io.opencode-container.managed=true
```

The first command must print `1.18.3`. Start and quit the second command interactively; `--version` does not initialize OpenTUI and cannot catch renderer failures. The final command must show no test-owned wrapper container; preserve any preexisting sessions. ShellCheck may be run through Podman when unavailable on the host.

## Coding Style & Naming Conventions

Use Bash with `set -euo pipefail`, quoted variables, and command arrays for user-controlled arguments. Follow the script's four-space indentation. Prefer small functions and actionable errors prefixed `opencode-container:`. Wrapper settings use the `OPENCODE_CONTAINER_` prefix; never add generic names in OpenCode's own `OPENCODE_*` namespace. Labels use `io.opencode-container.*`. Write documentation, comments, help, and messages in English.

## Testing Guidelines

Run the suites through `tests/run-runtime.sh`, which uses private native Linux state in a disposable volume, the same absolute workspace mount and an executable `/tmp` (the fake engine of `test_wrapper.py` must be executable):

```bash
bash tests/run-runtime.sh --wrapper   # wrapper contracts, fake engine
bash tests/run-runtime.sh --shared    # shared suites from claude-container
bash tests/run-runtime.sh --setup     # shared setup suite
bash tests/run-runtime.sh --setup-runtime  # guided setup with real rootless Podman
bash tests/run-runtime.sh             # unrestricted runtime suite
bash tests/run-runtime.sh --network   # restricted modes, real rootless Podman
bash tests/run-runtime.sh --guard     # guard fixtures (toolchain image required)
```

Other modes: `--qualification`, `--network-feasibility`, `--network-policy`, `--mux`, `--guard-idle`. The tooling image defaults to the OpenCode image; `OPENCODE_TEST_TOOLS_IMAGE` can select another image with Python 3.11+, Bash, GNU timeout, Git and Podman remote. Tests never import actual credentials.

Keep synthetic evidence separate from real acceptance in `docs/validation.md`. Check OpenTUI startup and quit interactively in a PTY in addition to version output, and inspect test-owned resources afterward. Temporary transcripts and Python caches are ignored by `.gitignore`; production build inputs remain governed solely by `.containerignore`.

## OpenSpec Workflow

For OpenSpec changes, keep proposal, delta specs, design, and tasks coherent. Proposal work changes planning artifacts only; implement through the apply workflow. Mark tasks complete after verification, synchronize delta specs into main specs, and archive completed changes under dated directories.

## Commit & Pull Request Guidelines

Use concise imperative subjects. Keep commits focused. PRs should explain behavior changes, list verification, identify security/mount changes, and update `README.md` when usage changes.

## Security & Configuration

### Required behavior

- Use rootless Podman only. Docker and Compose support are intentionally out of scope.
- Require host Podman and GNU coreutils timeout. Validate a complete Linux rootless launch response with boolean ServiceIsRemote before image operations. Accept local or explicit same-host absolute Unix endpoints; reject named/implicit remote/TCP/SSH contexts and slash-only paths.
- Delegate only with exact `OPENCODE_CONTAINER_PODMAN=1`; all other values omit the mount and explicitly unset session CONTAINER_HOST. Enabled verification failures stop before image operations. Select nonempty OPENCODE_CONTAINER_PODMAN_SOCKET, Unix launch endpoint, then runtime default; query the canonical accessible socket and bind its reported absolute host source. Never start/enable services or silently fall back.
- Preserve host security policy: no SELinux label disabling or automatic relabeling. Document manual service/permissions/SELinux setup. Socket authority can create host mounts beyond the workspace. Reject failed, incomplete, extra-record, or CR-containing engine/service responses, preserving trailing records and query status.
- Preserve the host workspace at the same absolute path inside the container so containers launched through `podman-remote` can bind it correctly.
- Require an explicit `OPENCODE_CONTAINER_NETWORK`; never fall back to unrestricted networking after a restricted failure. Reject delegation in offline and provider modes. Every image build needs exact `OPENCODE_CONTAINER_MAINTENANCE=1`. Restricted modes never forward host proxy or CA variables, forward only the network profile's credential and set the protected `OPENCODE_DISABLE_*` values after forwarding.
- Keep the root filesystem read-only. Only the workspace and OpenCode state directories are host-writable. `.agents` and `/etc/opencode` are read-only mounts only on exact `OPENCODE_CONTAINER_AGENTS_DIR=1` / `OPENCODE_CONTAINER_SYSTEM_CONFIG=1`; never mount `~/.claude` or another agent's state.
- Keep `/tmp` as an ephemeral `tmpfs` with `nosuid,nodev`, but never add `noexec`: OpenTUI extracts a shared library there and loads it at startup.
- Keep `--cap-drop=all`, `no-new-privileges`, the pinned image inputs and by-name forwarding; never add `--privileged` or add a capability back.
- Validate `OPENCODE_CONTAINER_MEMORY_LIMIT` (4g), `OPENCODE_CONTAINER_CPU_LIMIT` (2), `OPENCODE_CONTAINER_PIDS_LIMIT` (512) and `OPENCODE_CONTAINER_RUN_TIMEOUT` before engine queries with the Claude `sandbox-ref-5` rules and messages; request each budget only when the engine delegates its cgroup v2 controller (`Host.CgroupControllers`), announce unenforced ones, and never require host changes to delegate them; inspect the created container and start it only when enforced budgets match and unenforced ones are absent; print the lifetime notice while keeping the client status.
- Refuse a workspace or worktree parent that physically is `/`, a system directory, `/tmp`, the physical home or a `/mnt/<letter>` drive root, before engine queries or state creation, unless exactly `OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=1`, which warns.
- Do not replace existing containers. Names are `<sanitized-workspace-basename>-N`, where `N` is one greater than the highest existing suffix; reserve names atomically with `podman create`.
- One generic image (`OPENCODE_CONTAINER_IMAGE`, default `localhost/opencode-cli:latest`); the numeric identity is set only at launch with `--userns=keep-id --user UID:GID`. `OPENCODE_CONTAINER_VERSION` and `OPENCODE_VERSION` are ignored with a warning.
- Sessions use `HOME=/opencode-home` with XDG bases below it. By default it is a 512 MiB exec tmpfs with the four validated host OpenCode directories (`~/.config/opencode` or `OPENCODE_CONTAINER_CONFIG_DIR`, `~/.local/share/opencode`, `~/.cache/opencode`, `~/.local/state/opencode`; host `XDG_*_HOME` does not relocate them) bound at fixed paths below it; a nonempty `OPENCODE_CONTAINER_STATE_DIR` instead binds a private, validated, non-overlapping host directory as the persistent home and conflicts with `OPENCODE_CONTAINER_CONFIG_DIR`.
- Forward environment variables by name only from the base allowlist, the provider profile selected with `OPENCODE_CONTAINER_PROVIDER`, and names in `OPENCODE_CONTAINER_ENV_VARS`; never forward GitHub tokens or other providers' keys by default, and never introduce `--env-host`. Profile variable sets follow the pinned OpenCode version's provider metadata; re-read them when the version changes.
- `OPENCODE_CONTAINER_YOLO` accepts `1/true/yes` and `''/0/false/no` case-insensitively and rejects other values before engine queries. Enabled, it adds the literal `OPENCODE_PERMISSION={"*":"allow"}` after forwarding and refuses a host `OPENCODE_PERMISSION`; disabled, it adds nothing. YOLO and delegation are independent and YOLO changes no mount or forwarding.

### State and environment contracts

Privately create only missing OpenCode XDG config/data/cache/state directories with a scoped umask; physically resolve and verify each caller-owned directory's read/write/traverse access and absence of group/other permissions before image operations. Never repair state with chmod/chown or copy credentials. Resolve nonstandard host homes and symlinked state directories physically, then bind each validated directory at its fixed path below `/opencode-home`; isolated state follows the same validation and must not overlap the workspace. A tmpfs home binds below `/opencode-home` but never shadows it. Reject destination conflicts. Keep opted-in integrations read-only and preserve physical absolute bind sources. Use explicit tmpfs mounts: exec `/tmp` 512 MiB, exec `/opencode-home` 512 MiB in shared mode, noexec `/var/tmp` 512 MiB and noexec `/run` 32 MiB, all nosuid/nodev mode 1777; keep automatic read-only tmpfs provisioning but override its targets with a noexec 64 MiB `/dev`, an explicit `devpts` and an empty read-only `/dev/shm`, and mask `/run/secrets` with an empty read-only tmpfs. Never reintroduce `--read-only-tmpfs=false` or a writable `/dev/shm`. Verify actual flags and ephemeral lifetime at runtime.

Forward nonempty inherited variables by name from the base allowlist, the selected provider profile and the operator-listed names, keeping secret values out of generated engine-client arguments. Validate the YOLO, version, image and provider values and the listed names, and check opted-in integration directories, before engine queries. This does not hide values from engine inspection or container processes. Identity/path assignments remain explicit; image defaults or forwarded values must not override disabled delegation.

### Wrapper modes

The host must provide GNU coreutils `timeout` for bounded session cleanup. Use `--container-help` for wrapper help without engine or state side effects; normal `--help` remains an OpenCode argument. `--container-build` refreshes the versioned per-user image and then starts the selected session. `--container-shell` bypasses the OpenCode entrypoint and opens `/bin/bash`, omitting all OpenCode arguments. `--container-git-worktree` explicitly exposes the physical current directory's entire immediate parent read/write while retaining the original physical working directory and naming basename. Other OpenCode arguments keep their order and boundaries.

### Image inspection and build context

Keep the pinned versions in `Containerfile` (`OPENCODE_VERSION=1.18.3`, `OPENSPEC_VERSION=1.16.0`) and the base digest; change them only through the README "Updating pinned image inputs" procedure, re-reading the OpenCode provider metadata and permission merge behavior. `OPENCODE_CONTAINER_IMAGE` overrides the image name; builds pass no build arguments. Only image-exists status 1 triggers an automatic build, and only under exact `OPENCODE_CONTAINER_MAINTENANCE=1`; other engine/storage errors stop startup. Explicit refresh still performs all preflights first. Builds use the wrapper's physical recipe directory. The sole `.containerignore` defaults to denying all inputs and allows only root `Containerfile`, `.containerignore`, `network/relay.py` and `network/mux.py`. Update this allowlist deliberately for any future local COPY input; nested lookalikes, credentials, state and unrelated files must remain excluded.

### Session lifecycle

Names use the original physical workspace basename, sanitized, followed by an index above the highest running/stopped suffix. Parse at most nine digits in base ten (including `08`); ignore malformed/oversized suffixes. Reserve atomically with create and retry at most 20 confirmed collisions. Checked enumeration and collision errors stop startup. Never replace or remove another session to obtain a name. Private creation records and `io.opencode-container.session` identify owned full container IDs; stderr warnings must not become part of an ID. Never adopt or remove containers labeled with the earlier `io.opencode.*` prefix.

Stdin remains interactive for pipes/files as well as terminals; allocate a TTY only with terminal stdin and stdout. Preserve input/EOF for the attached client. Forward TERM/INT/HUP explicitly once and return 143/130/129. Preserve application exit statuses, including 125, and the first interruption status despite cleanup errors or repeated signals. Shutdown has one 20-second budget, including at most five seconds of application grace, bounded engine calls, interrupted-create reconciliation and local create/attach client termination/reaping. Repeated signals do not renew the deadline. Only verified owned IDs authorize removal.

Unresolved creation or removal is reported with an ID/session marker for manual engine inspection. Client cancellation does not prove engine request cancellation; engine loss or SIGKILL can leave residual resources. Use `podman ps --all --filter label=io.opencode-container.managed=true` and the reported session label to inspect them; never indiscriminately remove other managed sessions.

### Known portability gaps

- Quoted volume arguments support spaces/commas; colon/CR/LF bind paths are explicitly rejected.
- The npm install selects the x64 AVX2 or baseline OpenCode binary from the build host's CPU; build the image on the host that runs it.
- With keep-id, a caller UID that already exists in the base image (for example 1000, `node`) shows that image user name; `USER` is still set from the host.
- HOME/XDG must be absolute. State storage must enforce private Unix ownership/modes; choose native Linux storage if WSL/DrvFS cannot enforce them.
- Host SELinux policy may require explicit socket-access setup; the wrapper never weakens policy.

The runtime recipe fetches Debian packages over verified HTTPS only; the host CA reaches builds only as the `build-ca` secret. The recipe creates `/workspace` in a build step: never declare a `WORKDIR` that no build step creates.
