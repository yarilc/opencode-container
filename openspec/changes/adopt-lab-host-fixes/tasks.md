# Tasks

## 1. Adopt sandbox-ref-11

- [x] 1.1 From claude-container, run `python3 -I tools/propagate.py
  ../opencode-container sandbox-ref-10 sandbox-ref-11` (dry run). Verify
  that it lists 21 modified shared files, nothing added, removed or "not
  adopted", and `REFERENCE_COMMIT` `d17e865`.
- [x] 1.2 Stash the change directory (`git stash -u`), run the same command
  with `--apply`, and restore the stash on the new branch. Verify:
  - OpenCode is on `adopt-sandbox-ref-11`;
  - the stash list is empty;
  - `git diff --name-only` lists only the shared files,
    `tests/test_reference_copy.py`, `README.md`, `AGENTS.md`,
    `docs/setup.md` and `docs/network-contract.md`;
  - `python3 -m unittest tests.test_reference_copy tests.test_alignment`
    passes.

## 2. Wrapper test fixtures

- [x] 2.1 In `tests/test_wrapper.py`, copy `network/agent_budgets.py` into
  the fake installation, and make the fake engine answer
  `{{.Host.CgroupControllers}}` from `FAKE_CONTROLLERS`, by default
  `[cpu memory pids]`. Verify that the full unit discovery passes on the
  adopted shared files.

## 3. Launcher

- [x] 3.1 Reduce a `unix://` host socket report to its pathname before the
  socket pattern check (design decision 2). Add wrapper tests:
  - `unix:///host/podman.sock` mounts `/host/podman.sock`;
  - `unix://relative`, `unix://` and `unix:///` are rejected before image
    operations.

  Verify that they pass.
- [x] 3.2 Make budgets follow the delegated controllers (design decision 3):
  - the controller query and its validation;
  - `budget_args`, with `--pids-limit=-1` when `pids` is missing;
  - the notices;
  - the inspection for enforced and unenforced budgets;
  - the help text.

  Make the fake inspection report `0` for unrequested budgets. Add tests:
  - every subset of controllers, with the arguments, notices and start;
  - an unverifiable controller list, rejected before state creation;
  - an unenforced budget present, and an enforced budget missing.

  Verify that they pass.
- [x] 3.3 Replace `--read-only-tmpfs=false` with the `/run/secrets`, `/dev`,
  `/dev/pts` and `/dev/shm` mounts (design decision 4). Update
  `test_tmpfs_and_named_environment`. Add a test asserting the four mounts
  and the unchanged `/tmp`, `/var/tmp`, `/run` and home options:
  - in OpenCode and shell mode, with and without delegation;
  - in offline and provider mode;
  - on the provider proxy, the secrets mask and its budgets.

  Verify that they pass.
- [x] 3.4 Add the `build-ca` secret to `build_current_image` and
  `!/podman-build-secret*` to `.containerignore` (design decision 5). Add
  tests with and without trust, for `--container-build` and for a missing
  image. Verify that they pass, together with the existing build-argument
  assertions.
- [x] 3.5 Run `bash -n opencode-container.sh` and the full
  `python3 -m unittest discover -s tests -p test_wrapper.py`. Verify that
  both pass.

## 4. Runtime image recipe

- [x] 4.1 Port the HTTPS trust bootstrap and add `mkdir -p /workspace` to the
  package step (design decision 6), with comments. Port the transport,
  toolchain and workdir checks into `tests/test_image_pins.py`. Verify that
  `python3 -m unittest tests.test_image_pins` passes and that each mutated
  recipe is rejected.
- [x] 4.2 Build the image with the wrapper's build arguments as
  `localhost/opencode-cli:adopt-ref-11`. Verify:
  - every Debian `URIs:` line is `https://`;
  - `/tmp/apt-bootstrap-ca.pem` is absent and `ca-certificates` is
    installed;
  - `opencode --version` and `openspec --version` report the pinned
    versions;
  - `/workspace` appears in `podman export` with the build time;
  - a `keep-id` container without `--workdir` leaves the time of
    `/workspace` unchanged.

## 5. Documentation

- [x] 5.1 Update `README.md` (hardening and budgets, mounts, image
  preparation) and `AGENTS.md`:
  - conditional budget enforcement, with notices and the exhaustion risk;
  - the `/run/secrets` mask;
  - the `noexec` `/dev`, `/dev/pts` and read-only `/dev/shm`;
  - HTTPS-only image fetches on port 443;
  - the `build-ca` secret;
  - the image working directory.

  Verify that the documented paths and variables match the launcher and
  `--container-help`.

## 6. Validation and publication

- [ ] 6.1 Run the full unit discovery on executable, private, native
  temporary storage. Verify that there are no failures, apart from known
  timing-sensitive tests that pass on a rerun, which are recorded as such.
- [x] 6.2 With the image from 4.2, run `bash tests/run-runtime.sh` with
  `--shared`, `--setup`, `--setup-runtime`, `--qualification`, `--guard`,
  `--network` and the default mode, including `test_opentui_renderer` and
  `test_tools_without_capabilities`. Verify that every mode passes, or
  record it as unavailable on this host.
- [x] 6.3 Fill in the tool's validation-record template in
  `docs/validation.md` with the results of 6.1–6.2, the wrapper adaptations
  and the image ID. Record the operator setups as pending. Verify that every
  check is listed as passed, failed or unavailable.
- [x] 6.4 Verify that the SHA-256 of the five-wrapper parity table matches
  claude-container and Codex.
- [x] 6.5 Commit on `adopt-sandbox-ref-11` with the tool's message and the
  co-author trailer, merge it into `main` with `--no-ff`, and verify that
  `git log --oneline -3` shows the merge.

## Workflow follow-up

- The operator pushes OpenCode `main`, then runs `--container-setup`
  (refresh approved) and a session on this host, the Rocky Linux 9 lab host
  and the newer WSL host. The results are added to `docs/validation.md`.
- Sync the delta specs and archive this change after review.
- Shared follow-up in claude-container: `--workdir /` in `network/qualify.py`
  `Gate.common()`, published as `sandbox-ref-12` and propagated to every
  wrapper.
