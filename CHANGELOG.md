# Changelog

All notable user-visible changes are documented here.

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
