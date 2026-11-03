# Tasks

## 1. Wrapper interface and test fixtures

- [x] 1.1 Add `tests/test_wrapper.py` with disposable HOME/XDG, fake Podman call/status/response controls, Unix socket fixtures, private creation records, and an isolated runner; verify a baseline launch can be recorded without host credentials or real engine writes.
- [x] 1.2 Parse the four reserved container flags and add side-effect-free `--container-help`; verify help without Podman, unchanged native `--help`, and exact forwarding of spaces/empty strings/order.
- [x] 1.3 Implement shell entrypoint override, explicit parent worktree mount, and build-refresh session selection; verify shell omits agent arguments and worktree mode retains physical original workdir/name through symlinks.
- [x] 1.4 Document modes and GNU timeout in README/AGENTS; verify usage text, examples, parent exposure, and prerequisite diagnostics agree with the new interface.

## 2. Launch engine and delegation authority

- [x] 2.1 Implement status-preserving complete response capture and launch transport/engine validation before image operations; test missing/extra fields, rootful/non-Linux engines, invalid ServiceIsRemote, named/implicit remote contexts, TCP/SSH, relative/slash-only Unix endpoints, CR, extra blank/nonblank records, optional single final LF, and failed queries with plausible output.
- [x] 2.2 Add exact `OPENCODE_CONTAINER_PODMAN=1` opt-in and session `--unsetenv CONTAINER_HOST` when disabled; test unset/empty/0/1/true/yes/01/invalid/padded values across ordinary/build/shell modes and ensure a Unix launch service still works independently.
- [x] 2.3 Implement override/launch/runtime socket precedence, physical canonicalization/access checks, two-record exact-endpoint service query, and reported-host-source remapping; test relative/missing/inaccessible sockets, symlink endpoints, failed/malformed/rootful responses, space/comma paths, and unchanged launch connection.
- [x] 2.4 Remove label disabling and retain standard security policy; verify synthetic arguments contain no relabel/privilege overrides and all current capability/no-new-privileges/process-limit/identity settings remain present.
- [x] 2.5 Replace automatic/fallback socket instructions in README/AGENTS with explicit opt-in, same-host assumptions, manual systemctl/service and SELinux setup, and authority implications; verify diagnostics never execute service commands and failed opt-in prevents every image operation.

## 3. Private state, mounts, environment, and entrypoint

- [x] 3.1 Resolve and validate all four writable XDG directories under scoped creation umask; test missing private directories, permissive/wrong-owner/inaccessible/nondirectory/broken-symlink state, caller umask preservation, invalid relative HOME/XDG, and failure before image inspection/build.
- [x] 3.2 Align effective HOME/XDG with physical mount destinations and preserve supplied HOME in `opencode-entrypoint`; test nonstandard HOME, symlinked bases, differently named app-directory symlink targets, fallback HOME, and rejection of conflicting mount destinations using a stub OpenCode command and runtime smoke coverage.
- [x] 3.3 Replace unsafe mount construction with quoted bind arguments preserving physical sources and optional read-only integrations; test workspace/XDG/integration/socket comma-and-space paths, symlink workdirs, explicit colon-path rejection, and absence of additional host-home/credential mounts.
- [x] 3.4 Disable implicit read-only tmpfs provisioning and explicitly define `/tmp`, `/run`, `/var/tmp` flags, sizes, and modes from the storage spec; test exact arguments now and add runtime mount/exec/capacity/lifetime assertions for integration acceptance.
- [x] 3.5 Forward nonempty allowlisted inherited variables with `--env NAME`; test synthetic API keys/passwords arrive by name without values in client arguments, unlisted variables stay absent, and disabled delegation cannot be overridden.
- [x] 3.6 Document state privacy failures/manual remediation, native Linux storage, nonstandard HOME/XDG mapping, physical path constraints, explicit temporary mounts, and by-name forwarding limits in README/AGENTS; verify examples match synthetic cases and no automatic chmod/chown/import exists.

## 4. Image lifecycle and restricted build context

- [x] 4.1 Build automatically only for image-exists status 1 and preserve explicit refresh behavior; test image-present/missing/unexpected error/build failure, preflights in every mode, physical recipe location, and unchanged version/username/UID/GID tag/build arguments.
- [x] 4.2 Replace `.dockerignore` with an anchored default-deny allowlist for Dockerfile, entrypoint, and itself; add a real-Podman disposable context probe proving required COPY works while unknown root files, nested lookalikes, metadata, synthetic credentials/state, and unrelated files are excluded.
- [x] 4.3 Update image/build-context guidance in README/AGENTS and retain Dockerfile as the pinned-version/per-user identity authority; verify version stays `1.18.3` by default and documented allowlist matches actual recipe inputs.

## 5. Atomic naming and bounded owned lifecycle

- [x] 5.1 Check running/stopped name enumeration, parse one-to-nine-digit suffixes in base ten, and cap atomic create reservation at 20 confirmed collisions; test `08`, stopped names, invalid/oversized suffixes, concurrent reservations, listing/collision-lookup failures, and exhaustion without replacing containers.
- [x] 5.2 Separate create stdout/stderr and track exact full owned IDs through private cid records and a unique session label; test successful-create warnings, malformed/multiple/late IDs, ownership mismatches, noncollision create failures including 125, and unrelated-container preservation.
- [x] 5.3 Keep stdin interactive independently of conditional TTY and preserve it explicitly for tracked background attach; test pipes/files/EOF, terminal stdin+stdout, mixed terminal/redirection cases, and application exit statuses including 125.
- [x] 5.4 Add distinct signal handlers and EXIT cleanup with explicit once-only signal forwarding; test TERM/INT/HUP status 143/130/129, repeated first-signal precedence, application status preservation, no automatic signal proxy duplication, and cleanup diagnostics.
- [x] 5.5 Enforce one 20-second shutdown budget with at most five seconds grace and bounded control/client cancellation/reaping/reconciliation; test stalled create, delayed CID publication, engine loss, stuck kill/rm clients, unresolved ownership diagnostics, repeated signals, and no removal without verified ownership.
- [x] 5.6 Document naming bounds, owned cleanup, interruption/application statuses, shutdown deadline, residual-resource inspection, and redirected stdin in README/AGENTS; verify documented limits against measured synthetic timing and identity assertions.

## 6. Integrated credential-free acceptance

- [x] 6.1 Provide `tests/test_runtime.py`, a real-rootless opt-in runner, and an image smoke script using disposable private native Linux state and ownership-labelled resources; verify required tooling can run via Podman with preserved host absolute workspace paths and no imported user credentials.
- [x] 6.2 Run `bash -n opencode-wrapper` and `bash -n opencode-entrypoint` first, then the complete synthetic suite; record commands, case totals, timings, and results separately from real-engine acceptance.
- [x] 6.3 Build the current-user `1.18.3` image with the documented build arguments and run real identity/mount/state/build-context smoke checks; verify retained hardening, temporary effective flags/capacities/execution/lifetime, read-only integrations/root, persistent four-way XDG, and nonstandard HOME through the actual entrypoint.
- [x] 6.4 Run real-engine concurrent sessions, stopped-name/08 cases, redirected stdin/EOF, exit 125, TERM/INT/HUP/stubborn shutdown, worktree metadata, enabled child-container absolute bind, disabled image-default CONTAINER_HOST, and containerized-caller socket-remapping checks; verify bounded completion and preservation of unrelated containers.
- [x] 6.5 Verify `./opencode-wrapper --version` prints `1.18.3`, then start and quit actual OpenTUI interactively with disposable credential-free state; record renderer outcome independently of version output, explicit runtime blockers if any, and absence of test-owned wrapper containers using managed/session labels.
- [x] 6.6 Review README/AGENTS against final scripts and all `todo.md` items; deliver an acceptance record mapping each checklist item to synthetic and real evidence, keeping any blocked runtime/renderer requirement visibly unresolved rather than treating it as passed.
