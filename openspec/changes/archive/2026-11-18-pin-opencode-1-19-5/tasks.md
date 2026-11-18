## 1. Baseline

- [x] 1.1 Record the current image ID and the reported versions (1.18.3 and 1.16.0). Run the pin tests and the credential-free unit suite on the unchanged tree, and keep the results as the baseline for the old-test gate.

## 2. Pins and policy

- [x] 2.1 In `Containerfile`, set `OPENCODE_VERSION=1.19.5` and `OPENSPEC_VERSION=2.0.0`. Leave the base digest unchanged.
- [x] 2.2 In `agent/policies/default.json`, set revision `opencode-2026-11-18-v1` and `tested.cli` to `1.19.5`, with the measurement notes and dates.
- [x] 2.3 Update every test that names the version:
  - `tests/image-smoke.sh`;
  - `tests/test_image_pins.py`: the diverging CLI becomes `1.19.6`, and the OpenSpec range follows the new pin;
  - `tests/test_network_runtime.py`, `tests/test_runtime.py` and `tests/test_setup_runtime.py`.

## 3. Build and measure

- [x] 3.1 Rebuild with `OPENCODE_CONTAINER_NETWORK=unrestricted OPENCODE_CONTAINER_MAINTENANCE=1 ./opencode-container.sh --container-build`. The build checks the versions: `opencode` must report 1.19.5 and OpenSpec must report 2.0.0.
- [x] 3.2 Re-read the provider metadata of 1.19.5 for the four providers, and update the `OPENCODE_CONTAINER_PROVIDER` table if needed.
- [x] 3.3 Check two behaviors:
  - `OPENCODE_PERMISSION={"*":"allow"}` still merges after the configuration files and overrides `ask` and `deny`;
  - `--auto` is still accepted only on the default interface and `run`.
- [x] 3.4 Run the static endpoint inventory and the logging-proxy runs for the four profiles with dummy keys, with and without the five `OPENCODE_DISABLE_*` controls. Compare with the 1.18.3 record, including the sharing and auto-update requests. If a required host changed, stop and agree on a `network-egress` delta.
- [x] 3.5 Requalify with `--container-qualify`, then start OpenTUI interactively and quit. It must show the prompt, with no rendering error.

## 4. Suites

- [x] 4.1 Run the full credential-free suite (unit, wrapper, shared, setup, setup-runtime, qualification, network, guard and default runtime). Classify any failing old test with the gate and resolve it.
- [x] 4.2 Run the offline OpenSpec round trip from the reference change in shell mode.
- [x] 4.3 Run `bash ../sandbox-container/tools/shellcheck.sh .` and `git diff --check`. Known shared-file findings stay as recorded; this change adds none.

## 5. Record

- [x] 5.1 Update `AGENTS.md` and `README.md`, and in `docs/network-contract.md` the "Measured on" profile rows and the optional-traffic notes on sharing and auto-update.
- [x] 5.2 Add a dated entry to `docs/validation.md`. It records:
  - the version rule, and why 2.x is deferred;
  - the versions, provider metadata, YOLO and `--auto` results;
  - the inventory diff and the OpenTUI and suite results.
- [x] 5.3 Run `openspec validate pin-opencode-1-19-5 --strict`, then commit on `main`.

## Workflow follow-up

- The operator pushes `main` and reruns `--container-setup` on the three hosts.
- Archive with `/opsx:archive pin-opencode-1-19-5`. Sync specs only if a delta was added.
- A dedicated change for OpenCode 2.x (2.3.0 or later), distributed as a GitHub binary.
- Real-key checks go to the deferred authenticated pass.
