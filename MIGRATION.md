# Migrating to ChatGPT OAuth 1.0.0

Version 1.0.0 introduces the public name **ChatGPT OAuth for Home Assistant** while preserving the integration's original internal domain for compatibility.

## What remains unchanged

- Internal domain: `openai_oauth_conversation`
- Existing Home Assistant config entries
- Stored OAuth credentials
- Conversation entity unique ID
- AI Task entity unique ID
- Existing entity IDs already stored in the entity registry
- `openai_oauth_conversation.generate_content`
- `openai_oauth_conversation.analyze_image`
- Automations using `ai_task.generate_data` or `ai_task.generate_image`

No reauthentication should normally be required.

## What changes

- Public project name: **ChatGPT OAuth for Home Assistant**
- Integration display name: **ChatGPT OAuth**
- Proposed repository location: `hebs/homeassistant-chatgpt-oauth`
- New AI Task entities use a more accurate `ChatGPT OAuth AI Task` style name.
- The default model for newly created entries is GPT-5.6 Terra.
- Documentation, diagnostics, errors, and configuration screens have been redesigned for a public release.
- Reconfiguration now includes **Enable Home Assistant control**. Existing entries default to enabled so Assist behavior is preserved.

User-customized entity names are not overwritten. Existing entity IDs remain attached to their stable unique IDs even when the default display name changes.

## HACS upgrade

When the GitHub repository is renamed, GitHub normally redirects the old repository URL. HACS should follow that redirect. After upgrading:

1. Restart Home Assistant.
2. Open **Settings → Devices & services → ChatGPT OAuth**.
3. Confirm the entry loads and the existing AI Task entity is available.
4. Use **Reconfigure** to review the model, thinking level, and Home Assistant control setting.

If HACS does not follow the repository redirect, remove only the HACS repository reference and add `https://github.com/hebs/homeassistant-chatgpt-oauth` as a custom integration repository. Do not delete the Home Assistant integration entry.

## Manual upgrade

1. Back up Home Assistant.
2. Stop Home Assistant or use the File editor/SSH tools carefully.
3. Replace the contents of:

   ```text
   /config/custom_components/openai_oauth_conversation
   ```

   with the same directory from the v1.0.0 release.

4. Start or fully restart Home Assistant.

Do not rename the `openai_oauth_conversation` directory. The folder name must continue to match the stable integration domain.

## After upgrading

The AI Task entity should report support for data, attachments, and image generation. Existing installations may retain an older entity ID containing `image_generation`; that is expected and preserves automation compatibility.

Download integration diagnostics before reporting a migration problem. Diagnostics do not include OAuth credentials, account identifiers, prompts, attachments, or generated content.
