# Spec Delta

## REMOVED Requirements

### Requirement: Verified launch engine
**Reason**: Moved to `container-launcher` when host Podman delegation is retired in `sandbox-ref-36`.
**Migration**: See `container-launcher` requirement `Verified launch engine`.

### Requirement: Complete verification responses
**Reason**: Launch verification response boundaries moved to `container-launcher`, and delegation response validation is obsolete after host Podman delegation removal.
**Migration**: See `container-launcher` requirement `Complete launch verification responses`.

### Requirement: Exact explicit delegation
**Reason**: Host Podman delegation (`OPENCODE_CONTAINER_PODMAN=1`) is removed in `sandbox-ref-36`.
**Migration**: Register container images with `--container-toolchain add` so sessions run them through the private `session-container-engine`.

### Requirement: Verified socket selection and host remapping
**Reason**: Host Podman socket mounting and remapping are removed in `sandbox-ref-36`.
**Migration**: Sessions with image toolchains reach their private engine over loopback TCP (`CONTAINER_HOST` / `DOCKER_HOST`); see `session-container-engine`.

### Requirement: Preserve host security policy
**Reason**: Host Podman delegation is removed; session hardening remains specified in `container-isolation` and engine exceptions in `session-container-engine`.
**Migration**: See `container-isolation` and `session-container-engine`.

### Requirement: Delegation only in unrestricted mode
**Reason**: Host Podman delegation is removed in all modes, including `unrestricted`.
**Migration**: Exact `OPENCODE_CONTAINER_PODMAN=1` now stops every launch with migration guidance; see `container-launcher`.
