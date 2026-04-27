# Governance Policy

This document describes how Zedd Weather is maintained, how decisions are made, and how contributors can participate.

## Project Goals

Zedd Weather aims to provide a reliable, secure, hardware-first weather telemetry and risk-analysis platform for edge deployments. Project decisions should favor:

1. Accurate real-world telemetry over synthetic or hidden fallback data.
2. Operator safety and clear risk communication.
3. Secure handling of credentials, telemetry, and infrastructure.
4. Maintainable Python-first architecture.
5. Practical deployment on Raspberry Pi and Docker environments.

## Roles

### Maintainers

Maintainers are responsible for reviewing pull requests, triaging issues, publishing releases, enforcing policies, and protecting the health of the project.

### Contributors

Contributors may open issues, discuss designs, submit pull requests, improve documentation, add tests, and report vulnerabilities. Contributors are expected to follow [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

### Security Reporters

Security reporters disclose vulnerabilities privately according to [SECURITY.md](SECURITY.md). Security reports are handled with priority over normal feature work.

## Decision Process

Most decisions are made through pull-request review and issue discussion. Maintainers should seek rough consensus, but they may make a final decision when consensus is not possible or when safety, security, or project scope requires a clear direction.

Changes that should receive maintainer review before implementation include:

- Public API changes
- Hardware driver behavior changes
- Data retention, privacy, or security changes
- Deployment topology changes
- New third-party services or external data flows
- Risk-engine threshold or scoring changes that affect safety guidance

## Pull Request Expectations

Pull requests should be focused, documented, and tested. A maintainer may request changes for correctness, safety, maintainability, security, documentation, or scope.

A pull request may be declined if it:

- Introduces synthetic telemetry in production code
- Exposes secrets to the frontend or logs
- Weakens security defaults without a clear migration path
- Adds unnecessary dependencies or external services
- Conflicts with the project goals above
- Lacks tests or documentation for behavior changes

## Issue Triage

Issues are generally triaged by impact:

1. Security vulnerabilities and credential exposure
2. Safety-critical telemetry, alerting, or risk-analysis defects
3. Regressions in supported deployment paths
4. Documentation defects that block setup or operations
5. Feature requests and enhancements

Maintainers may close issues that are duplicates, inactive, unsupported, not reproducible, or outside project scope.

## Policy Changes

Policy changes should be proposed through pull requests and reviewed by maintainers. Security, privacy, and governance changes should explain the reason for the change and any impact on operators or contributors.

## Enforcement

The [Code of Conduct](CODE_OF_CONDUCT.md) applies to all project spaces. Maintainers may moderate discussions, lock threads, remove inappropriate content, or restrict participation to protect the community and project.
