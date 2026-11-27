# Spec Delta

## MODIFIED Requirements

### Requirement: OpenCode launcher tests cover only OpenCode's part
OpenCode's launcher behavior (including leftover delegation refusal, session container engine wiring, and budgets) SHALL be tested by the shared `tests/test_launcher.py` and `tests/fake_podman.py`, copied unchanged from `sandbox-ref-36`. `tests/test_wrapper.py` SHALL test only OpenCode's hooks, agent data, credential rules per policy profile, shipped policy inventories, and OpenCode-specific option handling. An OpenCode launcher case that the shared tests do not cover SHALL be added to the reference first, not kept as a wrapper copy.

#### Scenario: Wrapper runtime tests
- **WHEN** `bash tests/run-runtime.sh --wrapper` runs
- **THEN** it runs both `tests/test_launcher.py` and `tests/test_wrapper.py` against this checkout
