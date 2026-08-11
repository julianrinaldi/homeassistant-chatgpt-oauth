# Owner release checklist — ChatGPT OAuth 1.1.0

Use this checklist after reviewing the release candidate.

## Repository identity

- [ ] Use the repository name `homeassistant-chatgpt-oauth`.
- [ ] Keep the Home Assistant integration directory and domain named `openai_oauth_conversation`.
- [ ] Set the repository description to: `Use ChatGPT OAuth in Home Assistant for Assist, AI Tasks, image generation, multimodal analysis, and sourced web search.`
- [ ] Add topics: `home-assistant`, `hacs`, `custom-integration`, `chatgpt`, `oauth`, `ai-task`, `assist`, `image-generation`, `structured-output`, and `web-search`.
- [ ] Enable Issues.
- [ ] Enable private vulnerability reporting.
- [ ] Optionally enable Discussions for community support.

## Branch protection and automation

- [ ] Push the complete 1.1.0 repository to the default branch.
- [ ] Confirm the HACS workflow passes.
- [ ] Confirm the Hassfest workflow passes.
- [ ] Confirm both Home Assistant test-matrix jobs pass.
- [ ] Confirm Ruff formatting and linting pass.
- [ ] Protect the default branch and require validation jobs before merge.
- [ ] Review Dependabot pull-request permissions and cadence.

## Upgrade and regression smoke test

- [ ] Upgrade an existing 1.0.0 installation without deleting its Home Assistant config entry.
- [ ] Confirm the existing conversation and AI Task entities retain their entity-registry identities.
- [ ] Confirm the saved model, thinking level, prompt, and Home Assistant control setting migrate correctly.
- [ ] Confirm web search defaults to Disabled on the migrated entry.
- [ ] Test Assist, plain and structured `ai_task.generate_data`, image generation, image editing, and image/PDF analysis.
- [ ] Confirm exactly ten image-generation attachments remain accepted and eleven are rejected before transmission.
- [ ] Test a Home Assistant LLM tool call.
- [ ] Confirm diagnostics contain no credentials, account ID, prompt, attachment, generated content, search history, or exact coordinates.
- [ ] Confirm a near-expiry token refreshes without duplicate refresh requests.

## Web-search smoke test

For every account-visible model (`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, and `gpt-5.5` when available):

- [ ] Test Automatic mode on a current-information prompt.
- [ ] Test Required mode and confirm at least one visible clickable citation.
- [ ] Test Disabled mode and confirm no web-search tool is sent.
- [ ] Test Low, Medium, and High context where accepted by the account/backend.
- [ ] Test live access enabled.
- [ ] Test cache/index-only access and confirm it never silently becomes live.
- [ ] Test country/time-zone location hints and confirm no coordinates are transmitted.
- [ ] Test the dedicated Web search action with one allowed domain.
- [ ] Test the dedicated Web search action with multiple allowed domains.
- [ ] Confirm a rejected domain filter fails rather than broadening to unrestricted search.
- [ ] Confirm the response includes `text`, `raw_text`, `citations`, `sources`, `searches`, `model`, `reasoning_effort`, `search_context_size`, and `live_access`.
- [ ] Test web search and Home Assistant tools in the same Assist conversation.

## Publish 1.1.0

- [ ] Review `CHANGELOG.md`, `MIGRATION.md`, `RELEASE_NOTES.md`, `VALIDATION_REPORT.md`, and `SECURITY.md`.
- [ ] Commit the final source as `Release 1.1.0`.
- [ ] Create and push the annotated tag `v1.1.0`.
- [ ] Confirm the tag-triggered release-check workflow passes.
- [ ] Create the GitHub release using `RELEASE_NOTES.md`.
- [ ] Attach the release source archive and SHA-256 checksums when desired.
- [ ] Mark the release as the latest stable release.

## HACS publication

- [ ] Verify the public repository, README, license, release, topics, and issue tracker are visible without authentication.
- [ ] Install the published release through HACS as a custom repository on a clean Home Assistant instance.
- [ ] Confirm the integration appears as `ChatGPT OAuth` after restart.
- [ ] Open a HACS default-repository inclusion request only after all required checks pass.
- [ ] Use the exact repository owner account required by HACS submission rules.

## Post-release

- [ ] Watch authentication, model availability, native web-search compatibility, citation rendering, image streaming, and structured-output issues closely.
- [ ] Never request unredacted `.storage` files, OAuth callback URLs, tokens, private prompts, search history, or attachments in support tickets.
- [ ] Publish backend-compatibility fixes as normal semantic-versioned releases without changing the stable Home Assistant domain.
