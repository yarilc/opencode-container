# Proposal: Narrow the host state exposed to OpenCode sessions

## Why

Two kinds of host state reach every OpenCode session without the operator asking for them:
- **Directories:** the wrapper mounts `~/.claude` read-only whenever it exists. That directory holds Claude Code credentials (`.credentials.json`) and sessions. `~/.agents` and `/etc/opencode` are mounted the same way.
- **Credentials:** the wrapper forwards every set variable from a broad allowlist. The list covers Anthropic, OpenAI, Google/Gemini, OpenRouter, AWS and Azure, plus `GH_TOKEN`/`GITHUB_TOKEN`.

No other wrapper exposes another agent's state or more than its own provider credentials. This change closes todo items A06 and A07 before the remaining Wave 2 alignment and the Wave 3 network port.

## What Changes

- **BREAKING** The wrapper no longer mounts `~/.claude`, with no opt-in. OpenCode loses its Claude Code compatibility sources inside the container: the global `~/.claude/CLAUDE.md` and `~/.claude/skills`. Operators can place instructions and skills in OpenCode's own configuration or in `~/.agents`.
- **BREAKING** `~/.agents` and `/etc/opencode` are mounted read-only only on explicit opt-in:
  - `~/.agents` needs exact `OPENCODE_CONTAINER_AGENTS_DIR=1`;
  - `/etc/opencode` needs exact `OPENCODE_CONTAINER_SYSTEM_CONFIG=1`.

  Any other value leaves the directory unmounted. An opt-in for a missing directory stops before any engine query.
- **BREAKING** Provider credentials are forwarded only for the provider selected with `OPENCODE_CONTAINER_PROVIDER`. Its values are OpenCode's own provider IDs, each with a fixed variable set taken from OpenCode 1.18.3:

  | Value | Variables |
  | --- | --- |
  | `anthropic` | `ANTHROPIC_API_KEY` |
  | `openai` | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |
  | `google` | `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `GEMINI_API_KEY` |
  | `openrouter` | `OPENROUTER_API_KEY` |
  | `amazon-bedrock` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`, `AWS_BEARER_TOKEN_BEDROCK` |
  | `azure` | `AZURE_RESOURCE_NAME`, `AZURE_API_KEY` |
  | `opencode` | `OPENCODE_API_KEY` |
  | `none` | none |

  - When `OPENCODE_CONTAINER_PROVIDER` is unset or `none`, no provider variable is forwarded.
  - When it is unset and some formerly forwarded credential variables are set on the host, the wrapper prints a one-time stderr notice. The notice lists their names only and points to the new variables. `none` silences it.
  - An unsupported value stops with status 1 before any engine query.
  - Credentials stored with `opencode auth login` live in the mounted OpenCode data directory and keep working.
- **BREAKING** `GH_TOKEN` and `GITHUB_TOKEN` are never forwarded by default.
- New `OPENCODE_CONTAINER_ENV_VARS`, modeled on Pi's `PI_ENV_VARS`, takes a space-separated list of extra variable names to forward by name.
  - An invalid name stops with status 1 before any engine query.
  - Names that the wrapper sets authoritatively, such as `HOME`, `USER`, the XDG bases, `CONTAINER_HOST` and `CONTAINER_CONNECTION`, are skipped with a warning.
  - GitHub tokens or extra provider keys can be listed here deliberately.
- The base allowlist stays the same: terminal and locale, proxy, and OpenCode configuration variables, including `OPENCODE_SERVER_PASSWORD`. Forwarding stays by name, so values never appear in engine-client arguments.
- Help, README, `AGENTS.md`, `docs/validation.md` and `todo.md` document the new variables, the provider table and the migration for existing users.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `container-isolation`:
  - optional integration mounts become explicit opt-ins, and `~/.claude` is never mounted;
  - environment forwarding is limited to the base allowlist, the selected provider profile and the names the operator lists.

## Impact

- `opencode-wrapper`:
  - early validation of the new variables;
  - the integration mount loop is replaced with opt-in mounts;
  - the forwarding loop is split into the base set, the provider profile and the extra names;
  - the migration notice;
  - help text.
- Tests:
  - `tests/test_wrapper.py`: mount, forwarding, validation and notice cases;
  - `tests/test_runtime.py`: the integration-mount check is replaced with an opt-in check, and a real-engine provider forwarding check is added.
- Documentation: `README.md`, `AGENTS.md`, `docs/validation.md`, `todo.md`.
- Users:
  - sessions no longer see `~/.claude`;
  - `~/.agents` and `/etc/opencode` users must opt in;
  - users who relied on environment API keys must set `OPENCODE_CONTAINER_PROVIDER` or use `opencode auth login`;
  - users who relied on GitHub tokens must list them in `OPENCODE_CONTAINER_ENV_VARS`.
