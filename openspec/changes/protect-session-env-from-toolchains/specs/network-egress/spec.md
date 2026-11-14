# Spec Delta

## MODIFIED Requirements

### Requirement: Optional traffic remains opt-in
Provider sessions SHALL disable these OpenCode features where the tested version supports it:
- automatic updates;
- default plugin downloads;
- LSP binary downloads;
- the remote model catalog fetch;
- session sharing.

The wrapper SHALL use protected environment values, set after forwarding and after toolchain variables, that writable OpenCode configuration, forwarded variables and toolchains cannot override. A missing disable control SHALL NOT broaden the allowlist. Shell and YOLO modes SHALL keep the same outer restrictions.

#### Scenario: Optional feature attempts outbound access
- **WHEN** a disabled feature or writable setting attempts an update, plugin, LSP, catalog, share, telemetry or MCP request to an unapproved host
- **THEN** the proxy denies it without adding vendor or CDN wildcards

#### Scenario: Protected values cannot be overridden
- **WHEN** the operator lists an optional-traffic variable in `OPENCODE_CONTAINER_ENV_VARS` or the host sets it to another value
- **THEN** the session receives the protected value

#### Scenario: Toolchain cannot reenable optional traffic
- **WHEN** a default toolchain in the shared library sets `OPENCODE_DISABLE_AUTOUPDATE=0` or another disable control, in a restricted mode
- **THEN** the session receives the protected value `1`

#### Scenario: Provider-hosted tools
- **WHEN** OpenCode uses a provider-hosted tool such as remote web search
- **THEN** documentation states that this network activity happens at the provider, outside the local boundary
