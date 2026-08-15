# Changelog

All notable user-facing changes are documented in this file.

## [1.3.0] - 2026-08-15

### Added

- Multiple Assist conversation profiles can now share one ChatGPT OAuth account while keeping independent model, prompt, thinking-level, tool, web-search, and memory settings.
- Configurable conversation memory modes for the current turn, recent turns, summarized older turns, or bounded full history.
- Optional read-only LLM tools for entity history, long-term statistics, and Energy Dashboard data, with exposure checks and bounded query ranges.

### Changed

- Config entries migrate to version 9 and expose profile-specific, non-sensitive diagnostics.
- Existing entries retain full-history behavior with a 64,000-character safety limit; new profiles default to 12 recent turns and a 16,000-character limit.
- The package version is now 1.3.0 and declares the Home Assistant recorder and energy dependencies used by history tools.

### Compatibility

- The stable internal domain, default conversation unique ID, OAuth credentials, existing actions, and existing entity IDs remain unchanged.
- Read-only history tools are disabled by default and never permit database mutation.

## [1.2.1] - 2026-08-14

### Changed

- Corrected all repository URLs, code-owner entries, commit authors, committers, and annotated-tag metadata to use `julianrinaldi`.
- Removed maintainer-only release checklists, private build-validation reports, and tracked release-note staging files from the public repository.
- Changed release automation to generate GitHub release notes without depending on a tracked maintainer file.
- Rebuilt the public Git history beginning with v1.0.0 so historical tags contain the correct repository ownership and public file set.

### Compatibility

- No Home Assistant runtime behavior, OAuth data, config entries, entities, actions, models, thinking levels, web-search behavior, or automations change in this release.
- The stable internal domain remains `openai_oauth_conversation`.

## [1.2.0] - 2026-08-14

### Added

- A configurable **Include sources in response text** setting for OpenAI web search.
- Voice-friendly source presentation for Assist: speech contains only the natural answer while interfaces that support cards receive a separate **Web search sources** card with clickable citations.
- A `cited_text` field in `generate_content`, `analyze_image`, and dedicated `web_search` action responses.
- A per-call `web_search_include_sources` override for all integration text actions.
- Source-presentation state in sanitized diagnostics and AI Task entity attributes.

### Changed

- New and migrated entries default to source-free response text so voice pipelines do not speak citation numbers, URLs, or a source list.
- Citation annotations, unique sources, and reported search actions remain available even when source formatting is hidden from the main text.
- `text` follows the configured or per-call source-display setting; `raw_text` remains the unformatted answer; `cited_text` always provides the clickable cited version.
- Public repository metadata and links now use `julianrinaldi/homeassistant-chatgpt-oauth`.

### Compatibility

- Existing OAuth credentials, config entries, entity IDs, action names, models, thinking levels, and web-search modes are preserved.
- Users who prefer the v1.1 cited-text behavior can enable **Include sources in response text** under Reconfigure.
- The stable internal domain remains `openai_oauth_conversation`.

## [1.1.1] - 2026-08-14

### Fixed

- Corrected the repository and GitHub release packaging for HACS.
- Added a dedicated `chatgpt_oauth.zip` release asset whose integration files are located directly at the ZIP root, as required when HACS extracts a `zip_release` into the integration directory.
- Added a separate `chatgpt-oauth-manual.zip` archive with the normal `custom_components/openai_oauth_conversation` path for manual installation.
- Updated `hacs.json` to declare the exact HACS release filename and ZIP-release behavior.
- Updated the tag workflow to validate both archive layouts and create or update the GitHub release automatically.
- Removed the unnecessary `custom_components/__init__.py` repository file.

### Compatibility

- No integration runtime behavior, config-entry data, OAuth credentials, entities, actions, or automations change in this release.

## [1.1.0] - 2026-08-11

### Added

- Native OpenAI Responses API `web_search` support for Assist, `ai_task.generate_data`, `generate_content`, and `analyze_image`.
- Configurable web-search modes: disabled, automatic, and required.
- Low, medium, and high web-search context sizes.
- Live-internet or cache/index-only search selection through `external_web_access`.
- Optional country-and-time-zone-only Home Assistant location hints.
- A dedicated `openai_oauth_conversation.web_search` action that forces search and returns sourced text, raw text, URL citations, unique sources, and reported search actions.
- Optional domain allowlisting for the dedicated web-search action.
- Machine-readable citation and source metadata in the existing `generate_content` and `analyze_image` action responses.
- Web-search capability and settings in sanitized integration diagnostics and AI Task entity attributes.

### Changed

- GPT-5.6 web-search turns use the full Responses transport required by OpenAI's hosted web-search tool while function-only turns retain Responses Lite.
- Plain-text searched answers preserve the complete generated text, add clickable inline citation markers, and append a source list.
- Required mode validates that the response contains an actual search call or URL citation instead of silently accepting an unsearched answer.
- Web-search responses request complete source lists when supported.
- Setup and reconfiguration now include web-search defaults. Existing entries migrate with web search disabled to preserve previous behavior and privacy expectations.
- Public documentation now covers search configuration, automation use, source metadata, privacy, prompt-injection risk, and troubleshooting.

### Compatibility

- The internal domain remains `openai_oauth_conversation`.
- Existing config entries, OAuth credentials, service calls, entity-registry records, and automations are retained.
- Image generation and its 10-reference-image limit are unchanged.
- The client retries without individually rejected optional search controls and can fall back to `web_search_preview` only when that does not discard cache-only access or a domain allowlist.

## [1.0.0] - 2026-08-05

### Added

- Public identity: **ChatGPT OAuth for Home Assistant**.
- Native Home Assistant Assist conversation agent with a configuration switch for Home Assistant entity inspection and control.
- Native `ai_task.generate_data` support for text and structured output.
- Native `ai_task.generate_image` support for generation, editing, and reference images.
- Up to 10 image attachments per image-generation request.
- Image and PDF attachments for data-generation tasks.
- Model-specific thinking-level selection for GPT-5.6 Sol, Terra, Luna, and GPT-5.5.
- Camera, image entity, local-file, and remote-URL image analysis actions.
- Sanitized diagnostics.
- HACS, Hassfest, lint, test, and release-validation workflows.
- Public migration, security, contribution, and support documentation.

### Changed

- Public-facing integration name changed from **OpenAI OAuth Conversation** to **ChatGPT OAuth**.
- Runtime code is separated into authentication, request transport, content, SSE, response, and structured-output modules.
- OAuth refreshes are serialized per config entry to prevent concurrent token-rotation races.
- Backend errors are classified into authentication, validation, rate-limit, timeout, unavailable-service, and malformed-response failures.
- Attachments and streamed responses have explicit size and timeout protection.
- Image and PDF attachments are validated by file signature before transmission.
- The AI Task entity display name now reflects both data and image capabilities.
- The default model for new entries is GPT-5.6 Terra.
- Home Assistant control access can be enabled or disabled independently of the selected model.

### Compatibility

- The internal domain remains `openai_oauth_conversation`.
- Existing config entries, OAuth credentials, service calls, entity-registry records, and automations are retained.
- Existing conversation and AI Task unique IDs are unchanged.

[1.0.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/releases/tag/v1.0.0
[1.1.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.0.0...v1.1.0

[1.1.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.1.0...v1.1.1
[1.2.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.1.1...v1.2.0
[1.2.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.2.0...v1.2.1
[1.3.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.2.1...v1.3.0
