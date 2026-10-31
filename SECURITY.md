# Security Policy

## Supported project status

ORCA is currently a research prototype. Security fixes are handled on a best-effort basis.

## Reporting a vulnerability

Please do not publish credentials, exploit details or sensitive deployment information in a public issue. Contact the repository maintainer privately through the contact method listed on the GitHub profile and include a concise description, impact and reproduction steps.

## Credential handling

- Store provider credentials only in a local `.env` file or a deployment secret manager.
- Never commit `.env`, API keys, passwords or access tokens.
- If a credential is exposed, revoke or rotate it with the provider immediately.
- Restrict CORS origins and add authentication before exposing the API to an untrusted network.
