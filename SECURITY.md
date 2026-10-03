# Security Policy

## Supported versions

Only the latest release receives security fixes.

| Version | Supported |
|---------|-----------|
| 1.2.x   | Yes       |
| < 1.2   | No        |

## Reporting a vulnerability

Please do not open a public issue for security problems.

Report privately through GitHub: **Security → Report a vulnerability** on this repository. This sends the report only to the maintainer.

Include:
- What the problem is and which file or script it affects
- Steps to reproduce, ideally with a minimal input
- The impact you think it has

This is a volunteer project. You can expect an acknowledgement within a week. Fixes are released as soon as they're verified, and you'll be credited in the release notes unless you ask not to be.

## Scope

In scope: the scripts in this repository, including the network-facing code in `competitor_diff.py`, `live_data.py`, and `impact.py events fetch-google`, and the GitHub Action templates.

Out of scope: vulnerabilities in Claude Code itself, in GitHub, or in a site you audit with this tool.
