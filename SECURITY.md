# Security policy

## Supported versions

Security fixes are provided for the latest released version. Users should upgrade before reporting a problem that has already been fixed in a newer release.

## Reporting a vulnerability

Do not open a public issue for a vulnerability or suspected credential exposure.

Use GitHub's **Report a vulnerability** feature under the repository's Security tab. Include:

- The affected version.
- The Home Assistant version and installation type.
- A concise reproduction that does not contain real credentials or private content.
- The likely impact.
- Any proposed mitigation.

Do not include:

- Access or refresh tokens.
- OAuth callback URLs or authorization codes.
- `.storage` files.
- ChatGPT account identifiers.
- Private prompts, images, PDFs, camera snapshots, or generated content.
- Unreviewed debug logs.

If a credential may have been exposed, remove or reauthenticate the Home Assistant integration and use the ChatGPT account's own security controls to revoke relevant sessions.

## Security scope

Reports are especially welcome for:

- Credential disclosure or unsafe logging.
- Authentication or OAuth state validation failures.
- Unauthorized local-file access.
- Unbounded remote downloads, redirects, attachments, or streamed responses.
- Injection paths that bypass Home Assistant's exposed-entity controls.
- Diagnostics containing private data.

The availability or behavior of the unofficial hosted ChatGPT/Codex backend is outside this repository's control, but integration-side handling of that backend is in scope.
