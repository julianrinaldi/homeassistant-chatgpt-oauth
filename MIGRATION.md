# Migrating ChatGPT OAuth

## From 1.7.x to 1.8.0

Version 1.8.0 adds opt-in persistent reminders and delayed device on/off actions, plus explicitly selected local TOML skill packs. Existing Home Assistant access and privacy choices are preserved; neither new capability is enabled automatically.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Assistant profiles, models, prompts, selected scripts, restricted-prompt entities, thinking levels, memory, context, web-search, AI media, history, and tool-safety settings
- Existing integration actions and automations

No reauthentication is required. Entries migrate automatically to config-entry version 14.

### New privacy defaults

Existing and new assistant profiles receive:

```text
Allow reminders and scheduled actions: Disabled
Local skill packs: None selected
```

The migration does not schedule an item, read a local skill file into a prompt, enable web search, expose another entity, or grant a new device permission. Open **Settings → Devices & services → ChatGPT OAuth → Reconfigure** for the specific assistant profile when you are ready to enable either feature.

### Persistent scheduled actions

After **Allow reminders and scheduled actions** is enabled, the assistant can create reminders. Delayed device on/off tools also require the profile's existing **Enable Home Assistant control** setting. Items are stored in Home Assistant's private persistent storage, restored after a restart, displayed by the native **Scheduled actions** calendar, and cancellable through Assist or calendar deletion. In the common single-entry case the entity ID is `calendar.scheduled_actions`; Home Assistant may add a suffix when required to keep an entity ID unique.

Existing scripts and automations are not converted into scheduled items. The scheduler does not accept arbitrary future service calls, script runs, automations, alarm changes, toggles, camera actions, or updates. Every device target is resolved, scope-checked, and permission-checked when created. Target existence, Assist exposure, the creating user's permission, the assistant's current control settings, the current local-skill scope, and the fixed operation's service availability are checked again at execution time. Narrowing, invalidating, or removing a scope prevents an affected stored device action from running; the calendar remains available for local cancellation.

Sensitive targets—locks, valves, buttons, input buttons, sirens, and door, garage, gate, or window covers—are not scheduled immediately. To approve one, the same Home Assistant user must send `Confirm scheduled action <12-character reference>` as the entire later message to the same assistant profile and same nonempty Home Assistant conversation. Matching is case-insensitive and allows only surrounding whitespace plus one optional terminal `.`, `!`, or `?`; the later turn must have a new Home Assistant Context and arrive within five minutes and before the run time. The confirmation tool is not exposed unless that raw user message matches, so a model tool call alone cannot authorize the action.

Reminders create a Home Assistant persistent notification when due. The private on-disk record necessarily retains the fixed operation or reminder content. Persisted records are revalidated against the scheduler's schema and fixed-operation allowlist before restart recovery; tampered or invalid records are discarded rather than executed. Diagnostics and the `chatgpt_oauth.scheduled_action_finished` event's data payload do not contain Home Assistant entity IDs, user IDs, reminder bodies, stored tool arguments, complete prompts, or assistant responses. Home Assistant's standard local event Context retains the creator's user ID and creation request's parent Context ID for local auditing; those fields are not part of the event data and are not sent to ChatGPT by the event. The calendar does show titles, target display names, statuses, references, and creator display names to users who can read that calendar entity; users allowed to delete its events can remove non-executing records.

### Local skill packs

Version 1.8.0 does not download, generate, or enable any skill pack. To add one, create a reviewed TOML file directly under:

```text
/config/openai_oauth_conversation/skills
```

Then reopen the assistant profile's **Reconfigure** form and explicitly select the file under **Local skill packs**. A file that is not selected has no effect and is not sent to ChatGPT. Selected valid files are reloaded on every conversation request, so later edits apply without a Home Assistant restart.

Only strict schema-version-1 TOML instruction packs are supported. The loader does not follow symlinks or nested directories, and the schema cannot define includes, secret or environment-variable expansion, downloads, remote imports, arbitrary tools or services, or Python or shell execution. The integration never executes a skill file or its instruction text; code-looking text in `instructions` is literal prompt content rather than an executable definition. Never put a password, token, address, or other secret in a pack because selected instructions are transmitted to ChatGPT.

If any explicitly selected pack is missing, invalid, or skipped because the aggregate pack budget is exceeded, it stops applying and the request enters safe mode. All Home Assistant tools and web search remain withheld until every selected pack is available, valid, and within the active limits, rather than silently falling back to the profile's broader permissions. Reconfigure the profile to fix or remove the affected selection; aggregate-budget skips are reported as ID-free counts in diagnostics.

If a selected pack declares `allowed_entities` or `allowed_areas`, version 1.8.0 enters hard scoped mode for that request. Generic Assist, history, AI Task, and media APIs are removed because Home Assistant does not provide a public per-request entity filter for those APIs. With `confirmation = "inherit"`, selected scripts whose script entity resolves inside the combined accessible scope remain eligible alongside the separately permission-checked scheduler. A `sensitive` or `always` confirmation policy also withholds all selected-script tools. A scope that resolves to no accessible entities exposes no general Home Assistant tools.

Home Assistant has no generic trusted confirmation API. For `confirmation = "sensitive"` or `confirmation = "always"`, ChatGPT OAuth withholds generic Assist control and all selected-script tools instead of relying on model wording. History and media tools may remain when no hard entity or area scope is active because they do not provide that immediate Home Assistant mutation path. Confirmation wording is guidance only for those other remaining tools. The scheduler uses a separate enforced state transition for sensitive targets, and `always` extends it to every scheduled device action.

### Release publishing

Release archives and checksums continue to be built and validated automatically, but the build workflow now has read-only repository permission and cannot create or alter GitHub releases. After a successful build, releases are published through the repository owner's authenticated `julianrinaldi` account so the GitHub release shows the human maintainer as its publisher.

## From 1.7.0 to 1.7.1

Version 1.7.1 corrects the clean-runner release test setup for dynamically loaded Home Assistant component packages. Integration behavior, selected-script access, restricted prompt templates, OAuth credentials, entities, and stored configuration are unchanged. No reauthentication, migration action, or reconfiguration is required.

## From 1.6.x to 1.7.0

Version 1.7.0 adds selected Home Assistant scripts as strongly typed Assist tools and restricted Jinja system prompts with explicitly selected entity-state access.

### Preserved automatically

- Existing config entries and OAuth credentials
- Conversation and AI Task entity identities
- Assistant profiles, prompts, models, thinking levels, memory, web-search, context, camera, and tool-safety settings
- Existing actions and automations

No reauthentication is required. Entries migrate automatically to config-entry version 13.

### New defaults

Existing profiles receive no selected scripts and no prompt-readable entities. This means the upgrade does not grant new device, script, or entity access automatically.

Open **Settings → Devices & services → ChatGPT OAuth → Reconfigure** to choose:

```text
Scripts this assistant may run
Entities the system prompt may read
```

Configured prompt text is preserved. Restricted Jinja variables are rendered per request, while state lookup functions return values only for explicitly selected entities that the initiating Home Assistant user may read.

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
