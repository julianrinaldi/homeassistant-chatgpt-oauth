# Validation report — ChatGPT OAuth 1.1.0

This report separates checks completed against the release source from checks that require GitHub Actions, a full Home Assistant test environment, or a real ChatGPT OAuth account.

## Source-tree checks completed

The 1.1.0 release build validates the following locally before archives are produced:

- Every Python file compiles under the available Python runtime.
- `manifest.json`, `hacs.json`, `strings.json`, `translations/en.json`, and `icons.json` parse as JSON.
- GitHub Actions, issue forms, Dependabot configuration, and service metadata parse as YAML.
- `pyproject.toml` parses as TOML.
- The manifest, Python project, public documentation, and release artifacts use version `1.1.0` consistently.
- `strings.json` and `translations/en.json` contain the same English content.
- The public integration name remains `ChatGPT OAuth` while the stable internal domain remains `openai_oauth_conversation`.
- Existing entries migrate with web search disabled, preserving the pre-1.1 behavior unless the user explicitly enables it.
- Web-search modes normalize to Disabled, Automatic, or Required and context size normalizes to Low, Medium, or High.
- Native web search forces the full Responses transport for every supported model while non-search GPT-5.6 requests retain Responses Lite.
- Current `web_search` payloads support context size, live-versus-cache access, optional country/time-zone location hints, and a domain allowlist of at most 100 domains.
- Required mode rejects an answer that contains neither a web-search call nor a URL citation.
- Compatibility retries never silently remove a domain allowlist or convert cache-only search into live browsing.
- The legacy `web_search_preview` fallback is used only when doing so does not weaken an explicit privacy or domain restriction.
- Completed and streamed URL citations are parsed, deduplicated, rendered as safe clickable Markdown, and exposed as serializable metadata.
- Complete consulted-source URLs and search actions are parsed and deduplicated.
- Unsafe URLs containing credentials, control characters, or unsupported schemes are never rendered as links.
- Every supported model/thinking-level combination produces a valid request, and `Ultra` maps to `Max` at request time without changing the saved selection.
- Serialized request bodies are ASCII JSON, recursively reject the obsolete hosted-backend output-limit field, and continue to use `aiohttp`'s `data=` path instead of Home Assistant's shared `json=` serializer.
- The chunk-safe SSE parser accepts multi-megabyte response events without relying on `aiohttp.readline()`.
- Image generation remains isolated from web search and retains its existing attachment, signature, size, stream, and result validation.
- OAuth token refresh remains serialized per config entry, preserves a non-rotated refresh token, and starts Home Assistant reauthentication after a rejected refresh.
- Diagnostics omit OAuth credentials, account identifiers, prompts, attachments, conversation content, generated output, and exact home coordinates.
- The repository contains no `.storage`, `.env`, OAuth credential file, Python cache, compiled Python file, or Git metadata in release archives.
- The manual-install archive and complete repository archive pass ZIP integrity tests and extract byte-for-byte to the final release source.
- The binary upgrade patch applies cleanly to the exact 1.0.0 source and reproduces the 1.1.0 source tree byte-for-byte.

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

The Home Assistant test-plugin versions are pinned to releases that embed the Home Assistant versions shown in the test matrix.

## Checks requiring the published repository

The following checks must complete on GitHub after the repository is pushed:

- HACS Action result.
- Hassfest Action result.
- Both Home Assistant test-matrix jobs.
- Ruff format and lint jobs.
- Release-check workflow on tag `v1.1.0`.
- GitHub release archive generation.

A default HACS submission should not be opened until all required workflows are green.

## Checks requiring a real account

A live hosted-backend smoke test requires the maintainer's own ChatGPT OAuth session. Before publishing, test each account-visible model with a supported thinking level:

1. Assist with search Disabled, Automatic, and Required.
2. `ai_task.generate_data` plain text with search Disabled, Automatic, and Required.
3. A required search that returns visible clickable citations.
4. The dedicated `openai_oauth_conversation.web_search` action and all response fields.
5. Cache/index-only search with live access disabled.
6. Search with Home Assistant country/time-zone hints enabled.
7. Search restricted to an allowed-domain list.
8. Search alongside Home Assistant LLM tools when Assist control is enabled.
9. Structured `ai_task.generate_data`, noting that native structured results return the requested schema while the dedicated web-search action is the source-metadata path.
10. Existing image generation and image/PDF analysis regression checks.
11. Token refresh or reauthentication using a test entry whose access token is near expiry.

Do not commit captured requests, OAuth tokens, callback URLs, account identifiers, prompts, attachments, search history, or generated private content while performing these checks.

## Local environment limitation

The release source was compiled and exercised with focused request, response, citation, fallback, serialization, migration, metadata, and packaging checks. The complete Home Assistant pytest matrix and Ruff executable were not available in this isolated build container; the repository's pinned GitHub Actions are the authoritative full-environment checks before publication.
