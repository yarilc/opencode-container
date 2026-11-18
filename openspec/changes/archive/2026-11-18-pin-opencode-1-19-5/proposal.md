## Why

The image pins OpenCode 1.18.3 and OpenSpec 1.16.0. On 2026-11-18 the six
repositories agreed on a rule: pin the newest stable release that was at
least 72 hours old at that time. On the npm `opencode-ai` line that the
wrapper installs from, this is **1.19.5** (2026-10-28), because 1.19.6
(2026-11-17) was too new. For OpenSpec it is **2.0.0**.

OpenCode 2.x (2.3.0, 2026-11-13) is stable, but it is published only as
GitHub release binaries. It also changes the runtime: background subagents
and a process daemon. A dedicated change will move to it. Since 1.19.2, the
1.x line no longer offers 2.x as a regular update.

## What Changes

- **`Containerfile`:** `OPENCODE_VERSION` moves from `1.18.3` to `1.19.5` and
  `OPENSPEC_VERSION` from `1.16.0` to `2.0.0`. The base digest is unchanged.
- **`agent/policies/default.json`:** `tested.cli` becomes 1.19.5, with the new
  measurement dates. The README procedure requires a new revision
  (`opencode-2026-11-18-v1`), even when the hosts stay the same.
- **Tests that name the version:**
  - `tests/image-smoke.sh`;
  - `tests/test_image_pins.py`: the diverging-CLI and OpenSpec range mutations;
  - `tests/test_network_runtime.py`, `tests/test_runtime.py` and
    `tests/test_setup_runtime.py`.
- **Documentation:**
  - `AGENTS.md` (the pinned versions and the expected version output);
  - `README.md` (the `--auto` note and the provider table heading);
  - `docs/network-contract.md`, where the profile rows say "Measured on 1.18.3"
    and the optional-traffic section notes session sharing;
  - a dated entry in `docs/validation.md`.
- **Revalidation, following the README procedure:**
  - the provider metadata behind `OPENCODE_CONTAINER_PROVIDER`;
  - how `OPENCODE_PERMISSION` (YOLO) is merged, and how `--auto` is parsed;
  - the provider and optional-traffic hosts and the five `OPENCODE_DISABLE_*`
    controls;
  - OpenTUI startup.
- **Visible upstream changes:**
  - 1.19.1 discontinued session sharing;
  - 1.19.0 stopped automatic update installs;
  - 1.19.4 bundles Bun 1.4.4.

  The record notes what still applies to `OPENCODE_DISABLE_SHARE` and
  `OPENCODE_DISABLE_AUTOUPDATE`. The controls stay set, because they cost
  nothing and still guard older configurations.
- **BREAKING (inside the image):** OpenSpec 2.0 no longer generates `/opsx:*`
  command files.

No shared launcher file changes and no new reference tag.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None expected. If the remeasurement finds a required host change, a
`network-egress` delta is added before implementation goes on. Until then the
change sets `skip_specs: true`.

## Impact

- **Files:**
  - `Containerfile` and `agent/policies/default.json`;
  - the tests listed above;
  - `AGENTS.md`, `README.md`, `docs/network-contract.md` and
    `docs/validation.md`.
- **Image identity:** the image changes. The operator reruns
  `--container-setup` on the three hosts.
- **Deferred:** real-key checks stay with the operator.
- **Follow-up:** a dedicated change for OpenCode 2.x.
