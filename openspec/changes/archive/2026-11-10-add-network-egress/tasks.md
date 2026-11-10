# Tasks

## 1. Copy the shared components from `sandbox-ref-3`

- [x] 1.1 Create branch `add-network-egress` from `main`. Use `git -C ../claude-container archive sandbox-ref-3` (`sandbox-ref-2` initially; `tests/test_guard.py` recopied from `sandbox-ref-3`) to unpack:
  - `network/`, without `bin/` and `__pycache__`;
  - `setup/diagnostics.py`;
  - the shared tests listed in Claude's `tests/test_alignment.py`, except `test_alignment.py` and `test_setup.py`.

  Verify with `diff -r` against a `sandbox-ref-3` worktree of Claude: no differences.
- [x] 1.2 Add the per-agent `tests/test_reference_copy.py`, adapted from Codex:
  - the SHA-256 manifest;
  - failure on a changed, missing or extra file;
  - the scan for the profile identifiers;
  - an optional `diff -r` against a sibling checkout.

  Verify that it passes, and that it fails on an injected byte change and on an injected `opencode` literal, each made in a scratch copy. If `anthropic`, `openai` or `openrouter` matches a shared file, drop that identifier from the profile and record why.

## 2. Measure the OpenCode-specific unknowns

- [x] 2.1 Build a static inventory of the installed `opencode-ai@1.18.3` binary and the official OpenCode documentation. Record in `docs/validation.md`, dated and with the version:
  - the OpenCode Zen API hosts;
  - the hosts of the model catalog, share, auto-update, default-plugin and LSP-download features;
  - the provider base URLs used for Anthropic, OpenAI and OpenRouter;
  - which `opencode auth login` methods need a browser callback.
- [x] 2.2 Verify each optional-traffic control in 1.18.3 with a credential-free run against a denying proxy or no network:
  - `OPENCODE_DISABLE_AUTOUPDATE`;
  - `OPENCODE_DISABLE_DEFAULT_PLUGINS`;
  - `OPENCODE_DISABLE_LSP_DOWNLOAD`;
  - `OPENCODE_DISABLE_MODELS_FETCH`;
  - the share control.

  Check whether each environment value wins over a conflicting `opencode.json` and `OPENCODE_CONFIG_CONTENT`. Record each supported control, each missing one and each precedence result.
- [x] 2.3 With the synthetic TLS fixture (a `CA:FALSE`, `serverAuth` leaf certificate) and a local CONNECT proxy, check that the OpenCode Bun client:
  - honors `HTTPS_PROXY`/`https_proxy` and the loopback `NO_PROXY` for HTTPS and server-sent event streaming;
  - trusts the bundle through `NODE_EXTRA_CA_CERTS` and/or `SSL_CERT_FILE`.

  Record the variables Bun honors and any transport that bypasses the proxy, which must then fail closed.
- [x] 2.4 With an operator-built guard (task 3.2), run a disposable `localhost/opencode-cli` container with `--cap-drop=all`, no-new-privileges and the guard in offline mode:
  - OpenTUI in a PTY, starting, connecting to its local server and quitting;
  - `opencode run` with a bash-tool command against a stub;
  - any preinstalled LSP or formatter.

  Record any Unix-socket, `bubblewrap` or download dependency and the documented outcome. Never weaken the guard.
- [x] 2.5 Run the guard runtime fixtures with OpenCode's executable `/tmp`, `/var/tmp` and `/opencode-home` tmpfs layout and the fixed state binds. Verify that layout validation passes. If it fails, stop and report the shared-code finding rather than patching `network/`.

## 3. Agent profile, policy and operator artifacts

- [x] 3.1 Write `agent/profile.json` with the values from design.md. Write `agent/policies/default.json` with:
  - `anthropic-api`, `openai-api`, `openrouter-api` and the measured `opencode-zen`;
  - revision `opencode-2026-11-10-v1`, `source_date` and `sources`;
  - `tested.cli` `1.18.3`, with authentication marked unverified.

  Verify that `python3 -I network/agent_profile.py` validation, `tests/test_agent_profile.py` and `tests/test_network_policy.py` pass.
- [x] 3.2 Build the guard toolchain image `localhost/opencode-guard-toolchain:development`. Run `OPENCODE_CONTAINER_MAINTENANCE=1 bash network/build-guard.sh` into a protected native `network/bin` of a disposable installation. Build `localhost/opencode-egress` from `network/Containerfile` and record its image ID. Verify the guard SHA-256 (it must equal Claude's) and the guard runtime mode of the runner.
- [x] 3.3 Run the copied shared suites in the runner:
  - `test_network_policy`, `test_mux`, `test_tls_client_hello`, `test_tls_proxy`;
  - `test_platform`, `test_qualification`, `test_guard`, `test_session`;
  - `test_network_feasibility`, `test_agent_profile`.

  They must all pass without edits to shared files.

## 4. Runtime image and test runner

- [x] 4.1 Add `COPY network/relay.py network/mux.py /opt/sandbox-egress/` to `Containerfile`, and admit only these two files plus `Containerfile` and `.containerignore` in `.containerignore`. Extend `tests/test_image_pins.py` so it requires `OPENCODE_VERSION` to equal the policy's `tested.cli` and names both versions on a mismatch. Verify:
  - the pin tests, including an injected divergence;
  - the four-file build-context probe;
  - a rebuilt image whose `opencode --version` reports 1.18.3.
- [x] 4.2 Extend `tests/run-runtime.sh` to the Codex mode set:
  - `--wrapper`, `--shared`;
  - `--network-feasibility`, `--network-policy`, `--network`, `--mux`, `--guard`, `--guard-idle`, `--qualification`;
  - the default runtime mode.

  It runs in the OpenCode image with a disposable native volume and an executable `/tmp`, and mounts the project read/write only where the shared suites need it. Verify that each mode starts and reports its suite.

## 5. Wrapper integration

- [x] 5.1 Mode admission:
  - parse `OPENCODE_CONTAINER_NETWORK`; an unset or empty value stops before engine calls, naming the three values and `unrestricted` as the previous behavior;
  - unknown values fail;
  - `OPENCODE_CONTAINER_PODMAN=1` is rejected in restricted modes;
  - help gains the new options, variables, migration notes and the provider disclosure.

  Verify with `test_wrapper.py` cases for each combination of OpenCode, shell, build, worktree and YOLO.
- [x] 5.2 Maintenance gate: image builds, automatic or explicit, require the exact `OPENCODE_CONTAINER_MAINTENANCE=1`. Without it the wrapper stops before any pull or build. Restricted preconditions are checked before image operations. Verify with fake-engine cases:
  - image present;
  - image absent, with and without authorization;
  - explicit build, with and without authorization;
  - inspection error;
  - an invalid policy with authorization.
- [x] 5.3 State and CA:
  - the fixed shared paths below `$HOME`;
  - host `XDG_*_HOME` ignored;
  - `OPENCODE_CONTAINER_CONFIG_DIR` validated and mounted at `/opencode-home/.config/opencode`;
  - the conflict between that variable and `OPENCODE_CONTAINER_STATE_DIR`;
  - `OPENCODE_CONTAINER_TRUST_HOST_CA` and `OPENCODE_CONTAINER_CA_BUNDLE`, giving a read-only `/opencode-home/ca/bundle.pem` plus the four variables, with the private `ca` parent in isolated state.

  Verify with `test_wrapper.py` cases for:
  - both state modes, the override and the conflict;
  - a set `XDG_CONFIG_HOME`;
  - a privacy failure and an escaped symlink;
  - CA off, `1` and `maybe`;
  - an explicit or missing bundle, and no default bundle.
- [x] 5.4 Restricted forwarding:
  - no host proxy or CA variables in offline and provider modes;
  - authoritative network names in `OPENCODE_CONTAINER_ENV_VARS`;
  - offline forwards no provider variable;
  - provider forwards only the profile's credential;
  - the `OPENCODE_CONTAINER_PROVIDER` compatibility check;
  - no `OPENAI_BASE_URL`;
  - protected optional-traffic values appended after forwarding (from task 2.2), in OpenCode and shell modes.

  Verify with `test_wrapper.py` cases for every profile, a mismatched provider and inherited conflicting values. The unrestricted cases must be unchanged.
- [x] 5.5 Restricted preparation, in the Claude order:
  1. platform queries;
  2. `session.py prepare` with the workspace, the four state paths (or the isolated home) and `/opencode-home` as writable paths and mount targets;
  3. the immutable runtime image ID;
  4. proxy image acquisition, only under maintenance and by digest;
  5. `qualify.py check`;
  6. `session.py start`, then `agent-args`, then container creation with the restricted arguments;
  7. `session.py stop` within the remaining shutdown budget, terminating an in-flight `start` by process group.

  The startup report gives the mode, profile and policy revision. Verify with fake-engine `test_wrapper.py` cases for:
  - argument assembly and the order of operations;
  - interrupted start;
  - preserved exit status and owned cleanup.
- [x] 5.6 Add `--container-qualify` (alone, offline by default, no application command) and `--container-qualify-probe` using `network/qualify.py`, with the Claude argument rules. Verify with fake-engine cases and with `tests/test_qualification.py`.
- [x] 5.7 Unrestricted regression: with `OPENCODE_CONTAINER_NETWORK=unrestricted` and maintenance where needed, the existing `test_wrapper.py` and `test_runtime.py` cases pass unchanged, apart from the added mode and maintenance variables and the fixed state paths. These cover lifecycle, delegation, YOLO, provider forwarding, budgets and workspace. Verify with the full unit suite in the runner.

## 6. Runtime acceptance with real rootless Podman

- [x] 6.1 Add `tests/test_network_runtime.py` and `tests/network_tls_fixture.py`, adapted from Codex with OpenCode names and a synthetic OpenAI-compatible or Anthropic-compatible streaming endpoint. Verify that every runner mode from task 4.2 passes on the WSL target with disposable native state.
- [x] 6.2 Offline acceptance through `opencode-container.sh`, after `--container-qualify`:
  - no IPv4, IPv6, DNS or UDP egress;
  - host socket and abstract socket denial;
  - loopback and connected pairs work;
  - files persist with caller ownership;
  - OpenTUI starts and quits in a PTY.

  Verify through the runtime suite.
- [x] 6.3 Provider acceptance with controlled fixtures:
  - matching CONNECT and SNI pass with certificate verification;
  - mismatched SNI is rejected with zero bytes forwarded;
  - denied authority, redirect, IP-literal and deceptive-suffix requests fail;
  - proxy loss fails closed;
  - CA off and on behave as specified;
  - the proxy budgets and hardening are verified.

  Also check that `opencode run`, against a synthetic provider configured through a profile-matching fixture host, streams a response and executes a tool through the relay with no real credentials. Verify through the runtime suite.
- [x] 6.4 Concurrency and cleanup: run two concurrent OpenCode provider sessions, plus one Codex or Claude restricted session if a sibling installation is available. Verify that:
  - labels and resources are distinct;
  - each session cleans up only its own resources;
  - nothing is left over (`podman ps -a`, networks and volumes filtered by `io.opencode-container`).

  Do not touch pre-existing containers or networks.

## 7. Documentation and evidence

- [x] 7.1 Update `README.md` with:
  - network modes and migration, including the fixed state paths and `OPENCODE_CONTAINER_CONFIG_DIR`;
  - maintenance, CA and `--container-qualify`;
  - the operator build inputs;
  - the four provider profiles and the credential rules;
  - provider limits, the residual exfiltration disclosure for every profile host, share and the hosted-tools boundary;
  - the documented qualification behaviors (reboot, unidentifiable LSM policy, empty release inventory);
  - the browser-callback login limitation;
  - local tool compatibility (task 2.4).

  Update `AGENTS.md` with the shared-file rule and the test commands. Verify with markdownlint on the changed files and `git diff --check`.
- [x] 7.2 Add `docs/network-contract.md`, modeled on Codex:
  - the reference tag and commit;
  - the intentional differences, limited to `agent/` and per-agent files;
  - the mode and profile contract and the limits;
  - the port status.

  The copied `network/README.md` stays unchanged. Verify that the links resolve and that markdownlint passes.
- [x] 7.3 Record in `docs/validation.md`:
  - the target, Podman version, guard digest, image IDs and test results by mode;
  - the measured host inventory, the optional-traffic controls, the Bun proxy and CA behavior, and the local tool outcomes;
  - the operator-run authenticated checks (each profile: request, streaming, long-lived request, OpenTUI), marked unavailable until the operator runs them.

  Verify that every claim in the README has a matching evidence entry.
- [x] 7.4 Final verification:
  - `bash -n opencode-container.sh` and ShellCheck;
  - the full unit suite in the runner, including `image-smoke.sh`;
  - all runtime modes;
  - `openspec validate add-network-egress --strict`;
  - `git diff --check`.

  Update the `todo.md` items with their status and evidence location: N01–N15, C01–C09, C11 and C13, and the obsolete Alpine and default-offline notes.

## Workflow follow-up

- Operator-run authenticated checks for each profile before declaring it verified; results go into `docs/validation.md`.
- `/opsx:archive`, then commit and merge into `main`; the user pushes.
- Next change: `add-container-setup` for OpenCode (C10, `setup/`, `test_alignment.py`, `test_setup.py`, `docs/setup.md`, the missing-setup message, the OpenCode parity row in Claude and Codex).
