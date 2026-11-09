# Design

## Context

The wrapper is `opencode-wrapper`, a Bash script with its own validation block for the exposure controls added by `narrow-exposed-state`. Its image name is fixed: `localhost/opencode-sandbox:${OPENCODE_VERSION:-1.18.3}-<user>-<uid>-<gid>`. It builds with `--file "$SCRIPT_DIR/Dockerfile"` and labels containers with:
- `io.opencode.managed`, `io.opencode.workspace` and `io.opencode.workspace-name` in `run_args`;
- `io.opencode.session` and `io.opencode.instance` at create.

Name reservation scans `podman ps --all --format '{{.Names}}'`, not labels. Ownership recovery filters on the session label and inspects it.

Facts measured on the pinned OpenCode 1.18.3 image on 2026-11-09, with the network disabled:
- `opencode --auto debug paths` fails with status 1, and an unknown flag before a subcommand fails as well. The CLI parses arguments strictly; `--auto`, `--yolo` and `--dangerously-skip-permissions` exist only on the default TUI command and `run`.
- `OPENCODE_PERMISSION` is parsed as JSON and merged into the resolved `permission` configuration after the configuration files.
- With a user configuration containing `bash: {"rm *": "deny"}` and `edit: "ask"`, and `OPENCODE_PERMISSION={"*":"allow"}`, `opencode debug agent build` lists `{"permission":"*","action":"allow"}` after the user rules. The bypass therefore applies to everything, as Claude's `--dangerously-skip-permissions` and Codex's `--yolo` do.
- `opencode debug config` shows the resolved `permission`, which allows a credential-free check.

Reference interfaces: `codex-container.sh` (help layout, `CODEX_CONTAINER_IMAGE`, the YOLO word set and message) and the `codex-container` README and `AGENTS.md` structure.

## Goals / Non-Goals

**Goals:**
- Common names and switches with no silent break: deprecated names keep working with a warning.
- Credential-free evidence for the YOLO mapping on the pinned version.
- Help, README and `AGENTS.md` follow the common structure, so that later changes add sections in the same places as the other wrappers.

**Non-Goals:**
- The generic Debian image, removing per-user identity, the dedicated home, the state directory option, budgets, the workspace guard, lifetime and pinning (A03–A05, A11), which belong to `align-runtime-image`. `OPENCODE_CONTAINER_IMAGE` keeps the per-user default until then.
- Network, setup and qualification (Wave 3).
- Removing the `opencode-wrapper` shim (final cleanup).

## Decisions

### D1: YOLO through `OPENCODE_PERMISSION`
The wrapper validates `OPENCODE_CONTAINER_YOLO` in the early validation block with Codex's word set:
- lowercase the value with `${value,,}`;
- `1|true|yes` enable YOLO;
- `''|0|false|no` disable it;
- anything else dies with `OPENCODE_CONTAINER_YOLO must be 0, 1, true, false, yes, or no`.

When enabled, `run_args` gets `--env 'OPENCODE_PERMISSION={"*":"allow"}'`. This is a nonsecret literal, and it is added after by-name forwarding so it wins in Podman's last-wins order. A nonempty host `OPENCODE_PERMISSION` together with YOLO is refused during validation, so neither value silently overrides the other.

Alternatives considered:
- **Native `--auto`:** rejected because strict parsing breaks `debug`, `models`, `auth` and other subcommands. Inserting it only for the TUI and `run` would require the wrapper to parse OpenCode's command grammar.
- **`"allow"` as a string:** rejected because merging a string into an object configuration is not documented. The `{"*":"allow"}` object form was measured.

### D2: Entry point and shim
The script is moved with `git mv opencode-wrapper opencode-container.sh`, so its history stays attached. Usage text and diagnostics change from `opencode-wrapper:` to `opencode-container:`. The new `opencode-wrapper`:
1. resolves its own physical directory with `readlink -f`;
2. prints `opencode-wrapper: deprecated; use opencode-container.sh` to stderr;
3. runs `exec "$dir/opencode-container.sh" "$@"`.

`exec` keeps the PID, stdin and signals, so the lifecycle contract is unchanged.

### D3: Recipe and ignore files
Both files are moved with `git mv`. `.containerignore` allows `/Containerfile`, `/opencode-entrypoint` and `/.containerignore`. The wrapper builds with `--file "$SCRIPT_DIR/Containerfile"`. Podman 4.9 prefers `.containerignore` when present.

### D4: Image and version variables
The early block resolves the version:
1. `OPENCODE_CONTAINER_VERSION` if set;
2. otherwise `OPENCODE_VERSION`, with a warning;
3. otherwise `1.18.3`.

It validates the version with `^[A-Za-z0-9][A-Za-z0-9._-]*$`. It then sets `IMAGE=${OPENCODE_CONTAINER_IMAGE:-<per-user tag>}` and rejects whitespace and control characters in the image name. The build argument `OPENCODE_VERSION` keeps its name inside the recipe, because it is a build argument rather than a wrapper setting. A unit test reads `ARG OPENCODE_VERSION=` from `Containerfile` and requires it to equal the wrapper default.

### D5: Labels
All five labels are renamed in place. No old-label code path is kept: the wrapper never selects other sessions by label, and name reservation already treats a pre-existing `project-0` as taken whatever its labels. Documentation gives both filters for manual inspection during the transition.

### D6: Help and documentation layout
Help is restructured as Codex's:
1. usage;
2. `Container options:`;
3. the lifecycle paragraph;
4. `Environment:`, with one entry per variable and its default: `OPENCODE_CONTAINER_IMAGE`, `OPENCODE_CONTAINER_VERSION`, `OPENCODE_CONTAINER_PODMAN`, `OPENCODE_CONTAINER_PODMAN_SOCKET`, `OPENCODE_CONTAINER_YOLO`, `OPENCODE_CONTAINER_PROVIDER`, `OPENCODE_CONTAINER_ENV_VARS`, `OPENCODE_CONTAINER_AGENTS_DIR` and `OPENCODE_CONTAINER_SYSTEM_CONFIG`;
5. the security paragraph.

Help stays side-effect free.

The README is reorganized into the common sections:
- title "OpenCode CLI in Podman";
- "Enable rootless Podman on the host";
- "Optional host Podman API access";
- "Usage", covering modes, names, worktrees, YOLO and environment;
- "Mounts and security", covering state, integrations, credentials and migration;
- "Included Tools", covering the image, build context and updating;
- "Session lifecycle";
- "Verification".

Existing content is moved rather than rewritten. Rename and migration notes are added.

`AGENTS.md` is reorganized into Codex's "Repository Guidelines" sections:
- Project Structure & Module Organization;
- Build, Test, and Development Commands;
- Coding Style & Naming Conventions;
- Testing Guidelines;
- OpenSpec Workflow;
- Commit & Pull Request Guidelines;
- Security & Configuration.

Every existing OpenCode requirement is kept, and a checklist in the tasks verifies that none is lost.

### D7: Tests
The existing suites are updated mechanically for the new paths, image recipe, labels and diagnostics prefix. New wrapper cases cover:
- shim forwarding: arguments, status and one warning;
- YOLO: words, case-insensitivity, invalid values, the conflict with `OPENCODE_PERMISSION`, and identical mounts and forwarding with and without YOLO;
- `OPENCODE_CONTAINER_IMAGE`;
- the version alias and precedence;
- an invalid version;
- the label set;
- the `Containerfile` version matching the wrapper default;
- help content.

New runtime cases:
- with YOLO, `opencode debug config` inside a real session reports `permission` `{"*":"allow"}`, with no credentials;
- the created container carries only `io.opencode-container.*` labels;
- the shim runs a real session.

`test_image_default_host_is_removed` uses `OPENCODE_CONTAINER_IMAGE` instead of the version hook.

## Risks / Trade-offs

- **YOLO overrides explicit `deny` rules.** This matches the other wrappers' native bypasses. Help and README state it plainly, and the default is disabled.
- **External scripts filter on `io.opencode.*`.** The README migration note gives the new filter. Old containers are still listed by the old filter and are left untouched.
- **A future OpenCode release changes how `OPENCODE_PERMISSION` is merged.** The runtime check on the resolved configuration catches it when the version moves (A03 procedure).
- **The documentation reorganization loses a contract.** The task checklist compares the old and new `AGENTS.md` and README contract lists.

## Migration Plan

1. Implement on branch `align-wrapper-baseline`. Unit suites run in the runner container, and real-engine checks with `bash tests/run-runtime.sh`.
2. Users keep their alias, which warns, or point it to `opencode-container.sh`. They replace `OPENCODE_VERSION` with `OPENCODE_CONTAINER_VERSION` and update label filters. Existing images keep their tags, so no rebuild is required.
3. Rollback: revert the merge. No state or image format changes.
