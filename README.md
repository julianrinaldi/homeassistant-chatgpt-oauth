<p align="center">
  <img src="assets/logo.png" alt="ChatGPT OAuth for Home Assistant" width="760">
</p>

<p align="center">
  <a href="https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/julianrinaldi/homeassistant-chatgpt-oauth?display_name=tag&sort=semver"></a>
  <a href="https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/actions/workflows/hacs.yml"><img alt="HACS validation" src="https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/actions/workflows/hacs.yml/badge.svg"></a>
  <a href="https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/actions/workflows/hassfest.yml"><img alt="Hassfest" src="https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/actions/workflows/hassfest.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Home Assistant 2026.4.0 or newer" src="https://img.shields.io/badge/Home%20Assistant-2026.4.0%2B-41BDF5">
</p>

# ChatGPT OAuth for Home Assistant

Use a ChatGPT account in Home Assistant for **Assist**, structured AI Tasks, OpenAI web search, image and PDF analysis, image generation, and image editing—without configuring an OpenAI API key.

> [!IMPORTANT]
> This is an **unofficial community integration**. It is not affiliated with, endorsed by, or supported by OpenAI or the Home Assistant project. It uses a hosted ChatGPT/Codex OAuth backend that may change without notice. Do not use it for safety-critical or life-critical automation.

## Features

- Home Assistant Assist conversation agent with optional Home Assistant tool control.
- Native OpenAI `web_search` support with voice-friendly answers and retained citation metadata.
- Configurable disabled, automatic, or required web-search behavior.
- Low, medium, or high search context; live or cache/index-only access; optional approximate Home Assistant location.
- Dedicated web-search action with optional domain allowlisting and machine-readable source metadata.
- Native `ai_task.generate_data` support for text and schema-validated structured output.
- Native `ai_task.generate_image` support for new images, edits, and reference-image workflows.
- Up to **10 image attachments** in one image-generation request.
- Image and PDF attachments for data-generation tasks.
- Camera, image entity, local-file, and remote-URL analysis actions.
- Model-specific thinking-level selection.
- Concurrent-safe OAuth token refresh and Home Assistant reauthentication.
- Large streamed image-response support.
- Diagnostics that exclude credentials, prompts, attachments, and generated content.

## Requirements

- Home Assistant **2026.4.0 or newer**.
- HACS for the recommended installation method.
- A ChatGPT account that can access at least one supported model.
- Outbound HTTPS access from Home Assistant to the ChatGPT and OpenAI authentication services.

No OpenAI API key is required. Availability, usage limits, model access, and web-search access are determined by the signed-in ChatGPT account and workspace.

## Installation

### HACS

When the integration is available in the default HACS catalog:

1. Open **HACS → Integrations**.
2. Search for **ChatGPT OAuth**.
3. Select **Download**.
4. Restart Home Assistant.

### HACS custom repository

Until default-catalog inclusion is complete:

1. Open **HACS → Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/julianrinaldi/homeassistant-chatgpt-oauth` as an **Integration** repository.
4. Search for **ChatGPT OAuth** and select **Download**.
5. Restart Home Assistant.

### Manual installation

1. Download `chatgpt-oauth-manual.zip` from the desired GitHub release.
2. Extract the archive into the Home Assistant configuration directory (`/config`).
   The archive already contains the required path:

   ```text
   custom_components/openai_oauth_conversation
   ```

3. Restart Home Assistant.

The separate `chatgpt_oauth.zip` release asset is packaged specifically for HACS and contains the integration files at the ZIP root. Do not extract that asset directly into `/config`.

The internal integration domain remains `openai_oauth_conversation` for backward compatibility.

## Setup and authentication

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **ChatGPT OAuth**.
4. Enter a friendly name and select a model.
5. Choose whether the Assist agent may inspect and control entities exposed to Assist.
6. Choose the default OpenAI web-search mode, search context size, whether sources should appear in response text, live-access behavior, and whether approximate Home Assistant location may be used.
7. Optionally customize the system prompt.
8. Choose a thinking level supported by the selected model.
9. Open the displayed ChatGPT sign-in link.
10. Complete sign-in in the browser.
11. The browser will finish at a localhost callback page. It may display a connection error; that is expected because the callback is intended for the local Codex client.
12. Copy the **entire callback URL** from the address bar and paste it into Home Assistant.

The callback URL contains a short-lived authorization code. Treat it as sensitive and do not post it in issues or logs.

## Supported models and thinking levels

| Model | Available thinking levels | Default |
|---|---|---|
| GPT-5.6 Sol (`gpt-5.6-sol`) | Low, Medium, High, Extra high, Max, Ultra | Low |
| GPT-5.6 Terra (`gpt-5.6-terra`) | Low, Medium, High, Extra high, Max, Ultra | Medium |
| GPT-5.6 Luna (`gpt-5.6-luna`) | Low, Medium, High, Extra high, Max | Medium |
| GPT-5.5 (`gpt-5.5`) | Low, Medium, High, Extra high | Medium |

The setup and reconfiguration screens only show levels compatible with the selected model. `Ultra` uses the model's `Max` reasoning level; Codex's separate subagent-delegation runtime is not available inside Home Assistant.

Model and web-search availability are controlled by the hosted service and the signed-in account. A listed capability can be temporarily unavailable or restricted by a workspace policy.

## OpenAI web search

The integration uses OpenAI's native Responses API `web_search` tool. Search results can be used by Assist, plain-text AI Tasks, `generate_content`, and `analyze_image`. A separate `web_search` action forces a sourced search and returns citation metadata.

Configure the default behavior under **Settings → Devices & services → ChatGPT OAuth → Reconfigure**:

| Setting | Behavior |
|---|---|
| **Disabled** | The web-search tool is not sent to the model. |
| **Automatic** | The model may search when the request benefits from current or external information. |
| **Required** | A search is required; the integration rejects the response if no search evidence is returned. |
| **Context: Low** | Smaller search-result context for quick lookups. |
| **Context: Medium** | Balanced default. |
| **Context: High** | More result context for detailed research. |
| **Include sources in response text** | Adds clickable citation markers and a `Sources` section. This is disabled by default so voice assistants speak a natural answer. |
| **Live access enabled** | Search may fetch current external pages. |
| **Live access disabled** | Search is limited to OpenAI's cached or indexed content when supported. |
| **Use Home Assistant location** | Sends only Home Assistant's country and time zone as an approximate hint. Coordinates and the configured home name are not sent. |

When **Include sources in response text** is disabled, the spoken Assist response and normal `text` output contain only the natural answer. Citation annotations, unique sources, and reported search actions are still retained. Assist places the fully cited answer in a separate **Web search sources** card for interfaces that display cards, while the dedicated integration actions expose a separate `cited_text` value plus structured citation metadata.

Enable **Include sources in response text** when the answer is intended for a dashboard, notification, or document and should contain clickable Markdown citations and a `Sources` section directly in the main text.

### Assist with web search

Set the integration's web-search mode to **Automatic** or **Required**, then use the ChatGPT OAuth conversation agent in an Assist pipeline. The same request may expose Home Assistant tools when **Enable Home Assistant control** is on.

Web pages are untrusted input. Avoid exposing sensitive or safety-critical Home Assistant actions to Assist, and review the model's answer before relying on searched instructions.

### `ai_task.generate_data` with web search

The AI Task entity uses the integration's configured search settings:

```yaml
- action: ai_task.generate_data
  data:
    task_name: current_release_summary
    entity_id: ai_task.chatgpt_oauth_ai_task
    instructions: >-
      Find the latest stable Home Assistant release and summarize its three
      most important user-facing changes.
  response_variable: release_summary

- action: persistent_notification.create
  data:
    title: Home Assistant release
    message: "{{ release_summary.data }}"
```

For free-text tasks, source formatting follows the integration setting. With the default voice-friendly setting, `release_summary.data` contains only the answer. Enable source inclusion when the AI Task output itself must contain citations. Structured-output tasks return only the fields declared by the Home Assistant `structure`; use the dedicated web-search action when an automation needs separate citation metadata.

### Dedicated web-search action

`openai_oauth_conversation.web_search` always requires a search. It supports per-call model and thinking-level overrides, context size, live/cache behavior, approximate location, and an optional allowlist of up to 100 domains.

```yaml
- action: openai_oauth_conversation.web_search
  data:
    config_entry: 0123456789abcdef0123456789abcdef
    query: >-
      What is the latest stable Home Assistant release, and what are its most
      important breaking changes?
    model: gpt-5.6-terra
    reasoning_effort: high
    web_search_context_size: high
    web_search_include_sources: false
    web_search_live_access: true
    allowed_domains:
      - home-assistant.io
      - github.com
  response_variable: research
```

Common response values:

```jinja2
{{ research.text }}
{{ research.raw_text }}
{{ research.cited_text }}
{{ research.citations }}
{{ research.sources }}
{{ research.searches }}
{{ research.model }}
{{ research.reasoning_effort }}
{{ research.search_context_size }}
{{ research.include_sources_in_text }}
{{ research.live_access }}
```

`research.text` follows the selected source-display setting. `research.raw_text` is the unformatted model answer, and `research.cited_text` always contains the clickable cited version. Each item in `research.citations` contains `url`, `title`, `start_index`, and `end_index`. Each item in `research.sources` contains `url` and `title`. `research.searches` records search, page-open, or find-in-page actions reported by the hosted tool.

Allowed domains must be hostnames such as `home-assistant.io` or `developers.openai.com`; do not include a URL path, query, or fragment.

## Home Assistant Assist

After setup, choose the new conversation agent in an Assist pipeline:

1. Open **Settings → Voice assistants**.
2. Create or edit a pipeline.
3. Select the ChatGPT OAuth conversation agent under **Conversation agent**.

When **Enable Home Assistant control** is turned on, the agent receives Home Assistant's Assist tool API and may inspect or control entities exposed to Assist. Turn the option off under **Settings → Devices & services → ChatGPT OAuth → Reconfigure** for conversation-only behavior.

Only entities explicitly exposed to Assist are made available through Home Assistant's LLM tools. The model can still make mistakes; use normal Home Assistant permissions and avoid exposing safety-critical actions.

## Generate text or data

The AI Task entity supports Home Assistant's native `ai_task.generate_data` action. Select the entity created by this integration in the automation editor; the exact entity ID depends on the entry name and any existing entity-registry record.

```yaml
- action: ai_task.generate_data
  data:
    task_name: friendly_notification
    entity_id: ai_task.chatgpt_oauth_ai_task
    instructions: >-
      Write one concise, friendly sentence explaining that the garage door
      has been open for ten minutes.
  response_variable: generated

- action: persistent_notification.create
  data:
    title: Garage reminder
    message: "{{ generated.data }}"
```

### Structured output

Provide a Home Assistant `structure` to receive validated fields instead of free text:

```yaml
- action: ai_task.generate_data
  data:
    task_name: leak_alert
    entity_id: ai_task.chatgpt_oauth_ai_task
    instructions: >-
      The basement leak sensor is wet and the basement is 61°F.
      Produce a clear alert and select an appropriate severity.
    structure:
      title:
        description: Short notification title
        required: true
        selector:
          text:
      message:
        description: One or two clear sentences
        required: true
        selector:
          text:
      severity:
        description: Alert severity
        required: true
        selector:
          select:
            options:
              - critical
              - high
              - medium
              - low
  response_variable: alert

- action: notify.notify
  data:
    title: "{{ alert.data.title }}"
    message: "{{ alert.data.message }}"
```

The integration first requests native strict JSON-schema output. If the hosted endpoint rejects that feature, it retries with JSON-only instructions and validates the result against the original Home Assistant schema.

### Image and PDF attachments

`ai_task.generate_data` accepts images and PDFs resolved by Home Assistant:

```yaml
- action: ai_task.generate_data
  data:
    task_name: front_door_summary
    entity_id: ai_task.chatgpt_oauth_ai_task
    instructions: >-
      Describe only what is clearly visible in this front-door image.
      Do not infer identity or intent.
    attachments:
      - media_content_id: media-source://camera/camera.front_door
        media_content_type: image/jpeg
  response_variable: analysis
```

Each attachment and the combined unencoded attachment set are limited to 50 MB. Data generation accepts PNG, JPEG, WebP, GIF, and PDF files. File signatures are checked before content is transmitted.

## Generate or edit images

Use Home Assistant's native `ai_task.generate_image` action:

```yaml
- action: ai_task.generate_image
  data:
    task_name: tavern_poster
    entity_id: ai_task.chatgpt_oauth_ai_task
    instructions: >-
      Create a square vintage travel-poster illustration of a cozy Italian
      tavern at night, warm window light, rich print texture, and no text.
  response_variable: generated_image
```

Home Assistant stores the returned image in its AI Task media source. Common response values include:

```jinja2
{{ generated_image.url }}
{{ generated_image.media_source_id }}
{{ generated_image.mime_type }}
{{ generated_image.width }}
{{ generated_image.height }}
{{ generated_image.model }}
{{ generated_image.revised_prompt }}
```

### Reference images and edits

Attach between one and ten images to edit an image or guide a new composition:

```yaml
- action: ai_task.generate_image
  data:
    task_name: restyle_room
    entity_id: ai_task.chatgpt_oauth_ai_task
    instructions: >-
      Restyle the attached room as a refined art-deco lounge while preserving
      the camera angle, windows, major furniture placement, and room geometry.
    attachments:
      - media_content_id: media-source://image_upload/living_room.jpg
        media_content_type: image/jpeg
      - media_content_id: media-source://image_upload/material_reference.png
        media_content_type: image/png
  response_variable: restyled_room
```

Image generation accepts PNG, JPEG, WebP, and GIF attachments, with a maximum of 10 images and a combined unencoded size limit of 50 MB. File signatures must match the supplied MIME types.

Web search is intentionally not added to `ai_task.generate_image`; image prompts and reference images continue to use only the image-generation path.

## Additional integration actions

The actions below use the backward-compatible domain `openai_oauth_conversation`.

### `openai_oauth_conversation.generate_content`

```yaml
- action: openai_oauth_conversation.generate_content
  data:
    config_entry: 0123456789abcdef0123456789abcdef
    prompt: Summarize today's household reminders in one paragraph.
    model: gpt-5.6-terra
    reasoning_effort: medium
    web_search_mode: configured
    web_search_include_sources: false
  response_variable: generated
```

Search may be overridden per call with `configured`, `disabled`, `auto`, or `required`. Source display may also be overridden with `web_search_include_sources`. The response includes `text`, `raw_text`, `cited_text`, `citations`, `sources`, and `searches`.

### `openai_oauth_conversation.analyze_image`

This action accepts up to ten images from any mixture of:

- `image_file`: files inside Home Assistant's allowed paths.
- `image_url`: HTTP or HTTPS URLs returning an image content type.
- `entity_id`: `camera` or `image` entities.

```yaml
- action: openai_oauth_conversation.analyze_image
  data:
    config_entry: 0123456789abcdef0123456789abcdef
    prompt: >-
      Identify the visible plant and use web search to summarize its current
      care recommendations.
    entity_id:
      - camera.plant_camera
    web_search_mode: required
    web_search_context_size: medium
    web_search_include_sources: false
  response_variable: analysis
```

The response includes `text`, `response_text`, `raw_text`, `cited_text`, `citations`, `sources`, and `searches`.

## Reconfiguration and reauthentication

Open **Settings → Devices & services → ChatGPT OAuth** and use:

- **Reconfigure** to change the entry name, model, Home Assistant control access, system prompt, thinking level, source-display behavior, or other web-search defaults.
- **Reauthenticate** when Home Assistant reports that the OAuth session has expired or been revoked.
- **Download diagnostics** when filing a bug report. Diagnostics exclude tokens, account identifiers, prompts, attachments, conversation text, search queries, source contents, and generated output.

## Privacy and security

Prompts, enabled Home Assistant tool context, images, PDFs, and web-search queries used in a request are transmitted to the hosted ChatGPT service. When live web access is enabled, the search service may retrieve external pages. Review the service's terms and privacy controls before sending sensitive content.

- Web content is untrusted and may contain prompt-injection attempts. Treat searched instructions as advisory and verify important results.
- The optional Home Assistant location hint includes only country and time zone; it does not include latitude, longitude, home name, or street address.
- OAuth access tokens and refresh tokens are stored in Home Assistant's config-entry storage.
- Do not expose `.storage`, callback URLs, debug logs containing credentials, or unredacted request captures.
- Only expose the Home Assistant entities that the Assist agent genuinely needs.
- Local file access is restricted to Home Assistant's allowed paths.
- Remote image downloads are limited to HTTP/HTTPS, bounded redirects, an image content type, and a 20 MB response limit.
- Generated images and temporary signed media URLs are managed by Home Assistant.

## Limitations

- This integration depends on an unofficial hosted backend rather than a documented public OpenAI API contract.
- Backend request formats, model availability, search availability, usage limits, and OAuth behavior can change independently of this repository.
- A ChatGPT subscription does not guarantee unlimited usage or access to every listed model or search mode.
- Search citations and source coverage are produced by the hosted model and search service; they do not guarantee that every claim is correct or exhaustively sourced.
- Cache/index-only behavior depends on backend support. Compatibility fallback to the legacy preview tool occurs only when live access is allowed and no domain allowlist is present; the integration never silently removes an explicit cache-only or domain-filter restriction.
- Image generation may take several minutes and can time out under heavy service load.
- `Ultra` does not provide the Codex CLI's client-side subagent orchestration.
- The integration does not provide code interpreter, speech-to-text, or text-to-speech services.

## Troubleshooting

### The integration does not appear after installation

Confirm this file exists:

```text
/config/custom_components/openai_oauth_conversation/manifest.json
```

Then perform a full Home Assistant restart and clear the browser cache.

### The AI Task entity is not listed

Open **Settings → Devices & services → Entities**, filter by **ChatGPT OAuth**, and enable **Show disabled entities**. The entity supports both `ai_task.generate_data` and `ai_task.generate_image`.

### Authentication failed

Start **Reauthenticate** from the integration entry. Use the newly generated sign-in link and paste the full callback URL from the same attempt.

### A model or thinking level is rejected

Use **Reconfigure** and select a combination shown by the integration. The hosted service can also restrict a model for a particular account or temporarily remove access.

### Web search is not used

- Confirm the integration's mode is **Automatic** or **Required**.
- Use **Required** or the dedicated `openai_oauth_conversation.web_search` action when a search must occur.
- Confirm the signed-in account or workspace permits search.
- Remove an overly restrictive domain allowlist.
- Try live access when the request depends on very recent information.

Required mode raises an error instead of returning an answer when the backend provides no search call or citation evidence.

### Sources are spoken by the voice assistant

Open **Settings → Devices & services → ChatGPT OAuth → Reconfigure** and disable **Include sources in response text**. Assist will speak only the natural answer. Interfaces that support response cards can still display the fully cited answer, and integration actions continue returning `cited_text`, `citations`, `sources`, and `searches`.

### Search controls are rejected

The integration automatically retries without individually rejected optional controls and can fall back from `web_search` to `web_search_preview` only when doing so preserves the requested privacy constraints. It refuses the fallback rather than silently removing cache-only access or a domain allowlist.

### Image attachments are rejected

Confirm that:

- No more than 10 images are attached.
- Every image is PNG, JPEG, WebP, or GIF and its file signature matches its MIME type.
- No individual file exceeds 50 MB.
- Combined unencoded attachments do not exceed 50 MB.

### Reporting a problem

Download diagnostics from the integration entry and attach them to a GitHub issue. Never attach `.storage` files, callback URLs, access tokens, refresh tokens, complete request bodies, or unreviewed debug logs.

## Upgrading

- Upgrading from 1.2.0 to 1.2.1 changes only repository ownership metadata and public release packaging; Home Assistant configuration and runtime behavior are unchanged.
- Upgrading from 1.1.1 to 1.2.0 adds configurable source presentation. Existing entries default to voice-friendly text without appended sources; re-enable **Include sources in response text** to preserve the v1.1 behavior.
- Upgrading from 1.1.0 to 1.1.1 changes only HACS packaging and release automation; Home Assistant configuration and runtime behavior are unchanged.
- Upgrading from 1.0.0 to 1.1.x preserves existing entries and leaves web search disabled until explicitly enabled.
- Upgrading from 0.5.x preserves the stable domain, config-entry data, service namespace, conversation unique ID, and AI Task unique ID.

See [MIGRATION.md](MIGRATION.md) for details.

## Removal

1. Remove the integration entry from **Settings → Devices & services**.
2. Remove the integration from HACS, or delete `/config/custom_components/openai_oauth_conversation` for a manual installation.
3. Restart Home Assistant.

Removing the Home Assistant entry does not revoke the ChatGPT session outside Home Assistant. Use the account's own security controls when session revocation is required.

## Support and contributing

- Bug reports and feature requests: [GitHub Issues](https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/issues)
- Security reports: [SECURITY.md](SECURITY.md)
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Release history: [CHANGELOG.md](CHANGELOG.md)

## License

Released under the [MIT License](LICENSE).

This project includes original community code and is inspired by Home Assistant's conversation and AI Task architecture. Product and project names are used only to describe interoperability; all trademarks belong to their respective owners.
