# Migrating ChatGPT OAuth

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
