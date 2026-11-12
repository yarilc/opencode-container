# runtime-image Specification

## Purpose

Provide one generic, reproducible OpenCode runtime image with the common toolset, pinned inputs, an explicit update procedure and a default-deny build context.

## Requirements

### Requirement: Generic image with the common toolset
The image SHALL be built on `docker.io/library/node:22-bookworm-slim` referenced by digest and SHALL provide OpenCode, OpenSpec and the common toolset shared with the other wrappers. It SHALL NOT contain a user name, UID, GID or home derived from the caller, and its entrypoint SHALL run OpenCode directly.

#### Scenario: Common toolset
- **WHEN** the recipe is inspected
- **THEN** it installs `bash`, `bubblewrap`, `bzip2`, `ca-certificates`, `coreutils`, `curl`, `diffutils`, `file`, `findutils`, `gawk`, `git`, `grep`, `jq`, `less`, `nano`, `patch`, `podman`, `procps`, `python3`, `ripgrep`, `sed`, `tar`, `unzip`, `util-linux`, `xz-utils` and `zip`

#### Scenario: Tool inventory
- **WHEN** image verification runs in a session as the mapped non-root user
- **THEN** each listed tool, `opencode` and `openspec` are available and the image metadata defines no user-specific build argument

#### Scenario: Interactive interface on glibc
- **WHEN** OpenTUI starts in a PTY on the generic image with the executable `/tmp`
- **THEN** the interface renders and quits cleanly

### Requirement: Runtime image inputs are pinned
The image recipe SHALL install exact `opencode-ai` and `@fission-ai/openspec` versions recorded in the repository and SHALL reference the base image by registry digest. No floating tag, `latest` specifier or version range SHALL select an image input. The recipe SHALL use the npm registry, which verifies each package's recorded integrity. Sessions SHALL NOT change the installed OpenCode or OpenSpec version.

#### Scenario: Build uses recorded versions
- **WHEN** the image is built with `--container-build`
- **THEN** `opencode --version` and `openspec --version` report exactly the recorded versions and the base layer comes from the recorded digest

#### Scenario: Unpinned input is rejected by tests
- **WHEN** the recipe uses a base image without digest, an OpenCode or OpenSpec package without exact version or with `@latest`, or a third-party OpenCode image
- **THEN** the credential-free unit suite fails

### Requirement: Version updates follow explicit maintenance
Documentation SHALL describe the update procedure:
- record the new OpenCode version, OpenSpec version or base digest in the recipe;
- re-read the OpenCode provider metadata and the permission merge behavior for the new version;
- rebuild explicitly with `--container-build`;
- rerun the credential-free and real-engine checks, including OpenTUI;
- record the tested versions with the date in the validation record.

#### Scenario: Maintainer updates OpenCode
- **WHEN** a maintainer follows the documented procedure to move to a new OpenCode release
- **THEN** the procedure requires the recorded version, an explicit rebuild, the provider and permission rechecks, a rerun of the checks and a dated validation entry

### Requirement: Default-deny build context
The effective Podman build context MUST allow only the root `Containerfile`, the root `.containerignore`, `network/relay.py` and `network/mux.py`. The image SHALL copy the two network files to `/opt/sandbox-egress/` and SHALL NOT contain the guard, which is mounted from the protected installation at launch. Unknown files, nested lookalikes, repository metadata, local state, and credentials MUST be excluded.

#### Scenario: Probe context contents
- **WHEN** a disposable build context includes unknown root files, nested recipe names, and synthetic credentials
- **THEN** a build that copies the whole context sees only the four allowed files, and attempts to consume any unlisted input fail

### Requirement: Pinned CLI matches the tested policy version
The pinned OpenCode version SHALL equal the CLI version recorded in the protected network policy's tested metadata. A version change SHALL update both in the same change and record the tested version in the validation record.

#### Scenario: Versions diverge
- **WHEN** the pinned OpenCode version differs from the policy's tested CLI field
- **THEN** the credential-free unit suite fails and names both versions

### Requirement: Restricted sessions use an immutable runtime image identity
Offline and provider launches SHALL resolve the selected runtime image to its immutable image ID before preparation and SHALL create the agent container from that ID. An unresolvable or malformed identity SHALL stop startup. Unrestricted launches MAY keep using the image name.

#### Scenario: Image tag moves during a launch
- **WHEN** the selected tag is rebuilt after a restricted launch has resolved its identity
- **THEN** the session and its qualification check use the resolved ID, not the moved tag

#### Scenario: Identity cannot be resolved
- **WHEN** image inspection fails or returns a malformed ID in a restricted mode
- **THEN** startup fails before agent execution

### Requirement: Proxy image acquisition requires maintenance and a digest
Provider mode SHALL use the immutable egress proxy image named by `OPENCODE_CONTAINER_EGRESS_IMAGE`. An absent proxy image SHALL be pulled only with exact `OPENCODE_CONTAINER_MAINTENANCE=1` and only when the reference is pinned by digest. Otherwise startup SHALL fail with maintenance guidance before agent execution.

#### Scenario: Proxy image absent without authorization
- **WHEN** the proxy image is absent and maintenance is not authorized or the reference has no digest
- **THEN** startup fails without pulling and names the required operator action

### Requirement: Image package sources use verified HTTPS
The runtime image recipe SHALL fetch Debian packages only from `https://` sources, with TLS peer verification enabled for every fetch. The build SHALL NOT require outbound port 80 and SHALL NOT fall back to plain HTTP. The built image SHALL keep HTTPS Debian sources.

#### Scenario: Host blocks outbound port 80
- **WHEN** the runtime image is built under maintenance authorization on a host where outbound TCP 80 is blocked and HTTPS to the Debian, npm and container registries is reachable
- **THEN** the build completes and the image reports the recorded OpenCode and OpenSpec versions

#### Scenario: Built image keeps HTTPS sources
- **WHEN** a user inspects the Debian source configuration inside a container started from the runtime image
- **THEN** every Debian source URI uses `https://`

#### Scenario: Insecure transport is rejected by tests
- **WHEN** the recipe uses a plain-HTTP Debian source or disables apt TLS peer or host verification
- **THEN** the credential-free unit suite fails and names the violation

### Requirement: Package-source trust bootstrap uses pinned inputs and opt-in host CA
Before Debian `ca-certificates` is installed, the recipe SHALL verify HTTPS package fetches with roots from the digest-pinned base image, plus the operator's selected CA bundle only when host CA trust is enabled. It SHALL add no image, digest or download input. It SHALL remove the bootstrap bundle in the same build step, and the built image SHALL contain Debian `ca-certificates`.

#### Scenario: No bootstrap residue
- **WHEN** a user lists the bootstrap bundle path inside a container started from the runtime image
- **THEN** the file does not exist
- **AND** the Debian `ca-certificates` package is installed

#### Scenario: Host CA trust disabled
- **WHEN** setup or `--container-build` builds the runtime image with host CA trust disabled
- **THEN** the build receives no host CA bundle and verifies only against the base image's roots

#### Scenario: TLS-intercepting network with host CA trust
- **WHEN** setup or `--container-build` builds the runtime image with host CA trust enabled and a CA bundle that includes the network's interception CA
- **THEN** the build receives that bundle only as a build secret, the HTTPS package fetches verify against it, and the build completes

#### Scenario: Host CA bundle is not persisted
- **WHEN** a user searches a container started from an image built with host CA trust enabled
- **THEN** neither the bootstrap bundle nor the build secret is present in the image

### Requirement: Image working directory exists in the image
The runtime image SHALL contain its configured working directory `/workspace` in an image layer, owned by root with mode 755, so that a container started without `--workdir` never makes the engine create or chown it at start.

#### Scenario: Container started without an explicit workdir
- **WHEN** a qualification gate container starts from the runtime image without `--workdir`
- **THEN** the engine uses the existing `/workspace` and performs no workdir creation or ownership change

#### Scenario: Host with a large domain UID
- **WHEN** the caller's UID, for example 31600276, cannot be used for an engine-side chown under `--userns=keep-id`
- **THEN** qualification containers still start, because no workdir chown is needed

#### Scenario: Recipe regression is rejected by tests
- **WHEN** the recipe declares `WORKDIR /workspace` without creating `/workspace` in a build step
- **THEN** the credential-free unit suite fails
