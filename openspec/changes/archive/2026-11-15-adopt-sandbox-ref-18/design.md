# Design

## Context

See proposal.md for the findings. Current OpenCode lifecycle:

- `opencode-container.sh:1160` creates the container with the session label `$ownership_label`
  and a private CID file.
- `opencode-container.sh:1182` treats any existing container with the candidate name as a
  collision.

The reference (`claude-container.sh`, `recover_container` and the create loop)
checks the label before treating a name as taken, and recovers an interrupted
creation with `ps --all --no-trunc --filter label=<label>=<token>`, then
confirms the label with `inspect` before removing.

## Goals / Non-Goals

**Goals:**
- Adopt `sandbox-ref-18` byte for byte and declare OpenCode's agent variables.
- Never leave or skip a container that carries this session's label.

**Non-Goals:**
- Rewriting OpenCode's lifecycle into the reference's structure. Only the two
  reconciliation rules are ported.
- Moving the lifecycle into shared code.

## Decisions

### Agent variables

OpenCode declares `OPENCODE_`, `ANTHROPIC_`, `OPENAI_`, `OPENROUTER_`, `GEMINI_`, `GOOGLE_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, the five `AWS_` Bedrock names and the two `AZURE_` names. Prefixes cover controls a later release may add;
exact names are used where a prefix would also catch unrelated tools (for
example `GOOGLE_` would catch a Google Cloud SDK toolchain's settings).
The launcher's own filter stays: it was the immediate fix, it also runs when
the toolchain library is used without the profile declaration, and its test
already guards the `--env` order.

### Ownership-checked collision

After a failed create with no ID, run `container exists` and, when it
exists, `inspect --type container --format '{{index .Config.Labels "<label>"}}'`.
Only a different label is a collision. The same label leaves the creation
pending, so cleanup reconciles it, and the wrapper exits with the create
status. An `inspect` failure is reported like an unconfirmed collision today:
exit with the create status, no retry.

Alternative: retry on the same label. Rejected: the reference reports the
original failure, and a retry would double the credential-bearing containers.

## Risks / Trade-offs

- [The stricter alignment test or the shared overlap check fails on a OpenCode
  test fixture] → The adoption suites show it; the fixture is adapted in this
  change and recorded in `docs/validation.md`.
- [A legitimate toolchain sets a now-protected variable] → `launch-env`
  warns and leaves it out; the operator forwards it explicitly.
- [The extra lookup slows an interrupted shutdown] → It is bounded by the
  shared shutdown deadline.

## Migration Plan

Adopt on branch `adopt-sandbox-ref-18`, run the suites, merge with `--no-ff`.
The operator pushes and reruns `--container-setup` on the three hosts.
Rollback before the operator setup is a revert of the merge.
