# Proposal: Align the OpenCode wrapper with the common baseline

## Why

The other four wrappers share a common interface:
- a `<name>-container.sh` entry point;
- a `Containerfile`/`.containerignore` recipe;
- `<PREFIX>_CONTAINER_IMAGE` and a YOLO switch;
- `io.<name>-container.*` ownership labels;
- a common layout for help, README and `AGENTS.md`.

OpenCode still differs on all of these:
- it uses `opencode-wrapper` and `Dockerfile`/`.dockerignore`;
- it reads the generic `OPENCODE_VERSION`, which sits in OpenCode's own namespace;
- it has no image override and no YOLO switch;
- it labels its containers `io.opencode.*`.

This change closes todo A01, A02, A09 and the remaining A08 alignment. It completes the wrapper-interface part of Wave 2, before the image and baseline change (`align-runtime-image`) and the Wave 3 network port.

## What Changes

- **YOLO switch (A01):** new `OPENCODE_CONTAINER_YOLO`, with the same values as the other wrappers:
  - `1`/`true`/`yes` enable it and `''`/`0`/`false`/`no` disable it, case-insensitively;
  - any other value stops with status 1 before engine queries.

  When enabled, the wrapper sets `OPENCODE_PERMISSION={"*":"allow"}` in the session, which OpenCode 1.18.3 merges last into its resolved permissions. OpenCode's native `--auto` flag cannot be used: its strict argument parsing rejects the flag on most subcommands. Like the native bypass flags of Claude and Codex, the effect overrides configured `ask` and `deny` rules. It changes no mount, network or delegation setting.
  - When YOLO is enabled and a host `OPENCODE_PERMISSION` would also be forwarded, the wrapper stops instead of choosing one.
  - When YOLO is disabled, user permission settings are untouched.
- **BREAKING (deprecated alias kept), entry point (A02):** the wrapper becomes `opencode-container.sh`. `opencode-wrapper` remains as a shim that prints a deprecation warning to stderr and execs the new script with unchanged arguments, so existing aliases keep working. Diagnostics use the `opencode-container:` prefix.
- **BREAKING, recipe files (A02):** `Dockerfile` and `.dockerignore` become `Containerfile` and `.containerignore`, and the default-deny allowlist names the new files. Building from a manual `podman build .` still works, because Podman reads `Containerfile`.
- **Image override (A02):** new `OPENCODE_CONTAINER_IMAGE` selects the image name and defaults to today's per-user tag. The per-user default disappears with `align-runtime-image`.
- **BREAKING (deprecated alias kept), version variable (A02):** `OPENCODE_CONTAINER_VERSION` replaces `OPENCODE_VERSION`.
  - The old name is still honored, with a deprecation warning, when the new one is unset.
  - Both are validated as a version token before engine queries.
  - The wrapper default and the recipe `ARG` stay `1.18.3`, and a test keeps them equal.
- **BREAKING, labels (A02):** ownership labels move from `io.opencode.*` to `io.opencode-container.*` (`managed`, `workspace`, `workspace-name`, `session`, `instance`). The wrapper only ever removes containers it created in the same invocation, so it needs no compatibility with old labels. The README explains how to find pre-existing `io.opencode.managed=true` containers.
- **Tests (A09):** tests and helpers follow the new names. These are `tests/test_wrapper.py`, `tests/test_runtime.py`, `tests/run-runtime.sh` and `tests/image-smoke.sh`, and they now use the `io.opencode-container.acceptance` label. The existing lifecycle, response-validation and OpenTUI coverage is kept.
- **Documentation (rest of A08):**
  - `--container-help` uses the common "Container options / Environment" layout, listing every `OPENCODE_CONTAINER_*` variable with its default.
  - The README follows the common section order (rootless Podman setup, optional Podman API access, usage, mounts and security, included tools, verification).
  - `AGENTS.md` follows the common "Repository Guidelines" structure while keeping every OpenCode-specific contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `container-launcher`:
  - entry point and deprecated shim;
  - the YOLO switch;
  - image name and version variables;
  - recipe and ignore-file names in the build-context requirement.
- `container-session`: the ownership and management label namespace.

## Impact

- **Files:**
  - `opencode-wrapper` is renamed to `opencode-container.sh`, and a new `opencode-wrapper` shim is added;
  - `Dockerfile` becomes `Containerfile` and `.dockerignore` becomes `.containerignore`;
  - `opencode-entrypoint` is unchanged.
- **Tests:** all four test files.
- **Documentation:** `README.md`, `AGENTS.md`, `docs/validation.md`, `todo.md`.
- **Users:**
  - aliases pointing to `opencode-wrapper` keep working with a warning;
  - `OPENCODE_VERSION` keeps working with a warning;
  - scripts that filter on `io.opencode.*` labels must switch to `io.opencode-container.*`;
  - YOLO is opt-in.
- **Images:** existing per-user images keep their tags, so no rebuild is needed.
