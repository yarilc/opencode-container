# Design

## Context

See `proposal.md`. The reference is `claude-container` at tag `sandbox-ref-3` (commit `449ce60`). This change moves it to `sandbox-ref-5`. `add-network-egress` (merged as `73e3634`) copied `network/`, `setup/diagnostics.py` and the shared tests except `test_setup.py` and `test_alignment.py`, and integrated the restricted modes into `opencode-container.sh`. Codex completed the same step as `add-container-setup` on 2026-11-10; its archived change is the template.

**Observed in the reference.**

`setup/` takes every agent value from `agent/profile.json`:
- the wrapper and images;
- `config_dir_env`, `config_home` and `shared_dirs`;
- `approval_bypass_env`;
- the authentication methods.

`setup.py` behaves as follows:
- It proposes the first method of the profile as the default, which is `anthropic` here.
- It reports `Authentication pending. Supply <credential_env>` for API-key methods, and runs `login_args` only for login methods.
- It drives the wrapper through `--container-qualify`, `--container-shell` (the smoke check) and `--container-git-worktree`.
- The managed dispatcher calls `setup/launch.py`, which validates `setup.json`, exports the saved variables and execs the installed wrapper.

The shared tests:
- `tests/test_setup.py` runs the real wrapper. It checks:
  - `--container-setup` admission and help precedence;
  - the `setup required:` message;
  - managed launches;
  - the diagnostics filter;
  - a few literal wrapper messages, such as `cannot query Podman`.

  At import it computes `LOGIN_METHOD = next(...)` over methods with `login_args`, and uses that method in about fifteen places as "the provider method".
- `tests/test_alignment.py` scans `network/`, `setup/` and the shared tests for profile identifiers, and checks the wrapper against the profile.

**Observed in OpenCode.**
- The four methods have only `credential_env`, so `test_setup.py` fails at import.
- `setup/setup.py` itself handles API-key-only profiles.
- The wrapper already has:
  - the `"${session_helper[@]}" prepare|start|agent-args|stop` calls;
  - the `io.opencode-container.session` label;
  - the `localhost/opencode-cli`, `/opencode-home` and `opencode` values;
  - empty-equals-unset `OPENCODE_CONTAINER_STATE_DIR`, which setup relies on for shared state.
- The wrapper does not yet:
  - accept `--container-setup`;
  - print `setup required:`;
  - filter stderr.
- Its engine message is `cannot query launch engine`.

OpenCode needs no inner-sandbox override: it does not use `bwrap`.

## Goals / Non-Goals

**Goals:**
- `network/`, `setup/` and every shared test byte-identical to `sandbox-ref-5`. Unchanged `test_alignment.py` and `test_setup.py` pass against the OpenCode wrapper.
- Guided setup produces a working managed launcher in all three modes, with qualification and the smoke check passing on the WSL target.
- The OpenCode parity row is identical in the three ported repositories.

**Non-Goals:**
- Authenticated provider verification, which stays operator-run.
- Enabling real systemd user services in tests.
- An interactive login method for OpenCode.
- Ports for Pi and Antigravity.

## Decisions

### Fix the shared setup test in Claude first (`sandbox-ref-5`)

In `claude-container`, `tests/test_setup.py` gains:
- `PROVIDER_METHOD`: the first login method if any, otherwise the first API-key method;
- an optional `LOGIN_METHOD`, `None` when the profile has none.

The generic "provider method" uses switch to `PROVIDER_METHOD`. Only the check that the login arguments are executed is skipped when `LOGIN_METHOD` is `None`. The Claude and Codex profiles have login methods, so their test behavior is unchanged; `--setup` must still pass in both.

The steps are:
1. Merge in Claude and create the annotated tag `sandbox-ref-5`.
2. Recopy into Codex: update the manifest, tag and commit, and rerun `--shared` and `--setup`.
3. Copy here.

The procedure is the same as for `sandbox-ref-3`. The operator chose it on 2026-11-10 over adding a login method to OpenCode or keeping a per-agent test.

### A second shared-test fix found during apply (`sandbox-ref-5`)

Running `test_setup.py` against OpenCode showed that two checks created `<home>/<config_home>` or `<state>/<config_home>` without the parent directory. That works only for single-component homes such as `.claude` or `.codex`; OpenCode's `config_home` is `.config/opencode`. These checks were fixed in Claude the same way, tagged `sandbox-ref-5` (commit `3388b6e`) and adopted by Codex. This change copies from `sandbox-ref-5`.

The same run also showed a wrapper-side ordering difference. OpenCode created and validated `OPENCODE_CONTAINER_STATE_DIR` before the engine query, while the reference order (and this port's design) places engine verification before state. The wrapper now keeps only the lexical checks (absolute path, workspace overlap) before the engine, and creates and validates the directory afterward, before image operations. The `container-isolation` delta records this.

### The configuration variable also names the directory inside the session

The shared smoke check (`setup/smoke.py`) asserts that `os.environ[config_dir_env]` is writable inside the session. For Claude and Codex that variable (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`) is the native configuration variable on both sides. For OpenCode, `OPENCODE_CONTAINER_CONFIG_DIR` is a host-side override only. The wrapper therefore sets it in the session to the effective directory, `/opencode-home/.config/opencode`, as a nonsecret literal. It is reserved against `OPENCODE_CONTAINER_ENV_VARS`, and the host value is never forwarded. Changing the shared smoke contract was rejected: it would alter `setup.py` and `smoke.py` for all agents.

### Copy the remaining setup files and tests from the tag

`git -C ../claude-container archive sandbox-ref-5 setup tests/test_setup.py tests/test_alignment.py`, unpacked over the checkout. `tests/test_reference_copy.py` keeps its manifest, extended to the new files and moved to `sandbox-ref-5`. Both checks stay, as in Codex.

### Wrapper entry points follow the Claude and Codex wrappers

- `--container-setup` is handled after help and qualification. It must be used alone, needs a terminal on stdin and stdout and host Python 3, and then `exec`s `setup/setup.py`.
- The missing-mode message becomes `setup required: run bash <wrapper> --container-setup; use the managed launcher afterward or explicitly set OPENCODE_CONTAINER_NETWORK for an operator workflow (offline, provider, or unrestricted; unrestricted keeps the previous networking behavior)`, with the absolute wrapper path quoted by `printf %q`.
- The attached client's stderr goes through `setup/diagnostics.py` on a FIFO in the private session directory. The filter is reaped after the client within a one-second drain, inside the existing `shutdown` budget.
- Wrapper messages checked literally by the shared tests are aligned to the reference wording, for example `cannot query Podman or invalid engine response; ...`. Any further mismatch found in task 2.3 is resolved the same way, in the wrapper. A mismatch caused by shared code goes to Claude.

### Authentication is API-key only

Setup offers `anthropic`, `openai`, `openrouter` and `opencode-zen`, each mapped to its protected profile. After the sandbox is ready it reports `Authentication pending` with the variable to supply. It makes no model call and stores no key. Keys stored by `opencode auth login` keep working at runtime, but setup does not drive that command, because it is an interactive provider picker without a non-interactive form.

### Parity table

`docs/network-contract.md` here gets the five-wrapper table, copied from Claude, with the OpenCode row:
- contract adoption: ported from `sandbox-ref-5`, shared files unchanged;
- implementation: guard, multiplexed proxy, qualification and guided setup integrated;
- real enforcement: WSL ABI 3, all runtime modes and setup acceptance passed (with the date);
- authentication: pending operator API-key checks for the four profiles.

The same row replaces "Pending (profile-based port planned)" in `claude-container` and `codex-container`, in documentation-only commits.

### Setup runtime acceptance

`tests/test_setup_runtime.py` is ported from Codex with OpenCode names: `OPENCODE_CONTAINER_IMAGE`, `localhost/opencode-cli:latest`, `opencode-container`, and `--version` printing `1.18.3`. It runs setup under a pseudo-terminal against the real same-host service, with:
- a disposable `HOME`, installation and command path;
- a disposable proxy image;
- prepared runtime images routed by tag lookups.

It covers offline, provider and unrestricted installations and the managed launcher from another workspace. It does not enable systemd services, read real credentials or send model requests.

## Risks / Trade-offs

- **The Claude test change alters reference behavior.** Mitigation: Claude and Codex profiles keep a login method, so their selection is unchanged. `--setup` runs in all three repositories before the tag is used.
- **`test_setup.py` checks other Claude-only wrapper behavior.** Mitigation: run it early (task group 2). Wrapper-side mismatches are fixed in the wrapper; shared-code defects go to Claude.
- **The diagnostics FIFO changes stderr buffering.** Mitigation: the design is already measured in Claude and Codex, and the OpenCode TTY, pipe and signal tests are rerun, including OpenTUI in a PTY.
- **A new reference tag means another adoption in Codex.** Mitigation: only one shared test changes; the procedure is the same as for `sandbox-ref-3`.

## Migration Plan

1. New users run `bash ./opencode-container.sh --container-setup`, then use `~/.local/bin/opencode-container`.
2. Direct invocations keep working with an explicit `OPENCODE_CONTAINER_NETWORK`. Without one, they get the setup-required message.
3. Rollback:
   - setup keeps the last working release and restores it on failed activation;
   - at the repository level, check out `73e3634`.

## Open Questions

None.
