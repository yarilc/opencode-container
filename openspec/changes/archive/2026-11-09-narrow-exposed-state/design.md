# Design

## Context

`opencode-wrapper` (458 lines) runs in this order:
1. parses the `--container-*` options;
2. checks Podman and GNU `timeout`;
3. validates the launch engine and delegation;
4. builds the bind list:
   - the workspace and the four private XDG directories;
   - a loop that mounts `$HOME/.claude`, `$HOME/.agents` and `/etc/opencode` read-only when they exist;
   - the delegated socket;
5. assembles `run_args` and appends `--env NAME` for every nonempty variable in one fixed allowlist;
6. inspects or builds the image;
7. creates and starts the session.

The allowlist contains, after the base names, every provider key plus `GH_TOKEN`/`GITHUB_TOKEN`.

The provider variable sets below come from the provider metadata embedded in the pinned OpenCode 1.18.3 binary (`ghcr.io/anomalyco/opencode:1.18.3`, `env:[...]` entries), read on 2026-11-09:
- `anthropic`: `ANTHROPIC_API_KEY`;
- `openai`: `OPENAI_API_KEY`;
- `google`: `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `GEMINI_API_KEY`;
- `openrouter`: `OPENROUTER_API_KEY`;
- `amazon-bedrock`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_BEARER_TOKEN_BEDROCK`;
- `azure`: `AZURE_RESOURCE_NAME`, `AZURE_API_KEY`;
- `opencode` (Zen): `OPENCODE_API_KEY`.

The binary also reads `AWS_SESSION_TOKEN` and `OPENAI_BASE_URL`, which the current allowlist forwards. The current `AZURE_OPENAI_API_KEY`/`AZURE_OPENAI_ENDPOINT` are not the variables of OpenCode's `azure` provider. OpenCode also reads `~/.claude/CLAUDE.md` and `~/.claude/skills` for Claude Code compatibility.

## Goals / Non-Goals

**Goals:**
- No host directory reaches the session unless the operator asks for it, apart from the workspace and the OpenCode state.
- Credential forwarding is limited to one provider plus operator-listed names, as in the other wrappers.
- Existing users get a clear, value-free notice instead of silent breakage.

**Non-Goals:**
- Network provider profiles, the setup questionnaire and protected launch preferences (C06/C10, Wave 3). `OPENCODE_CONTAINER_PROVIDER` is the value the setup will later write.
- Google Vertex. Its profile needs `GOOGLE_APPLICATION_CREDENTIALS`, a host file that is not mounted. An operator can still list its variables explicitly, but a file path is useful only if it points inside a mounted path. This is documented as unsupported.
- Mounting a selected `~/.claude` subpath. The operator chose plain removal.
- The remaining A01/A02/A08/A09 alignment and the A03–A05/A11 image and baseline work, which are later Wave 2 changes.

## Decisions

### D1: Validate early
A new block runs right after option parsing and before `command -v podman`. It validates `OPENCODE_CONTAINER_PROVIDER` and the `OPENCODE_CONTAINER_ENV_VARS` tokens. It also checks that an opted-in integration directory exists and resolves it physically. Help still exits during parsing. This follows the "validate before any engine call" order used for the budgets in Claude, Codex and Antigravity.

### D2: Provider table in Bash
A `case` statement maps each accepted value to a fixed list of names. The lists are the OpenCode 1.18.3 metadata, plus the two names the current allowlist forwards and the binary reads:
- `AWS_SESSION_TOKEN` is required for temporary AWS credentials;
- `OPENAI_BASE_URL` is used by OpenAI-compatible endpoints.

Values are exact and lowercase, using OpenCode's own provider IDs so they map onto the Wave 3 profiles. An unset variable means `none`; an empty value is invalid, matching how the reference wrappers treat empty budgets.
- Alternative: a comma list of several providers. Rejected because the Wave 3 profile is single-upstream. Additional keys can go in `OPENCODE_CONTAINER_ENV_VARS`.

### D3: Three forwarding sources, by name
The forwarding sources, in order:
1. the base names unchanged: `TERM COLORTERM LANG LC_ALL`, the six proxy names, and the `OPENCODE_*` configuration and feature names already listed;
2. the profile names;
3. the validated extra names.

Each nonempty variable is added once as `--env NAME`, with duplicates removed. Reserved names in the extra list are skipped with a warning, following Pi's semantics but visibly: `HOME`, `USER`, the four XDG bases, `CONTAINER_HOST` and `CONTAINER_CONNECTION`. The delegation `--env CONTAINER_HOST=…`/`--unsetenv CONTAINER_HOST` still comes after forwarding, so nothing overrides it.

### D4: Migration notice
When `OPENCODE_CONTAINER_PROVIDER` is unset, the wrapper collects the nonempty names from the legacy set that are not in the extra list. The legacy set is every profile name plus `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `GH_TOKEN` and `GITHUB_TOKEN`. If any are found, it prints one line to stderr before engine queries:

`opencode-wrapper: not forwarding NAME…; set OPENCODE_CONTAINER_PROVIDER=<provider> or list names in OPENCODE_CONTAINER_ENV_VARS (OPENCODE_CONTAINER_PROVIDER=none silences this notice)`

The notice is informational and never changes the exit status.
- Alternative: no notice. Rejected, because users with environment keys would see an unexplained authentication failure inside OpenCode.

### D5: Opt-in integrations
The existence loop is replaced with two exact checks:
- `OPENCODE_CONTAINER_AGENTS_DIR=1` mounts `$HOME/.agents`;
- `OPENCODE_CONTAINER_SYSTEM_CONFIG=1` mounts `/etc/opencode`.

Both use `add_bind … ro` from the physical source at the original path, which keeps the conflict and colon checks. `~/.claude` has no code path at all. The exact-`1` rule matches `OPENCODE_CONTAINER_PODMAN`.

### D6: Tests
**`tests/test_wrapper.py`** (fake engine) gets:
- `~/.claude` never mounted;
- integrations mounted only with exact opt-in, with a failure for a missing directory and no engine call;
- a provider matrix with one case per value;
- an invalid provider;
- the notice present, suppressed by `none` and by a provider, and excluding names in the extra list;
- extra names, invalid tokens and reserved names;
- secret values never in the fake engine log;
- help.

The existing `test_mount_paths_and_boundaries` and `test_tmpfs_and_named_environment` are updated.

**`tests/test_runtime.py`** gets:
- the `.claude`/`.agents` read-only check replaced: `.claude` is absent, and `.agents` is read-only only with the opt-in;
- a provider forwarding check with synthetic values.

Unit suites run in the host runner container, as for Codex and Antigravity, because this agent sandbox has a `noexec` `/tmp`.

## Risks / Trade-offs

- **Users relying on environment keys lose access silently inside OpenCode.** The D4 notice names the variables, and the README gives the migration.
- **Users relying on Claude-compatible skills or `CLAUDE.md`.** The README documents moving them to `~/.agents/skills` with the opt-in, or to the OpenCode configuration directory.
- **The OpenCode provider metadata changes in a later pinned version.** The table records its source version, and the version-update procedure (A03) must re-read it.
- **Several providers in one session.** Operators list the extra keys in `OPENCODE_CONTAINER_ENV_VARS`.

## Migration Plan

1. Implement on branch `narrow-exposed-state`. Unit suites run in the runner container; the real-engine suite runs with `bash tests/run-runtime.sh`.
2. Users set `OPENCODE_CONTAINER_PROVIDER`, or use `opencode auth login`, and opt in to integrations as needed. No image rebuild or state migration is required.
3. Rollback: revert the commit. No state format changes.
