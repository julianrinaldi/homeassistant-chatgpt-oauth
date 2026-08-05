# Owner release checklist — ChatGPT OAuth 1.0.0

Use this checklist after reviewing the release candidate.

## Repository identity

- [ ] Rename the GitHub repository to `homeassistant-chatgpt-oauth`.
- [ ] Keep the Home Assistant integration directory and domain named `openai_oauth_conversation`.
- [ ] Set the repository description to: `Use ChatGPT OAuth in Home Assistant for Assist, structured AI tasks, image generation, image editing, and multimodal analysis.`
- [ ] Add topics: `home-assistant`, `hacs`, `custom-integration`, `chatgpt`, `oauth`, `ai-task`, `assist`, `image-generation`, and `structured-output`.
- [ ] Enable Issues.
- [ ] Enable private vulnerability reporting.
- [ ] Optionally enable Discussions for community support.

## Branch protection and automation

- [ ] Push the complete v1 repository to the default branch.
- [ ] Confirm the HACS workflow passes.
- [ ] Confirm the Hassfest workflow passes.
- [ ] Confirm both Home Assistant test-matrix jobs pass.
- [ ] Confirm Ruff formatting and linting pass.
- [ ] Protect the default branch and require the validation jobs before merge.
- [ ] Review Dependabot pull-request permissions and cadence.

## Live release smoke test

- [ ] Upgrade an existing v0.5.2 installation without deleting its Home Assistant config entry.
- [ ] Confirm the existing conversation entity retains its entity-registry identity.
- [ ] Confirm the existing AI Task entity retains its entity-registry identity, including an older `image_generation` entity ID when present.
- [ ] Confirm the saved model and thinking level migrate correctly.
- [ ] Test Assist.
- [ ] Test plain and structured `ai_task.generate_data`.
- [ ] Test `ai_task.generate_image` with zero, one, and ten reference images.
- [ ] Confirm eleven image attachments are rejected before transmission.
- [ ] Test image and PDF analysis.
- [ ] Test a Home Assistant LLM tool call.
- [ ] Confirm diagnostics contain no credentials, account ID, prompt, attachment, or generated content.
- [ ] Confirm a near-expiry token refreshes without duplicating refresh requests.

## Publish 1.0.0

- [ ] Review `CHANGELOG.md`, `MIGRATION.md`, `RELEASE_NOTES.md`, and `SECURITY.md`.
- [ ] Commit the final source as `Release 1.0.0`.
- [ ] Create and push the annotated tag `v1.0.0`.
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

- [ ] Watch authentication, model-availability, image-streaming, and structured-output issues closely.
- [ ] Never request unredacted `.storage` files, OAuth callback URLs, tokens, or private prompts in support tickets.
- [ ] Publish backend-compatibility fixes as normal semantic-versioned releases without changing the stable Home Assistant domain.
