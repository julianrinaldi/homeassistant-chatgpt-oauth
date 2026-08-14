# Owner release checklist — ChatGPT OAuth 1.1.1

## Repository root

- [ ] Push the **contents** of the repository package to the repository root; do not commit an enclosing `homeassistant-chatgpt-oauth-*` directory.
- [ ] Confirm these paths exist directly at the GitHub repository root:

  ```text
  README.md
  hacs.json
  custom_components/openai_oauth_conversation/manifest.json
  ```

- [ ] Confirm `custom_components` contains exactly one integration directory.
- [ ] Keep the stable Home Assistant directory and domain named `openai_oauth_conversation`.

## Repository metadata

- [ ] Use the repository name `homeassistant-chatgpt-oauth`.
- [ ] Set the description to: `Use ChatGPT OAuth in Home Assistant for Assist, AI Tasks, image generation, multimodal analysis, and sourced web search.`
- [ ] Add topics: `home-assistant`, `hacs`, `custom-integration`, `chatgpt`, `oauth`, `ai-task`, `assist`, `image-generation`, `structured-output`, and `web-search`.
- [ ] Enable Issues and private vulnerability reporting.

## Validation

- [ ] Confirm the HACS workflow passes.
- [ ] Confirm the Hassfest workflow passes.
- [ ] Confirm both Home Assistant test-matrix jobs pass.
- [ ] Confirm Ruff formatting and linting pass.
- [ ] Confirm `hacs.json` contains:

  ```json
  {
    "name": "ChatGPT OAuth",
    "content_in_root": false,
    "zip_release": true,
    "filename": "chatgpt_oauth.zip",
    "hide_default_branch": false,
    "homeassistant": "2026.4.0"
  }
  ```

## Publish 1.1.1

- [ ] Commit the final source as `Release 1.1.1`.
- [ ] Create and push the annotated tag `v1.1.1`.
- [ ] Confirm the **Build release** workflow creates or updates the GitHub release.
- [ ] Confirm the release contains these assets:

  ```text
  chatgpt_oauth.zip
  chatgpt-oauth-manual.zip
  SHA256SUMS.txt
  ```

- [ ] Open `chatgpt_oauth.zip` and confirm `manifest.json` and `__init__.py` are at the ZIP root; it must not contain a `custom_components` directory.
- [ ] Open `chatgpt-oauth-manual.zip` and confirm it contains `custom_components/openai_oauth_conversation/manifest.json`.
- [ ] Mark the release as the latest stable release.

## HACS smoke test

- [ ] Add `https://github.com/hebs/homeassistant-chatgpt-oauth` to HACS as an **Integration** custom repository.
- [ ] Install release `v1.1.1` on a clean Home Assistant instance.
- [ ] Confirm HACS creates `/config/custom_components/openai_oauth_conversation/manifest.json` without an extra nested directory.
- [ ] Restart Home Assistant and confirm **ChatGPT OAuth** is available under **Settings → Devices & services → Add integration**.
- [ ] Upgrade an existing 1.1.0 HACS installation and confirm the existing config entry and entity IDs are retained.

## Runtime smoke test

- [ ] Test Assist.
- [ ] Test plain and structured `ai_task.generate_data`.
- [ ] Test `ai_task.generate_image` with zero, one, and ten reference images.
- [ ] Test image/PDF analysis and a Home Assistant LLM tool call.
- [ ] Test Disabled, Automatic, and Required web-search modes with visible citations.
- [ ] Confirm diagnostics contain no credentials, prompts, attachments, generated content, search history, or exact coordinates.

## HACS default inclusion

- [ ] Verify the repository is public and its README, license, release, topics, issue tracker, and workflows are visible without authentication.
- [ ] Open a default-repository inclusion request only after HACS, Hassfest, tests, and the clean-install smoke test pass.
