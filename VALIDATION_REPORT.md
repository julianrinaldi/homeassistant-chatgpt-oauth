# Validation report — ChatGPT OAuth 1.0.0

This report records the checks prepared and executed for the 1.0.0 release candidate. It deliberately separates checks completed against the source tree from checks that require GitHub Actions, a full Home Assistant test environment, or a real ChatGPT OAuth account.

## Source-tree checks completed

The release build process validates the following locally before archives are produced:

- Every Python file compiles under Python 3.13.
- `manifest.json`, `hacs.json`, `strings.json`, `translations/en.json`, and `icons.json` parse as JSON.
- GitHub Actions, issue forms, Dependabot configuration, and service metadata parse as YAML.
- `pyproject.toml` parses as TOML.
- The manifest, Python project, documentation, and release archive use version `1.0.0` consistently.
- `strings.json` and `translations/en.json` contain the same English content.
- The public integration name is `ChatGPT OAuth` while the stable internal domain remains `openai_oauth_conversation`.
- Existing entries migrate with Home Assistant control enabled, preserving prior Assist tool behavior, while new and reconfigured entries can disable it.
- The model catalog contains only the documented model/thinking-level combinations.
- `Ultra` maps to `Max` at request time without changing the saved user selection.
- Serialized request bodies are ASCII JSON and reject the obsolete hosted-backend output-limit field recursively.
- The SSE parser accepts a response event larger than one megabyte without using `aiohttp.readline()`.
- Image dimensions are parsed from both `WIDTHxHEIGHT` strings and `{width, height}` objects.
- Generated image bytes are checked for supported image signatures before being returned to Home Assistant.
- Image generation accepts at most 10 image attachments, validates PNG/JPEG/WebP/GIF signatures, and enforces a 50 MB combined raw attachment limit.
- Data generation accepts signature-validated PNG/JPEG/WebP/GIF images and PDFs and enforces per-file and combined limits.
- OAuth token refresh is serialized per config entry, preserves a non-rotated refresh token, and starts Home Assistant reauthentication after a rejected refresh.
- Diagnostics omit OAuth credentials, account identifiers, prompts, attachments, conversation content, and generated output.
- The repository contains no `.storage`, `.env`, OAuth credential file, Python cache, compiled Python file, or Git metadata in release archives.
- The manual-install archive and complete repository archive pass ZIP integrity tests and extract byte-for-byte to the release source.

## Automated GitHub checks configured

The repository includes workflows for:

- HACS validation.
- Hassfest validation.
- Ruff formatting and linting.
- Python compilation.
- Pytest with coverage.
- Home Assistant 2026.4.0 on Python 3.13.
- Home Assistant 2026.7.4 on Python 3.14.
- Version consistency on release tags.
- Release archive construction.
- Generated/private-file rejection.

The Home Assistant test-plugin versions are pinned to releases that embed the exact Home Assistant versions shown in the test matrix, preventing an accidental test against a different Core release.

## Checks requiring the published repository

The following checks must complete on GitHub after the repository is pushed or renamed:

- HACS Action result.
- Hassfest Action result.
- Both Home Assistant test-matrix jobs.
- Ruff format and lint jobs.
- Release-check workflow on tag `v1.0.0`.
- GitHub release archive generation.

A default HACS submission should not be opened until all required workflows are green.

## Checks requiring a real account

A live hosted-backend smoke test requires the maintainer's own ChatGPT OAuth session. Before publishing, test each account-visible model with a supported thinking level:

1. Assist text response.
2. `ai_task.generate_data` plain text.
3. `ai_task.generate_data` structured output.
4. `ai_task.generate_image` without an attachment.
5. `ai_task.generate_image` with one reference image.
6. Image or PDF analysis.
7. Home Assistant LLM tool execution, when enabled.
8. Token refresh or reauthentication using a test entry whose access token is near expiry.

Do not commit captured requests, OAuth tokens, callback URLs, account identifiers, prompts, attachments, or generated private content while performing these checks.
