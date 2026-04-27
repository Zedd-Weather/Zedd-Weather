# Release Policy

This document describes how Zedd Weather versions, releases, and support expectations are managed.

## Versioning

Zedd Weather uses semantic versioning principles where practical:

- **Major** versions may include breaking API, configuration, deployment, or hardware behavior changes.
- **Minor** versions add backwards-compatible features, sensors, endpoints, policy updates, or operational improvements.
- **Patch** versions fix bugs, security issues, documentation defects, and small compatibility issues.

The PiNet DApp version in `public/dapp.json` should be updated when releasing user-visible DApp changes.

## Release Readiness

Before publishing a release, maintainers should verify:

- Python linting passes.
- Type checks pass for the configured mypy targets.
- The pytest suite passes.
- Docker images build for supported platforms.
- CodeQL or equivalent security analysis has run.
- Documentation and policy changes are included.
- `.env.example` and `.env.production.example` match the runtime configuration surface.
- New external services, credentials, or data flows are reflected in [SECURITY.md](SECURITY.md) and [PRIVACY.md](PRIVACY.md).

## Release Notes

Release notes should summarize:

- New features and changed behavior
- Bug fixes
- Security fixes or hardening changes
- Configuration or migration steps
- Hardware compatibility notes
- Known limitations

Do not disclose sensitive vulnerability details before affected users have a reasonable opportunity to update.

## Supported Versions

Only the latest release on the `main` branch is actively supported unless maintainers announce a longer support window for a specific version.

Security fixes are prioritized for the latest supported version. Older versions may receive guidance, but maintainers are not expected to backport fixes unless explicitly stated.

## Deprecations and Breaking Changes

Deprecations should be documented before removal when possible. Breaking changes should include migration guidance in the release notes or documentation.

Breaking changes include, but are not limited to:

- Removing or renaming REST endpoints
- Changing telemetry key names or units
- Changing risk-score semantics
- Requiring new mandatory secrets
- Changing Docker service names, exposed ports, or volume expectations
- Changing hardware driver fail-closed behavior

## Emergency Security Releases

For critical vulnerabilities, maintainers may publish an emergency patch with a shortened review cycle. Follow-up documentation, tests, and hardening work should be completed as soon as practical.
