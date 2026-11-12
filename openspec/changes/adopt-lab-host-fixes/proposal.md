# Proposal

## Why

claude-container tag `sandbox-ref-11` makes the sandbox work on a Rocky Linux 9
lab host (Podman 5, crun 1.27, partial cgroup delegation, `ipv6.disable=1`,
RHEL `/run/secrets` mount, domain UID) and on a newer WSL host. Codex adopted
it in its own change and then passed the operator's Rocky setup. OpenCode
still uses `sandbox-ref-10` with its own launcher and recipe. On those hosts
it fails in the same ways:

- it rejects the `unix://` socket path;
- it requests undelegated budgets;
- the guard refuses the RHEL secrets mount;
- the terminal cannot attach;
- the image build needs outbound port 80.

The recipe also ends with `WORKDIR /workspace`, which Codex showed to break
the qualification gate for a domain UID under `--userns=keep-id`.

## What Changes

- **Adopt `sandbox-ref-11`** with `tools/propagate.py`: the 21 shared
  `network/`, `setup/` and test files, the reference manifest and the
  current-state documents. This brings, unchanged:
  - controller-dependent budgets in qualification, smoke and proxy;
  - IPv6-less qualification;
  - the guard's read-only `/run/secrets` acceptance;
  - the proxy address-family fallback;
  - the setup socket and CA build-secret handling.
- **Launcher (`opencode-container.sh`)**, ported from the reference, as
  in Codex:
  - reduce a `unix://` host socket report to its pathname;
  - request each budget only when the engine reports its cgroup
    controller. Announce each unenforced budget, and at inspection require
    enforced budgets to match and unenforced ones to be absent;
  - mask `/run/secrets` with an empty read-only tmpfs;
  - stop disabling automatic read-only tmpfs. Mount a `noexec` `/dev`
    tmpfs, `devpts` and an empty read-only `/dev/shm`;
  - pass the selected host CA to the image build as the `build-ca`
    secret.
- **Runtime image recipe**:
  - fetch Debian packages only over verified HTTPS, bootstrapped from the
    base image's Node.js roots plus the optional `build-ca` secret;
  - `.containerignore` admits `/podman-build-secret*`;
  - the package step creates `/workspace`, so Podman never creates or
    chowns the image working directory at container start;
  - the pin tests reject plain-HTTP sources, disabled verification and a
    `WORKDIR` that no build step creates.
- **Wrapper tests**:
  - fixtures for the shared-code imports and the controller query;
  - assertions for the new mounts, budgets, socket and build secret.
- **BREAKING (policy):**
  - a budget whose controller is not delegated is not enforced;
  - `/dev` becomes a writable `noexec` tmpfs.
- **BREAKING (installation):** the qualification identity, code digests and
  runtime image identity change. Restricted installations must rebuild and
  rerun setup.
- **Unchanged:**
  - `/tmp` stays executable for OpenTUI at 512 MiB;
  - `/var/tmp` (512 MiB) and `/run` (32 MiB) stay `noexec`;
  - the home tmpfs, budget values and validation;
  - the provider profiles;
  - the guard's `/run/secrets` rule, kept exactly as in the reference.
- **Not in scope:** passing `--workdir /` to the qualification gate
  containers in `network/qualify.py`. It is shared code, tracked for a
  claude-container change and tag `sandbox-ref-12`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `container-isolation`:
  - explicit ephemeral storage no longer disables automatic provisioning;
  - budgets are enforced per delegated controller and verified as enforced
    or absent;
  - the secrets mask;
  - terminal-compatible device mounts.
- `container-podman-access`: accepts a `unix://` host socket report.
- `container-session`:
  - the qualification identity binds the enforced budget sets;
  - unenforced budgets are announced.
- `container-setup`:
  - smoke and plan follow the enforced set;
  - the host CA covers the setup package fetches.
- `network-egress`:
  - proxy budgets per delegated controller;
  - IPv6-less qualification;
  - the bootstrap admits only the read-only secrets mask;
  - the proxy skips unsupported address families.
- `runtime-image`:
  - HTTPS package sources and the pinned trust bootstrap;
  - the image working directory exists in the image.

## Impact

- Shared files from the tag, through the tool: `network/`, `setup/` and the
  shared tests, plus `tests/test_reference_copy.py`, `README.md`,
  `AGENTS.md`, `docs/setup.md` and `docs/network-contract.md`.
- OpenCode-owned files:
  - `opencode-container.sh`, `Containerfile`, `.containerignore`;
  - `tests/test_wrapper.py`, `tests/test_image_pins.py`;
  - `README.md`, `AGENTS.md`, `docs/validation.md`.
- `main` is already two commits ahead of `origin/main` (the parity-table
  alignment). That is unrelated and stays as it is.
- Existing OpenCode installations must rebuild and rerun setup or
  qualification.
