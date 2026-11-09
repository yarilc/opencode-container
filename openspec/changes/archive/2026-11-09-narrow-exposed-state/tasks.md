# Tasks

## 1. Early validation

- [x] 1.1 Add the validation block after option parsing and before `command -v podman` (D1):
  - `OPENCODE_CONTAINER_PROVIDER`: exact values, unset is `none`, empty or unknown values fail with the accepted list;
  - `OPENCODE_CONTAINER_ENV_VARS`: token syntax, reserved-name warning;
  - existence and physical resolution of opted-in integration directories.

  Verify with wrapper tests: each invalid case exits 1, names the variable or token, and leaves no fake-engine log entry and no XDG state directory.

## 2. Integration mounts (A06)

- [x] 2.1 Replace the `.claude`/`.agents`/`/etc/opencode` existence loop with the exact `OPENCODE_CONTAINER_AGENTS_DIR=1` and `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` read-only binds (D5). Verify with wrapper tests:
  - `~/.claude`, even with a `.credentials.json` file, never appears in the create arguments;
  - `.agents` is absent without opt-in or with `true`, and present read-only with `1`;
  - a missing opted-in directory fails before engine calls;
  - the delimiter-path case still mounts the opted-in `.agents` correctly.

## 3. Credential forwarding (A07)

- [x] 3.1 Split forwarding into the base allowlist, the provider profile table (D2) and the extra names (D3), with deduplication. Keep the delegation `CONTAINER_HOST` handling after forwarding. Verify with wrapper tests:
  - a matrix over all eight provider values, where only the selected profile's nonempty variables appear as `--env NAME`;
  - `GH_TOKEN`/`GITHUB_TOKEN` and the other providers' keys are absent by default;
  - extra names are forwarded;
  - a reserved extra name does not change `CONTAINER_HOST`;
  - no synthetic secret value appears in the fake-engine log.
- [x] 3.2 Add the migration notice (D4). Verify with wrapper tests:
  - with the provider unset and `OPENAI_API_KEY`/`GITHUB_TOKEN` set, exactly one notice names both and contains neither value;
  - `OPENCODE_CONTAINER_PROVIDER=none` or `=openai` suppresses it;
  - names in `OPENCODE_CONTAINER_ENV_VARS` are excluded;
  - the session status is unchanged.

## 4. Real-engine checks

- [x] 4.1 Update `tests/test_runtime.py`:
  - `$HOME/.claude` with a sentinel is absent in the session;
  - `$HOME/.agents` is absent without opt-in, and read-only with the sentinel when `OPENCODE_CONTAINER_AGENTS_DIR=1`;
  - with `OPENCODE_CONTAINER_PROVIDER=openai` a synthetic `OPENAI_API_KEY` arrives and a synthetic `ANTHROPIC_API_KEY` and `GH_TOKEN` do not;
  - an `OPENCODE_CONTAINER_ENV_VARS` name arrives.

  Verify that `bash tests/run-runtime.sh` passes on the host with no credentials or model requests.

## 5. Documentation and evidence

- [x] 5.1 Update `--container-help`, the README and `AGENTS.md`:
  - the four variables;
  - the provider table with its OpenCode 1.18.3 source;
  - `~/.claude` never mounted, and Vertex unsupported;
  - the migration steps: provider or `opencode auth login`, the integration opt-ins, moving skills or `CLAUDE.md`, and GitHub tokens through `OPENCODE_CONTAINER_ENV_VARS`.

  Verify that a help test lists the variables and provider values, and that `bash -n opencode-wrapper` and `git diff --check` pass.
- [x] 5.2 Run the full credential-free wrapper suite in the runner container and `bash tests/run-runtime.sh`, then add a dated `docs/validation.md` section. It covers the provider metadata source, results, initial failures and reruns, and the behavior changes. Verify that `openspec validate narrow-exposed-state --strict` passes.
- [x] 5.3 Mark A06 and A07 in `todo.md` with an implementation note naming the change and the evidence section. Verify the note is present.

## Workflow follow-up

- Archive, commit and merge when the user asks; the user pushes.
- Continue Wave 2 with OpenCode `align-wrapper-baseline`.
