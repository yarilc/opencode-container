# Proposal

## Why

OpenCode's launcher still automatically delegates the user's Podman authority and lacks the engine, private-state, and bounded lifecycle checks now present in the neighboring Codex, Claude Code, and Antigravity projects. Aligning these contracts addresses the verified gaps in `todo.md` while preserving OpenCode's XDG layout, per-user image identity, and executable OpenTUI temporary storage.

## What Changes

- **BREAKING**: Require a verified Linux rootless launch engine, reject named/implicit remote and TCP/SSH contexts, and validate complete engine responses before image operations.
- **BREAKING**: Delegate Podman only with `OPENCODE_CONTAINER_PODMAN=1`; verify the selected socket and its reported host source, stop on failed opt-in verification, and preserve host security policy.
- **BREAKING**: Reject insecure existing OpenCode XDG directories without repairing permissions or importing credentials; preserve effective HOME/XDG consistency for nonstandard homes and physical state paths.
- Provision temporary mounts explicitly, retain executable `/tmp`, support bind paths containing commas/spaces, and forward allowed credentials by environment name.
- Bound atomic name reservation, signal handling, interrupted-create reconciliation, and cleanup; preserve redirected stdin, application statuses, and unrelated containers.
- Add wrapper build, shell, worktree, and side-effect-free help modes; distinguish missing images from inspection errors and deny unlisted build-context inputs.
- Add synthetic and credential-free real-rootless acceptance checks and synchronize README/AGENTS with the new contracts.

## Capabilities

### New Capabilities

- `engine-authority`: Launch-engine verification, explicit delegation, socket selection/remapping, and retained host security policy.
- `sandbox-storage`: Private persistent XDG state, HOME consistency, mount boundaries, temporary storage, and environment forwarding.
- `session-lifecycle`: Atomic bounded naming, owned-container tracking, stdin attachment, status preservation, and bounded interruption cleanup.
- `wrapper-interface`: Wrapper modes, argument forwarding, image inspection/build behavior, and restricted build contexts.

### Modified Capabilities

None. The main spec inventory is currently empty; these capabilities document both the required changes and the existing invariants they must preserve.

## Impact

Primary files: `opencode-wrapper`, `opencode-entrypoint`, `.dockerignore` (or a replacement `.containerignore`), `README.md`, and `AGENTS.md`; new acceptance scripts/tests. `Dockerfile` remains the image/version and user-identity authority; adjust it only if required for the documented HOME contract. Host GNU coreutils `timeout` becomes an explicit prerequisite. No OpenCode version bump, new approval/YOLO switch, credential migration, Docker/Compose support, unrelated GID-collision repair, or changes to sibling projects are included. The user's `../antiantropy-container` reference is interpreted as the existing `../antigravity-container`.
