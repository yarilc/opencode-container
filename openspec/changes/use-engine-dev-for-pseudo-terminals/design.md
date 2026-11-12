# Design

## Context

`opencode-container.sh` builds the container arguments around line 680. For
every OpenCode and shell container it passes, among others:

- `--read-only`, with automatic read-only tmpfs provisioning enabled;
- `--tmpfs "/dev:rw,nosuid,noexec,mode=755,size=65536k"`;
- `--mount type=devpts,destination=/dev/pts`;
- `--mount type=tmpfs,destination=/dev/shm,ro=true`;
- `--mount type=tmpfs,destination=/run/secrets,ro=true`;
- the OpenCode tmpfs mounts:
  - executable `/tmp` (512 MiB) for OpenTUI;
  - `noexec` `/var/tmp` (512 MiB) and `/run` (32 MiB);
  - `/opencode-home` in shared-state mode.

The same layout was fixed in the Claude reference and in Codex. The
reference validation record (claude-container `docs/validation.md`,
"Engine-provided `/dev` for pseudo-terminals") measured:

- the explicit `devpts` is `mode=600,ptmxmode=000`, and allocation fails;
- `--device /dev/ptmx` does not help;
- Podman rejects `ptmxmode` as a mount option;
- the engine's `devpts` is `mode=620,ptmxmode=666` and works.

The defect was rechecked here with `localhost/opencode-cli:adopt-ref-11`
(`45ae34976eb9`) and this launcher's `/dev` arguments: "out of pty
devices".

Qualification digests the launcher (`agent/profile.json` `wrapper`).

The existing tests are:

- `tests/test_wrapper.py`:
  - `DEVICE_MOUNTS` with `assert_device_and_secret_mounts` (around
    line 454);
  - the tmpfs list in `test_tmpfs_and_named_environment` (around line 487),
    which includes the `/dev` entry.
- `tests/test_runtime.py`:
  - it always uses `localhost/opencode-cli:latest`, so that tag is assigned
    temporarily to the image under test and removed afterwards with
    `podman untag <image> localhost/opencode-cli:latest`. A bare
    `podman untag <image>` removes every tag;
  - `shell()` feeds the script through a pipe.

## Goals / Non-Goals

**Goals:**
- The same launcher, test and documentation behavior as the Claude
  reference, with the OpenCode temporary mounts unchanged.

**Non-Goals:**
- Shared code. The proxy keeps `--read-only-tmpfs=false`.
- The hardcoded image tag in `test_runtime.py`.

## Decisions

1. **Leave `/dev` to the engine**, as in the reference. Remove the `/dev`
   tmpfs and the `devpts`, keep `--read-only` and both masks, and use the
   reference comment wording. The alternatives (`ptmxmode`, `--device
   /dev/ptmx`, keeping no PTYs) were rejected in the reference.

2. **Spec.** Remove "Terminal-compatible device mounts" and add
   "Engine-provided device mounts allow pseudo-terminals", with the
   reference's scenarios plus the existing scenario "Temporary mounts keep
   their OpenCode policy".

3. **Tests.**
   - `tests/test_wrapper.py`:
     - `DEVICE_MOUNTS` keeps only the `/dev/shm` and `/run/secrets` masks;
     - `assert_device_and_secret_mounts` also asserts that there is no
       `--tmpfs` for `/dev` and no `devpts` or `/dev` `--mount`;
     - the tmpfs list loses its `/dev` entry.
   - `tests/test_runtime.py`: add `test_pseudo_terminals_and_device_masks`,
     the reference probe run through `self.shell()`. It must fail on the
     current launcher and pass after the fix.

4. **Documentation.**
   - `README.md` hardening list (around line 511): the engine provides
     `/dev` and a `devpts` that allows pseudo-terminals, and an explicit
     `devpts` would get `ptmxmode=000`. On Podman 5, `/dev` is writable but
     needs capabilities to create devices; on Podman 4.9 it is read-only.
     The `/dev/shm` sentence stays.
   - `AGENTS.md` line 114: replace "override its targets with a noexec
     64 MiB `/dev`, an explicit `devpts` and an empty read-only `/dev/shm`"
     with "leave `/dev` and its `devpts` to the engine and override
     `/dev/shm` with an empty read-only tmpfs".
   - `docs/validation.md`: a record with the results and pending operator
     setups.

## Risks / Trade-offs

- [On Podman 5, `/dev` is writable and executable] → `nosuid` remains,
  devices need the dropped capabilities, and `/dev` is ephemeral. OpenCode's
  `/tmp` is already executable for OpenTUI, so the exposure does not grow.
- [The OpenTUI renderer depends on the terminal] → `test_opentui_renderer`
  runs in the default runtime run.
- [The Rocky host cannot be reproduced here] → The operator reruns setup
  there.

## Migration Plan

1. Merge on `main` after validation. The operator pushes it.
2. On each host, run `--container-setup` (the launcher digest changed).
3. Rollback: revert the merge and rerun setup.
