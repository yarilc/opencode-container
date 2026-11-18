## Context

`README.md`, section "Updating pinned image inputs", gives a seven-step
procedure:

1. Change the pins.
2. Re-read the provider metadata.
3. Check how `OPENCODE_PERMISSION` is merged and how `--auto` is parsed.
4. Remeasure the hosts and the `OPENCODE_DISABLE_*` controls, then set a new
   policy revision and `tested.cli`.
5. Rebuild in maintenance mode and requalify.
6. Rerun the credential-free and real-engine checks, including OpenTUI.
7. Record the results.

The pin test requires `tested.cli` to match `OPENCODE_VERSION`. npm verifies
the integrity of `opencode-ai` and of its platform binaries, which are
exact-version optional dependencies.

The 1.18.3 measurements (2026-11-10) are a static endpoint inventory plus
logging-proxy runs. They found that the five disabling variables win over
`opencode.json`. Two requests have no control: the background install of
`@opencode-ai/plugin` and an explicit `opencode upgrade`. Both reach
`registry.npmjs.org` and are denied.

## Goals / Non-Goals

**Goals:**
- Pin 1.19.5 and OpenSpec 2.0.0 exactly. The build checks
  `opencode --version` and `openspec --version`.
- Run every step of the README procedure, and compare the results with the
  1.18.3 record.

**Non-Goals:**
- OpenCode 2.x, which gets a dedicated change.
- Removing `OPENCODE_DISABLE_SHARE` or `OPENCODE_DISABLE_AUTOUPDATE`, even if
  1.19 no longer needs them.
- Changing the base digest or any shared file.

## Decisions

- **1.19.5, not 1.19.6 and not 2.3.0.** This follows the agreed age rule
  (newest non-prerelease that was at least 72 hours old on 2026-11-18) on the
  npm line the recipe uses. The user moved 2.x to its own change.
- **Always a new policy revision.** The README procedure asks for one, and it
  marks the remeasurement, even if the host sets stay the same.
- **Keep both obsolete-looking controls.**
  - Session sharing is discontinued in 1.19.1, and automatic update installs
    stopped in 1.19.0.
  - The variables are harmless and still protect configurations written for
    1.18.
  - The record states what each one still controls on 1.19.5. Dropping them
    would be a separate, visible change.
- **Spec delta only when required hosts change.** If that happens, the work
  pauses, and a `network-egress` delta is added after the user agrees.

## Risks / Trade-offs

- [Bun 1.4.4 in 1.19.4 changes TLS or `fetch` behavior behind the relay and
  proxy] → The logging-proxy runs and the network runtime suite cover the TLS
  path through the relay. A failure is classified with the old-test gate.
- [YOLO merge or `--auto` parsing changed] → Check them directly, as step 3 of
  the procedure requires. A change in YOLO semantics is a lost or visible
  behavior and goes to the user.
- [The executable `/tmp` and read-only state layout behave differently] →
  `tests/test_runtime.py` already covers them. Classify any failure.
- [Rollback] → Revert the pins and the policy, then rebuild.

## Migration Plan

1. The operator pushes `main`.
2. The operator reruns `--container-setup` on the three hosts.

OpenCode 2.x follows in its own change.
