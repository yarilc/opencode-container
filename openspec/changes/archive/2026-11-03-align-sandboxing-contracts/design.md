# Design

## Context

See `proposal.md` for motivation and scope. Discovery read `todo.md`, the current wrapper/entrypoint/Dockerfile/README/ignore policy, and the three neighboring launchers, ignore files, and acceptance tests. `../antiantropy-container` does not exist; the matching implementation is `../antigravity-container`. There are no existing main capability specs.

Observed OpenCode behavior confirms the checklist: launch verification queries only Rootless; accessible default sockets are exposed automatically with `label=disable`; XDG paths are created without privacy checks; inherited secrets are embedded in arguments; comma-delimited mounts cannot encode comma paths; image-inspection errors all trigger builds; unchecked name enumeration and unbounded create retries accompany a shared EXIT/signal cleanup trap. Interactive stdin is enabled only with a TTY. The entrypoint overwrites the supplied HOME with `/home/<user>`. The ignore file is a blacklist and the requested wrapper modes do not exist.

The neighboring launchers supply useful contracts, not interchangeable code: response serialization and lifecycle recovery differ, and their HOME layouts are application-specific. OpenCode already has keep-id, named per-user images, capability dropping, no-new-privileges, executable `/tmp`, an environment allowlist, and a process limit. These are preserved, not described as missing. Bash syntax checks passed during this planning run. No new fake-engine suite, image build, service connection, or OpenTUI acceptance was executed; the existing fake-probe report in `todo.md` is prior evidence only.

Two current repository instructions deliberately change: automatic optional-socket fallback becomes explicit fail-closed opt-in, and the SELinux label-disable branch is removed. README and AGENTS must change with implementation. The documented GID-collision limitation remains out of scope.

## Goals / Non-Goals

**Goals:**

- Separate launch-engine verification from the additional authority delegated to a session.
- Make preflight failures occur before image inspection/build/create, including explicit refresh and shell/worktree combinations.
- Preserve OpenCode state location compatibility and observable statuses while bounding cancellation and cleanup.
- Make every checklist item reviewable through specific synthetic cases and independent real-engine evidence.

**Non-Goals:**

- No shared library/package extraction across sibling repositories and no copying their entire wrappers or application-specific credential/approval features.
- No claim that rootless socket delegation limits the host mounts available through that service, or that by-name forwarding hides secrets from container processes/engine inspection.
- No new host-home writable mount, state migration, filesystem permission repair, version upgrade, or host service activation.

## Decisions

### 1. Order preflights before image operations

Parse only the four reserved wrapper flags first; `--container-help` exits before tool checks or filesystem changes and native `--help` remains forwarded. Require host Podman and GNU `timeout`, then validate launch transport and engine, enabled delegation, and all four state directories before image inspection/build/create. Resolve workspace and recipe directories physically. Keep launch connection variables on the engine clients; never export the delegation endpoint back into the wrapper environment.

Use `OPENCODE_CONTAINER_PODMAN` and `OPENCODE_CONTAINER_PODMAN_SOCKET` to match the sibling naming convention. Only exact `1` enables access. Disabled sessions always use `--unsetenv CONTAINER_HOST`; their socket override is ignored. Enabled access selects nonempty override, Unix launch endpoint, then runtime default, canonicalizes the accessible socket, verifies socket type/access, and queries that endpoint with explicit `--remote --url`. Mount its reported host source at `/run/podman/podman.sock` and explicitly set only the session endpoint.

Alternative: reuse the current rootless-only check and warn on unavailable sockets. Rejected because launch policy and delegated authority would remain ambiguous and opted-in failures could silently change behavior.

### 2. Capture complete responses and parse a fixed grammar

Use a capture helper that appends a non-newline sentinel while returning the original command status and preserving stderr. Remove only the sentinel and at most one final LF. Launch output contains exactly one record with three fields: `true linux true|false`; reject CR, missing/extra fields, and any extra newline. ServiceIsRemote=true requires the explicit supported Unix launch endpoint, even with delegation disabled. Reject nonempty CONTAINER_CONNECTION and malformed Unix/TCP/SSH endpoints before querying.

For delegated verification request two records: Rootless, then Host.RemoteSocket.Path. Require exactly `true` followed by an absolute pathname containing a non-slash character; preserve spaces/commas in the second record. An extra record, blank record, CR, query failure, or malformed field is fatal. The caller-visible canonical endpoint is checked for access; the reported host source is not required to exist in a containerized caller's filesystem.

Alternative: ordinary command substitution and whitespace splitting. Rejected because trailing blank records disappear and socket paths with spaces can be truncated. Two records avoid the path ambiguity found in single-line formats without requiring JSON tooling on the host.

### 3. Keep XDG persistence while fixing HOME and physical destinations

Require an absolute HOME and nonempty XDG overrides to be absolute (invalid relative XDG settings fail with a diagnostic). For each base, compute `<base>/opencode`; create only missing directories under `(umask 077; mkdir -p ...)`, physically resolve them, and validate directory type, caller UID, read/write/traverse access, and octal mode with no group/other bits. Existing symlinks to valid private directories are accepted; broken symlinks and invalid targets fail. No chmod/chown, credential copies, or bulk HOME import occur.

Mount each resolved OpenCode directory at its identical physical absolute path, preserving the host-side path required for nested bind operations. Set the session XDG base to the resolved directory's parent, verifying its final component remains `opencode`. If an app-directory symlink points at a differently named target, bind its physical source at `<physical-parent>/opencode` and set that parent as the session XDG base; this is an explicit destination mapping, not a host-side symlink requirement. Test this mapping separately from a symlinked XDG base. Reject colliding destinations that would shadow the workspace, another state directory, a temporary path, or a different optional integration; identical source/destination aliases can be deduplicated.

Preserve wrapper-supplied HOME in `opencode-entrypoint`; derive USER from `id`, and use `/home/<user>` only as a fallback if HOME is absent. HOME outside declared mounts stays read-only. The existing image user/home can remain unchanged because the wrapper supplies the session path. Tests must exercise entrypoint behavior directly as well as shell mode, which bypasses it.

Alternative: mount the entire HOME or move all state to one writable home as in some neighbors. Rejected because that broadens persistence and changes OpenCode's established XDG layout. Silently accepting relative XDG settings is rejected because it cannot establish a consistent absolute mount contract.

### 4. Use explicit storage and safe bind arguments

Use quoted Podman `--volume source:destination:rw|ro` arguments for the Linux absolute paths in scope; commas and spaces remain literal. Preserve optional integrations read-only. Colon-containing paths are outside the newly guaranteed path set; reject them explicitly before image operations if this volume representation cannot encode them, with a clear diagnostic rather than an incorrect mount. Do not add relabel options or disable SELinux policy.

Set `--read-only-tmpfs=false` and provision `/tmp` as exec,nosuid,nodev,512m,1777; `/var/tmp` as noexec,nosuid,nodev,512m,1777; `/run` as noexec,nosuid,nodev,32m,1777. No writable HOME tmpfs is introduced. Retain all current hardening and the 512-process limit. Add allowed inherited variables as `--env NAME`, preserving current nonempty-value forwarding semantics; keep only deliberate nonsecret HOME/USER/XDG/delegation assignments as literals. Do not extend the allowlist with engine selection variables.

Alternative: hand-built CSV mounts or automatic tmpfs defaults. Rejected because they leave delimiter bugs and engine-dependent writable paths. Mount flags and capacities require real runtime inspection, not just argument assertions.

### 5. Use a bounded session lifecycle with explicit ownership

Retain the existing managed/workspace labels and add a unique per-invocation session label. Create a private 0700 bookkeeping directory and 0600 stdout/stderr/cid records. Enumerate names with checked status; accept only one-to-nine decimal digits and use base-ten arithmetic. Start above the largest accepted suffix, reserve with create, and stop after at most 20 confirmed collisions. A collision lookup error is fatal; preserve original noncollision create status/diagnostics, including 125.

Use `--cidfile` and track create/attach child clients explicitly. Require an exact full lowercase hexadecimal 64-character ID; never treat stderr text or a name as ownership proof. Private creation records establish normal ownership. During interrupted creation, use bounded lookup by the unique session label if a record is delayed and verify the recovered ID's label before removal. Reject malformed, multiple, or inconsistent IDs and report unresolved outcomes. A name collision owned by another session never authorizes cleanup.

Use separate TERM/INT/HUP handlers and EXIT cleanup. Record the first signal/status, prevent repeated signals from renewing deadlines, and use `--sig-proxy=false` on attach so forwarding is explicit. Shutdown uses one 20-second monotonic budget, with at most five seconds of application grace; bound every control call with GNU timeout, reserving time for TERM/KILL client cancellation, reaping, and a final creation reconciliation. Never perform a blocking wait on a child still known to run after its deadline. Normal application status and first interruption status take precedence over cleanup failures. Unresolved creation/removal emits the full owned ID or session marker for manual inspection.

Run create with stdin detached; run attach interactively with explicit `<&0` so background clients receive pipes/files and EOF. `--interactive` is unconditional on create; only `--tty` depends on terminal stdin and stdout.

Alternative: shared cleanup traps, unbounded waits, or delete-by-name. Rejected because races can lose identity, exceed shutdown budgets, corrupt statuses, or remove an unrelated container.

### 6. Keep wrapper modes and build inputs narrow

`--container-build` refreshes the existing version/user/UID/GID tag using the repository Dockerfile, then starts the selected session; it does not imply a version update or mandatory no-cache build. Ordinary inspection builds only for status 1 and reports/stops on other errors. Shell mode overrides the entrypoint with `/bin/bash` and clears OpenCode arguments. Worktree mode mounts the immediate parent read/write but retains the original physical workdir and name prefix. Help documents the extra exposure; all modes share preflights.

Retain `.dockerignore` as the sole effective ignore file and replace its blacklist with an anchored default-deny policy allowing only `/Dockerfile`, `/opencode-entrypoint`, and `/.dockerignore`. Test actual Podman filtering in a disposable context containing synthetic root and nested secrets/lookalikes; demonstrate required COPY success and forbidden COPY failure. Avoid a second ignore file that could silently take precedence.

Alternative: copy the neighbors' recipe allowlists unchanged. Rejected because OpenCode uses Dockerfile and requires its own entrypoint COPY input.

### 7. Separate synthetic evidence from runtime acceptance

Add a Python standard-library fake-Podman suite with disposable HOME/XDG and a real local Unix socket fixture for filesystem checks. Record calls without real credentials. Cover malformed outputs including trailing LF/CR, failed queries with plausible stdout, exact opt-in matrices across modes, launch/delegation independence and remapping, private state and symlinks, comma/space paths, by-name secrets, stdin/PTY, missing/failed images, collision limits/08/concurrency, exit 125, interruption races, stalled create/control clients, bounded reaping, and unrelated ownership preservation.

Add an explicitly enabled real-rootless suite and image smoke script. Use native Linux private test state (a disposable volume if needed in WSL), original host absolute bind paths, and synthetic values. Verify context filtering, effective mount flags/capacities and execution, state persistence versus temporary lifetime, nonstandard HOME, numeric identity, worktree metadata access, default-image CONTAINER_HOST removal, child-container absolute binds and remapped caller sockets, status/signals/concurrency, and unrelated-container preservation. Use Podman for missing test tooling while preserving workspace bind paths; do not depend on installing host Python or ShellCheck.

Build the default per-user image, verify `--version` prints `1.18.3`, and start/quit the actual OpenTUI interactively using disposable credential-free state. Record blocked renderer checks separately if the runtime is unavailable; version/help alone is not renderer acceptance. Test-created resources use their own ownership labels so managed-container leak checks distinguish them from preexisting sessions.

## Risks / Trade-offs

- [Existing state may be permissive on WSL/DrvFS] → Fail with explicit path diagnostics; explain manual permissions or private native Linux storage. Never silently chmod credentials.
- [Host policy may deny opted-in service access] → Retain standard confinement and document manual service/SELinux setup; no automatic relabel or policy override.
- [A same-host Unix endpoint cannot prove storage locality by itself] → Document the same-host absolute-path precondition and validate remapped binds in runtime tests.
- [Engine loss or SIGKILL can leave resources] → Bound shutdown, preserve status, report ownership/session identifiers, and document manual inspection.
- [Overlapping user-selected mounts can shadow validated paths] → Detect conflicts before image operations and include adversarial path tests.
- [Colon paths are not representable with the selected volume syntax] → Explicit rejection; the required compatibility gain covers spaces and commas, not arbitrary Unix filename bytes.
- [Sibling suites passing does not prove OpenCode compatibility] → Use an OpenCode-specific image/entrypoint smoke check and actual interactive renderer acceptance.

## Migration Plan

1. Implement and verify wrapper/entrypoint/ignore policy plus synthetic tests without touching existing credentials or unrelated engine resources.
2. Update README and AGENTS in the same change: exact opt-in variables, launch restrictions, private-state requirements, GNU timeout, explicit modes and their exposure, temporary storage, by-name forwarding limits, SELinux setup, finite cleanup and residual-resource diagnostics.
3. Users who need delegation explicitly set `OPENCODE_CONTAINER_PODMAN=1` and prepare their rootless service manually; users with insecure state choose private storage or correct permissions themselves. No credential migration is performed.
4. Run real-rootless acceptance and record its results separately from synthetic checks, including renderer evidence and unavailable checks. Confirm no test-owned wrapper containers remain.
5. Rollback restores the earlier wrapper/entrypoint/ignore/docs revision and rebuilds the same per-user image if needed. State remains in place. Clearly note that rollback restores automatic socket exposure and earlier lifecycle limitations; no automatic downgrade is performed.
