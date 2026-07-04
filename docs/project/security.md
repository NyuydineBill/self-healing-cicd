# Security Policy

See also the [architecture overview](../architecture/overview.md) and [documentation index](../README.md).

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | Yes       |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Send a private report to **info@umemployed.com** with:

1. A description of the vulnerability and its potential impact.
2. Steps to reproduce (minimal example preferred).
3. Any suggested mitigations you are aware of.

You can expect an acknowledgement within **72 hours** and a status update within **7 days**.

## Security Design Notes

- **Secrets masking** — GitHub tokens and OpenAI keys are redacted from all log output by `utils/secrets.py`.
- **Path allowlist** — `ALLOWED_PATH_PREFIXES` in `.env` restricts which files the patcher may touch.
- **File backups** — `BACKUP_BEFORE_PATCH=true` (default) saves originals before any write; failed validation triggers automatic restore.
- **Approval gates** — `REQUIRE_APPROVAL=true` (default) requires human sign-off before a patch is written.
- **Prompt injection mitigation** — `utils/prompts.py` strips control characters and redacts known injection patterns before interpolating log content into LLM prompts.
- **Audit trail** — Every patch write, rejection, and PR is recorded as a structured JSON line in `results/audit.log`.

## Known Limitations

- LLM-generated patches are not formally verified. A patch that passes the scoped test suite may still introduce bugs in untested code paths.
- The web approval UI (`WEB_APPROVAL_ENABLED`) has no authentication. Run it only on loopback (`127.0.0.1`) or behind a firewall.
- API keys are loaded from environment variables / `.env`. Use a secrets manager (Vault, AWS Secrets Manager) in production.
