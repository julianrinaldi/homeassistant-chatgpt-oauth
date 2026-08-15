# Migrating ChatGPT OAuth

## From 1.5.0 to 1.6.0

Version 1.6.0 lets the Assist conversation agent delegate generation and analysis to this integration's AI Task entity, inspect explicitly exposed camera snapshots, and create or edit images.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Assistant profiles, models, prompts, thinking levels, memory, web-search, context, and tool-safety settings
- Existing Home Assistant control and history-tool settings
- Existing actions and automations

No reauthentication is required. Entries migrate automatically to config-entry version 12.

### New privacy setting

Existing and new assistant profiles receive:

```text
Let Assist analyze cameras and create images: Disabled
```

Open **Settings → Devices & services → ChatGPT OAuth → Reconfigure** to enable it for the desired assistant profile. Then expose only the required camera or image entities to Assist. Camera analysis is limited to a fresh still captured on demand and honors the initiating Home Assistant user's entity permissions. Generated image bytes and camera contents are excluded from diagnostics and conversation-completed events.

## From 1.4.0 to 1.5.0

Version 1.5.0 adds optional user, voice-satellite, room, and room-entity context; configurable Home Assistant tool limits; loop detection; and privacy-safe conversation completion events.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Assistant profiles, models, prompts, thinking levels, memory, and web-search settings
- Home Assistant control and history-tool settings
- Existing actions and automations

No reauthentication is required. Entries migrate automatically to config-entry version 11.

### New defaults

Existing and new assistant profiles use these defaults:

```text
Current user's display name: Disabled
Voice satellite and current room: Disabled
Exposed entities in the current room: Disabled
Maximum Home Assistant tool calls: 5
Maximum total tool time: 60 seconds
```

Open **Settings → Devices & services → ChatGPT OAuth → Reconfigure** to enable only the context appropriate for each assistant. Precise web-search location remains a separate setting and is not enabled by this migration.

## From 1.2.0 to 1.2.1

Version 1.2.1 is a repository and release-packaging cleanup. It does not change integration runtime behavior or stored Home Assistant data.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Selected model, thinking level, and web-search settings
- Home Assistant control and source-presentation settings
- Existing actions and automations

No reauthentication or reconfiguration is required. Use the normal HACS update action or replace the manual-install directory and restart Home Assistant.

## From 1.1.1 to 1.2.0

Version 1.2.0 adds voice-friendly control over how OpenAI web-search sources are presented.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Selected model and thinking level
- Web-search mode, context size, live-access setting, and location setting
- Home Assistant control setting
- Existing actions and automations

No reauthentication is required. Entries migrate automatically to config-entry version 8.

### New source-display setting

Existing entries receive:

```text
Include sources in response text: Disabled
```

With the setting disabled:

- Assist speaks only the natural answer.
- Home Assistant interfaces that support cards can display a separate cited answer.
- Plain-text AI Tasks return clean text suitable for TTS.
- Integration actions retain `cited_text`, `citations`, `sources`, and `searches` response fields.

To preserve the v1.1 behavior, open:

```text
Settings → Devices & services → ChatGPT OAuth → Reconfigure
```

Then enable **Include sources in response text**.

The custom integration actions also accept a per-call override:

```yaml
web_search_include_sources: true
```

## From 1.1.0 to 1.1.1

Version 1.1.1 corrects HACS repository and release-asset packaging. It does not change integration runtime behavior or stored Home Assistant data.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Selected model and thinking level
- Web-search settings
- Home Assistant control setting
- All existing actions and automations

No reauthentication or reconfiguration is required.

### HACS upgrade

Use the normal HACS update action. HACS downloads the release asset named `chatgpt_oauth.zip`, whose files are packaged directly at the archive root for extraction into:

```text
/config/custom_components/openai_oauth_conversation
```

### Manual upgrade

Download `chatgpt-oauth-manual.zip`, extract it into `/config`, and restart Home Assistant.

## From 1.0.0 to 1.1.0

Version 1.1.0 adds OpenAI web search without changing the integration's stable Home Assistant identity.

### Preserved automatically

- Internal domain: `openai_oauth_conversation`
- Existing Home Assistant config entries
- Stored OAuth credentials
- Conversation entity unique ID
- AI Task entity unique ID
- Existing entity IDs in the entity registry
- `openai_oauth_conversation.generate_content`
- `openai_oauth_conversation.analyze_image`
- Automations using `ai_task.generate_data` or `ai_task.generate_image`
- Selected model, thinking level, prompt, and Home Assistant control setting

No reauthentication should normally be required.

### New settings

Existing entries migrate to config-entry version 7 with:

```text
Web search: Disabled
Search context size: Medium
Live internet access: Enabled
Use Home Assistant location: Disabled
```

Because the search mode is disabled, the live-access value has no effect until search is enabled. This preserves the 1.0.0 behavior and prevents an upgrade from silently sending new web-search queries.

After restarting, open:

```text
Settings → Devices & services → ChatGPT OAuth → Reconfigure
```

Choose **Automatic** when the model may decide whether current information is needed, or **Required** when every applicable request must contain search evidence.

### New action

Version 1.1.0 adds:

```text
openai_oauth_conversation.web_search
```

It forces OpenAI web search and returns sourced text, raw text, citations, unique sources, and reported search actions. Existing actions also gain optional per-call search overrides and source metadata without changing their existing response fields.

### Manual upgrade

1. Back up Home Assistant.
2. Replace the contents of:

   ```text
   /config/custom_components/openai_oauth_conversation
   ```

   with the same directory from the v1.1.0 release.

3. Perform a full Home Assistant restart.
4. Verify the integration entry loads.
5. Use **Reconfigure** to review the new search settings.

Do not rename the `openai_oauth_conversation` directory. The folder name must continue to match the stable integration domain.

## From 0.5.x to 1.x

The public project name is **ChatGPT OAuth for Home Assistant**, but the integration continues to use the original internal domain for backward compatibility.

The following remain unchanged:

- Existing config entries and OAuth credentials
- Conversation entity unique ID
- AI Task entity unique ID
- Existing entity IDs stored in the entity registry
- Existing `generate_content` and `analyze_image` action names
- Automations using Home Assistant AI Tasks

New AI Task entities use a more accurate `ChatGPT OAuth AI Task` display name. Existing installations may retain an older entity ID containing `image_generation`; that is expected and preserves automation compatibility.

Download integration diagnostics before reporting a migration problem. Diagnostics do not include OAuth credentials, account identifiers, prompts, attachments, search queries, source contents, or generated content.
