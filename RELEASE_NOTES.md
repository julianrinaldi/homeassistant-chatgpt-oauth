# ChatGPT OAuth 1.0.0

ChatGPT OAuth 1.0.0 is the first public, HACS-ready release of the integration formerly displayed as OpenAI OAuth Conversation.

## Highlights

- Home Assistant Assist conversation agent with an explicit switch for device and entity tools.
- Native `ai_task.generate_data`, including strict structured output.
- Native `ai_task.generate_image` for generation and editing.
- Up to 10 source or reference images in one image-generation request.
- Image and PDF analysis.
- Model-specific thinking levels for GPT-5.6 Sol, Terra, Luna, and GPT-5.5.
- Concurrent-safe OAuth refresh, clearer errors, sanitized diagnostics, and bounded attachment handling.
- Complete public documentation and automated HACS/Hassfest validation.

## Upgrade compatibility

The internal domain remains `openai_oauth_conversation`. Existing config entries, credentials, entity unique IDs, service names, and automations are preserved. See `MIGRATION.md` for upgrade details.

## Important notice

This is an unofficial community integration that uses a hosted ChatGPT/Codex OAuth backend. It is not affiliated with or endorsed by OpenAI or Home Assistant, and backend behavior can change without notice.
