# Spec Delta

## Purpose

Define the persistent and ephemeral filesystem boundaries and environment inputs available to an OpenCode sandbox session.

## ADDED Requirements

### Requirement: Private persistent state preflight
Before image operations the wrapper SHALL privately create missing OpenCode config/data/cache/state directories, physically resolve each, and verify caller ownership, read/write/traverse access, and no group/other permission bits. It MUST reject insecure existing paths without chmod/chown or credential copying. Creation MUST NOT change the caller's umask.

#### Scenario: Missing directories
- **WHEN** one or more writable OpenCode XDG directories do not exist
- **THEN** they are created with private permissions under a scoped creation umask and validated before image inspection or building

#### Scenario: Existing state fails validation
- **WHEN** a resolved directory is inaccessible, belongs to another user, has group/other permissions, is a broken symlink, or is not a directory
- **THEN** startup stops before image operations with a path-specific diagnostic
- **AND** existing permissions, ownership, and credentials remain unchanged

### Requirement: Consistent effective HOME and XDG layout
The session SHALL use the host HOME, including nonstandard absolute homes, and effective XDG bases consistently across wrapper mounts and the OpenCode entrypoint. Each OpenCode state directory MUST resolve to its validated physical mount destination; other host HOME content MUST NOT become writable or be mounted implicitly.

#### Scenario: Nonstandard HOME and symlinked XDG base
- **WHEN** HOME differs from `/home/<username>` and an XDG base resolves through a symlink
- **THEN** OpenCode observes that HOME and XDG paths that lead to the validated physical config/data/cache/state mounts
- **AND** no entrypoint reset redirects OpenCode toward an unmounted home

### Requirement: Physical bind paths and integration boundaries
The wrapper SHALL preserve physical absolute workspace and state bind sources, support spaces and commas without argument splitting, and start in the original physical working directory. Only the workspace, four OpenCode state directories, and explicitly enabled service socket SHALL be host-writable. Existing optional `.claude`, `.agents`, and `/etc/opencode` mounts MUST remain read-only.

#### Scenario: Paths contain delimiters
- **WHEN** workspace, XDG, optional integration, or reported socket paths contain spaces or commas
- **THEN** the intended complete paths are mounted with the specified access mode

#### Scenario: Optional integrations
- **WHEN** optional integration directories exist
- **THEN** they are mounted read-only at their intended destinations
- **AND** the host home, SSH/AWS/Docker directories, global Git configuration, and Podman configuration are not implicitly mounted

### Requirement: Explicit ephemeral storage
The root filesystem SHALL remain read-only with automatic read-only tmpfs provisioning disabled. `/tmp`, `/var/tmp`, and `/run` MUST have explicit ephemeral tmpfs mounts with capacity limits, nosuid/nodev, and modes permitting the mapped user to use them. `/tmp` MUST remain executable for OpenTUI.

#### Scenario: Effective mount flags
- **WHEN** a real session inspects its mounts
- **THEN** `/tmp` is executable, nosuid/nodev, mode 1777, and limited to 512 MiB
- **AND** `/var/tmp` is noexec, nosuid/nodev, mode 1777, and limited to 512 MiB
- **AND** `/run` is noexec, nosuid/nodev, mode 1777, and limited to 32 MiB

#### Scenario: Temporary lifetime and renderer startup
- **WHEN** files are written to temporary mounts and the session ends
- **THEN** a subsequent session does not retain those files
- **AND** interactive OpenTUI startup can extract and load its shared library from `/tmp`

### Requirement: Explicit environment allowlist without credential arguments
The wrapper MUST retain its explicit environment allowlist and forward allowed nonempty inherited values by variable name, excluding their values from engine-client arguments. Deliberate nonsecret identity/path assignments SHALL remain explicit. No forwarded or image-default environment setting MUST override disabled delegation.

#### Scenario: Credential forwarding
- **WHEN** an allowed exported API key or password and an unlisted variable are set
- **THEN** the allowed value reaches the session through `--env VARIABLE` and is absent from wrapper-generated Podman arguments
- **AND** the unlisted value is not forwarded
- **AND** documentation states that container processes and engine inspection can still observe forwarded credentials

### Requirement: Preserve sandbox identity and hardening
The sandbox SHALL retain keep-id, the host username and numeric UID/GID, capability dropping, no-new-privileges, and the existing 512-process limit.

#### Scenario: Session identity
- **WHEN** the image is built and a session starts
- **THEN** the process has the host username and numeric identity and the existing hardening settings remain active
