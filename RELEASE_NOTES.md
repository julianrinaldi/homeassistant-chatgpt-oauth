# ChatGPT OAuth 1.1.1

ChatGPT OAuth 1.1.1 is a packaging-only maintenance release that makes the project install and update correctly through HACS.

## Fixed

- `hacs.json` now declares `zip_release: true` and the exact release asset name `chatgpt_oauth.zip`.
- The HACS release asset contains `manifest.json`, `__init__.py`, and the rest of the integration directly at the ZIP root. HACS extracts that archive directly into `/config/custom_components/openai_oauth_conversation`.
- A separate `chatgpt-oauth-manual.zip` archive contains the full `custom_components/openai_oauth_conversation` path for manual installations.
- The release workflow validates both layouts, generates checksums, and creates or updates the GitHub release when a `v*` tag is pushed.
- The repository archive is distributed with `README.md`, `hacs.json`, and `custom_components/openai_oauth_conversation` at the repository root rather than inside an additional versioned directory.

## Compatibility

There are no runtime or configuration changes from 1.1.0. Existing OAuth credentials, config entries, entities, model settings, thinking levels, web-search settings, actions, and automations are preserved.

This remains an unofficial community integration and is not affiliated with or endorsed by OpenAI or the Home Assistant project.
