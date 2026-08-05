<p align="center">
  <img src="assets/logo.png" alt="ChatGPT OAuth for Home Assistant" width="760">
</p>

<p align="center">
  <a href="https://github.com/hebs/homeassistant-chatgpt-oauth/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/hebs/homeassistant-chatgpt-oauth?display_name=tag&sort=semver"></a>
  <a href="https://github.com/hebs/homeassistant-chatgpt-oauth/actions/workflows/hacs.yml"><img alt="HACS validation" src="https://github.com/hebs/homeassistant-chatgpt-oauth/actions/workflows/hacs.yml/badge.svg"></a>
  <a href="https://github.com/hebs/homeassistant-chatgpt-oauth/actions/workflows/hassfest.yml"><img alt="Hassfest" src="https://github.com/hebs/homeassistant-chatgpt-oauth/actions/workflows/hassfest.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Home Assistant 2026.4.0 or newer" src="https://img.shields.io/badge/Home%20Assistant-2026.4.0%2B-41BDF5">
</p>

# ChatGPT OAuth for Home Assistant

Use a ChatGPT account in Home Assistant for **Assist**, structured AI Tasks, image and PDF analysis, image generation, and image editing—without configuring an OpenAI API key.

> [!IMPORTANT]
> This is an **unofficial community integration**. It is not affiliated with, endorsed by, or supported by OpenAI or the Home Assistant project. It uses a hosted ChatGPT/Codex OAuth backend that may change without notice. Do not use it for safety-critical or life-critical automation.

## Features

- Home Assistant Assist conversation agent with optional Home Assistant tool control.
- Native `ai_task.generate_data` support for text and schema-validated structured output.
- Native `ai_task.generate_image` support for new images, edits, and reference-image workflows.
- Up to **10 image attachments** in a single image-generation request.
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

No OpenAI API key is required. Availability, limits, and model access are determined by the signed-in ChatGPT account.

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
3. Add `https://github.com/hebs/homeassistant-chatgpt-oauth` as an **Integration** repository.
4. Search for **ChatGPT OAuth** and select **Download**.
5. Restart Home Assistant.

### Manual installation

1. Download the source archive for the desired release.
2. Copy this directory:

   ```text
   custom_components/openai_oauth_conversation
   ```

   into:

   ```text
   /config/custom_components/openai_oauth_conversation
   ```

3. Restart Home Assistant.

The internal integration domain remains `openai_oauth_conversation` for backward compatibility.

## Setup and authentication

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **ChatGPT OAuth**.
4. Enter a friendly name and select a model.
5. Choose whether the Assist agent may inspect and control entities exposed to Assist. This is enabled by default for backward compatibility and can be disabled for conversation-only use.
6. Optionally customize the system prompt.
7. Choose a thinking level supported by that model.
8. Open the displayed ChatGPT sign-in link.
9. Complete sign-in in the browser.
10. The browser will finish at a localhost callback page. It may display a connection error; that is expected because the callback is intended for the local Codex client.
11. Copy the **entire callback URL** from the address bar and paste it into Home Assistant.

The callback URL contains a short-lived authorization code. Treat it as sensitive and do not post it in issues or logs.

## Supported models and thinking levels

| Model | Available thinking levels | Default |
|---|---|---|
| GPT-5.6 Sol (`gpt-5.6-sol`) | Low, Medium, High, Extra high, Max, Ultra | Low |
| GPT-5.6 Terra (`gpt-5.6-terra`) | Low, Medium, High, Extra high, Max, Ultra | Medium |
| GPT-5.6 Luna (`gpt-5.6-luna`) | Low, Medium, High, Extra high, Max | Medium |
| GPT-5.5 (`gpt-5.5`) | Low, Medium, High, Extra high | Medium |

The setup and reconfiguration screens only show levels compatible with the selected model. `Ultra` uses the model's `Max` reasoning level; Codex's separate subagent-delegation runtime is not available inside Home Assistant.

Model availability is controlled by the hosted service and the signed-in account. A model can be temporarily unavailable even when it appears in the integration.

## Home Assistant Assist

After setup, choose the new conversation agent in an Assist pipeline:

1. Open **Settings → Voice assistants**.
2. Create or edit a pipeline.
3. Select the ChatGPT OAuth conversation agent under **Conversation agent**.

When **Enable Home Assistant control** is turned on in the integration settings, the agent receives Home Assistant's Assist tool API and may inspect or control entities exposed to Assist. Turn the option off under **Settings → Devices & services → ChatGPT OAuth → Reconfigure** for conversation-only behavior.

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

## Integration actions

The integration also provides two actions under the backward-compatible domain `openai_oauth_conversation`.

### `openai_oauth_conversation.generate_content`

```yaml
- action: openai_oauth_conversation.generate_content
  data:
    config_entry: 0123456789abcdef0123456789abcdef
    prompt: Summarize today's household reminders in one paragraph.
    model: gpt-5.6-terra
    reasoning_effort: medium
  response_variable: generated
```

The generated text is available as `{{ generated.text }}`.

### `openai_oauth_conversation.analyze_image`

This action accepts up to ten images from any mixture of:

- `image_file`: files inside Home Assistant's allowed paths.
- `image_url`: HTTP or HTTPS URLs returning an image content type.
- `entity_id`: `camera` or `image` entities.

```yaml
- action: openai_oauth_conversation.analyze_image
  data:
    config_entry: 0123456789abcdef0123456789abcdef
    prompt: Describe the visible weather conditions in one sentence.
    entity_id:
      - camera.backyard
  response_variable: analysis
```

The generated text is available as `{{ analysis.text }}` and `{{ analysis.response_text }}`.

## Reconfiguration and reauthentication

Open **Settings → Devices & services → ChatGPT OAuth** and use:

- **Reconfigure** to change the entry name, model, Home Assistant control access, system prompt, or thinking level.
- **Reauthenticate** when Home Assistant reports that the OAuth session has expired or been revoked.
- **Download diagnostics** when filing a bug report. Diagnostics exclude tokens, account identifiers, prompts, attachments, conversation text, and generated output.

## Privacy and security

Prompts, enabled Home Assistant tool context, images, and PDFs used in a request are transmitted to the hosted ChatGPT service. Review the service's terms and privacy controls before sending sensitive content.

- OAuth access tokens and refresh tokens are stored in Home Assistant's config-entry storage.
- Do not expose `.storage`, diagnostics from unknown integrations, callback URLs, or debug logs containing credentials.
- Only expose the Home Assistant entities that the Assist agent genuinely needs.
- Local file access is restricted to Home Assistant's allowed paths.
- Remote image downloads are limited to HTTP/HTTPS, bounded redirects, an image content type, and a 20 MB response limit.
- Generated images and temporary signed media URLs are managed by Home Assistant.

## Limitations

- This integration depends on an unofficial hosted backend rather than a documented public OpenAI API contract.
- Backend request formats, model availability, usage limits, and OAuth behavior can change independently of this repository.
- A ChatGPT subscription does not guarantee unlimited usage or access to every listed model.
- Image generation may take several minutes and can time out under heavy service load.
- `Ultra` does not provide the Codex CLI's client-side subagent orchestration.
- The integration does not provide web search, code interpreter, speech-to-text, or text-to-speech services.

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

### Image attachments are rejected

Confirm that:

- No more than 10 images are attached.
- Every image is PNG, JPEG, WebP, or GIF and its file signature matches its MIME type.
- No individual file exceeds 50 MB.
- Combined unencoded attachments do not exceed 50 MB.

### Reporting a problem

Download diagnostics from the integration entry and attach them to a GitHub issue. Never attach `.storage` files, callback URLs, access tokens, refresh tokens, or complete debug logs without reviewing and redacting them first.

## Upgrading from 0.5.x

See [MIGRATION.md](MIGRATION.md). Version 1.0.0 keeps the internal domain, config-entry data, service namespace, conversation unique ID, and AI Task unique ID so existing installations and automations continue to work. Public names and documentation change to **ChatGPT OAuth**.

## Removal

1. Remove the integration entry from **Settings → Devices & services**.
2. Remove the integration from HACS, or delete `/config/custom_components/openai_oauth_conversation` for a manual installation.
3. Restart Home Assistant.

Removing the Home Assistant entry does not revoke the ChatGPT session outside Home Assistant. Use the account's own security controls when session revocation is required.

## Support and contributing

- Bug reports and feature requests: [GitHub Issues](https://github.com/hebs/homeassistant-chatgpt-oauth/issues)
- Security reports: [SECURITY.md](SECURITY.md)
- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Release history: [CHANGELOG.md](CHANGELOG.md)
- Release validation: [VALIDATION_REPORT.md](VALIDATION_REPORT.md)

## License

Released under the [MIT License](LICENSE).

This project includes original community code and is inspired by Home Assistant's conversation and AI Task architecture. Product and project names are used only to describe interoperability; all trademarks belong to their respective owners.
