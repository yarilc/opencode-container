# Proposal

## Why

`opencode-container` is on `sandbox-ref-28`, eight reference tags behind `sandbox-ref-36`. Adopting `sandbox-ref-36` aligns OpenCode's shared launcher, setup, qualification, and toolchain library with the reference baseline and replaces host Podman delegation with a private, session-owned container engine for image toolchains (including nested systemd containers).

## What Changes

- Adopt the shared files from `sandbox-container` tag `sandbox-ref-36` (commit `ce2c9d28873838a4ac541da34edaf7d8b5264be4`) via `tools/propagate.py` (29 modified, 17 added, 0 removed) and update `tests/test_reference_copy.py` to the 92-file manifest.
- **BREAKING**: Remove host Podman delegation in every mode. Exact `OPENCODE_CONTAINER_PODMAN=1` now stops session launches and build-only operations before engine access with migration guidance; other values are ignored. Rerunning `--container-setup` drops saved delegation settings and migrates preferences to schema 3.
- Introduce a private, session-owned rootless Podman engine (`localhost/opencode-cli-engine:latest`) whenever the enabled toolchain library contains at least one image toolchain, sharing the session's network namespace, mounting only the workspace and read-only image store, declaring its four startup capabilities in `io.containers.capabilities`, and supporting nested systemd containers and explicit nested limits on eligible engines.
- Adopt the shipped release toolchain catalog, host-side HTTPS archive provisioning, image-toolchain recipes, Windows toolchain path translation, in-container process rlimit fallback, guarded terminal availability probing, and runtime-test portability improvements.
- Adapt OpenCode's wrapper, runtime, setup, and network tests (`tests/run-runtime.sh`, `tests/test_wrapper.py`, `tests/test_runtime.py`, `tests/test_network_runtime.py`, `tests/test_setup_wrapper.py`, `tests/test_setup_runtime.py`) and current documentation (`README.md`, `AGENTS.md`, `docs/setup.md`, `docs/network-contract.md`, `docs/validation.md`), while preserving OpenCode's pinned runtime image (`1.19.5` / OpenSpec `2.0.0`), provider profiles (`anthropic-api`, `openai-api`, `openrouter-api`, `opencode-zen`), `OPENCODE_CONTAINER_YOLO`, `OPENCODE_CONTAINER_PROVIDER`, and optional mounts (`OPENCODE_CONTAINER_AGENTS_DIR`, `OPENCODE_CONTAINER_SYSTEM_CONFIG`).
- Exclude `add-read-only-dependency-mirror` (whose code landed on `sandbox-container/main` after `sandbox-ref-36`) from this adoption.

## Capabilities

### New Capabilities

- `session-container-engine`: Private, session-owned rootless container engine lifecycle, loopback endpoint, network boundary, workspace/store mounts, budgets, hardening exceptions, qualification, cgroup delegation, nested systemd containers, and capability declaration.

### Modified Capabilities

- `container-isolation`: Forbid host Podman sockets in sessions, keep all capabilities dropped on session containers, document host `/sys` and device-mount constraints with engines, and update in-container process rlimit fallback and verification.
- `container-launcher`: Move launch-engine and response-boundary validation from the retired `container-podman-access` spec and add refusal of leftover `OPENCODE_CONTAINER_PODMAN=1`.
- `container-podman-access`: Retire all host Podman delegation requirements (with `retire_capabilities: true` in `.openspec.yaml`) after preserving launch-engine verification in `container-launcher`.
- `container-session`: Update network-mode admission after delegation removal and keep read-only engine queries bounded across launch and engine operations.
- `container-setup`: Prepare the session engine image, migrate saved delegation preferences to schema 3, drop delegation prompts, re-verify toolchains on release updates, and align Windows setup guidance.
- `network-egress`: Update runtime-mode descriptions without delegation, proxy in-container process rlimit fallback, and common contract documentation.
- `runtime-image`: Document separate runtime (`localhost/opencode-cli:latest`) and session engine (`localhost/opencode-cli-engine:latest`) images.
- `shared-launcher`: Align OpenCode's wrapper test boundary with the shared `sandbox-ref-36` launcher suite.
- `toolchain-library`: Add the release recipe catalog, host-side archive fetching, operator recipe path refusal, image entries and read-only image store, idle-engine checks on image removal, and Windows drive-path handling.
- `windows-launcher`: Update network-mode and saved-delegation refusal requirements to match the removal of host delegation and adoption of the session engine.

## Impact

- Shared files in `launcher/`, `network/`, `setup/`, and shared test files under `tests/` become byte-identical to `sandbox-ref-36`.
- OpenCode-specific runtime, wrapper, setup, and network tests and docs are updated to remove legacy host-socket delegation assertions and cover the private session engine.
- `Containerfile`, `agent/profile.json`, `agent/launcher.sh`, `agent/policies/*`, `opencode-container.ps1`, and `.gitattributes` keep their existing OpenCode pins and behavior.
- Existing managed installations rerun `--container-setup` to migrate saved preferences, build `localhost/opencode-cli-engine:latest`, and refresh qualification records.
- Verification in the working session covers host unit/alignment/manifest checks and OpenSpec validation; full real-engine runs on Linux/WSL (`tools/adoption-run.sh`) and Windows (`tools/windows-validate.ps1`) are tracked as post-closure follow-up per `AGENTS.md`.
