# Spec Delta

## ADDED Requirements

### Requirement: Separate runtime and session engine images
OpenCode's runtime image (`localhost/opencode-cli:latest`, built from `Containerfile`) and its session container engine image (`localhost/opencode-cli-engine:latest`, built from `launcher/engine/Containerfile` by guided setup) SHALL remain separate images with distinct inputs and lifecycles. Runtime builds (`--container-build`) SHALL remain independent of the session engine image.

#### Scenario: Derived engine image name
- **WHEN** guided setup prepares the session container engine for OpenCode's profile (`images.agent = localhost/opencode-cli`)
- **THEN** setup builds and records `localhost/opencode-cli-engine:latest` without modifying `localhost/opencode-cli:latest`
