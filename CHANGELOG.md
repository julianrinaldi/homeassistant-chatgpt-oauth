# Changelog

All notable user-facing changes are documented in this file.

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

[1.0.0]: https://github.com/hebs/homeassistant-chatgpt-oauth/releases/tag/v1.0.0
[1.1.0]: https://github.com/hebs/homeassistant-chatgpt-oauth/compare/v1.0.0...v1.1.0
