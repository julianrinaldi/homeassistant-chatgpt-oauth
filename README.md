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
- Opt-in Assist tools that delegate text and image work to the integration's AI Task entity, analyze exposed camera snapshots, and create or edit images.
- Opt-in persistent reminders and delayed device on/off actions that survive restarts, appear on a Home Assistant calendar, and can be cancelled.
- Explicitly selected, user-managed local TOML skill packs for reusable instructions, response formats, tool guidance, web-search policy, and tightly scoped household roles.
- Per-profile selected Home Assistant scripts exposed as named, strongly typed tools with independently validated fields.
- Restricted Jinja system prompts with privacy-gated user and room variables plus explicitly selected entity-state access.
- Opt-in current-user, voice-satellite, device, room, and exposed room-entity context.
- Configurable tool-call and tool-time limits with repeated-call and no-progress detection.
- Privacy-safe `chatgpt_oauth.conversation_finished` events for automations and diagnostics.
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

Release archives and checksums are built and validated by a read-only GitHub Actions workflow. After that build passes, the resulting artifacts are downloaded and the GitHub release is published through the repository owner's authenticated `julianrinaldi` account. The workflow itself cannot create or modify a release, so new releases show the human maintainer rather than `github-actions[bot]` as their publisher.

The internal integration domain remains `openai_oauth_conversation` for backward compatibility.

## Setup and authentication

1. Go to **Settings → Devices & services**.
2. Select **Add integration**.
3. Search for **ChatGPT OAuth**.
4. Enter a friendly name and select a model.
5. Choose whether the Assist agent may inspect and control entities exposed to Assist.
6. Choose whether Assist may use this integration's AI Task entity and cameras or image entities exposed to Assist.
7. Optionally allow restart-safe reminders and delayed device on/off actions.
8. Optionally select the exact Home Assistant scripts this assistant may run as named tools.
9. Optionally select user-managed TOML packs already present under `/config/openai_oauth_conversation/skills`.
10. Optionally enable the current user's display name, satellite and room labels, or exposed entities in the current room.
11. Set the maximum Home Assistant tool calls and combined tool time for each message.
12. Choose the default OpenAI web-search mode, search context size, whether sources should appear in response text, live-access behavior, and whether approximate Home Assistant location may be used.
13. Optionally select entities that a restricted Jinja system prompt may read, then customize the prompt.
14. Choose a thinking level supported by the selected model.
15. Open the displayed ChatGPT sign-in link.
16. Complete sign-in in the browser.
17. The browser will finish at a localhost callback page. It may display a connection error; that is expected because the callback is intended for the local Codex client.
18. Copy the **entire callback URL** from the address bar and paste it into Home Assistant.

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
| **Share approximate location** | Sends Home Assistant's country and time zone as an approximate search hint. Coordinates and the configured home name are not sent. |
| **Share precise home location** | Also sends Home Assistant's exact latitude, longitude, and configured home name as trusted request context. Country and time zone are included automatically. This is disabled by default. |

OpenAI's structured web-search location field supports approximate city, region, country, and time zone values, but not coordinates. When precise sharing is enabled, this integration adds Home Assistant's coordinates and configured home name to the model instructions so it can localize search queries. Home Assistant does not store a separate street-address field; exact coordinates may nevertheless identify the home address.

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

`openai_oauth_conversation.web_search` always requires a search. It supports per-call model and thinking-level overrides, context size, live/cache behavior, approximate or precise Home Assistant location, and an optional allowlist of up to 100 domains.

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
    web_search_use_home_assistant_precise_location: true
    allowed_domains:
      - home-assistant.io
      - github.com
  response_variable: research
```

Common response values:

```jinja2
{{ research.text }}
{{ research.citations }}
{{ research.sources }}
{{ research.searches }}
{{ research.model }}
{{ research.reasoning_effort }}
{{ research.search_context_size }}
{{ research.include_sources_in_text }}
{{ research.live_access }}
```

`research.text` is the primary answer and follows the selected source-display setting. To keep Home Assistant action responses readable, `raw_text` appears only when the unformatted model answer differs from `text`, and `cited_text` appears only when citation annotations produce a distinct clickable answer. Each item in `research.citations` contains `url`, `title`, `start_index`, and `end_index`. Each item in `research.sources` contains one unique `url` and `title`. `research.searches` records search, page-open, or find-in-page actions without duplicating the top-level source list.

Allowed domains must be hostnames such as `home-assistant.io` or `developers.openai.com`; do not include a URL path, query, or fragment.

## Home Assistant Assist

After setup, choose the new conversation agent in an Assist pipeline:

1. Open **Settings → Voice assistants**.
2. Create or edit a pipeline.
3. Select the ChatGPT OAuth conversation agent under **Conversation agent**.

When **Enable Home Assistant control** is turned on, the agent receives Home Assistant's Assist tool API and may inspect or control entities exposed to Assist. Turn the option off under **Settings → Devices & services → ChatGPT OAuth → Reconfigure** for conversation-only behavior.

Only entities explicitly exposed to Assist are made available through Home Assistant's LLM tools. The model can still make mistakes; use normal Home Assistant permissions and avoid exposing safety-critical actions.

### Selected Home Assistant scripts

Use **Scripts this assistant may run** under an assistant profile's **Reconfigure** screen to choose up to 20 scripts. Each selected script becomes a separate model tool with a stable generated tool name, the script's friendly name and description, and parameters derived from its Home Assistant fields.

Script selectors provide the strongest schemas. Number limits, select options, booleans, dates, times, durations, entity selectors, and other Home Assistant selector types are preserved in the tool declaration and validated again before execution. A field without a selector uses a conservative scalar type inferred from its default or example; otherwise it accepts bounded text. Required fields are enforced by ChatGPT OAuth even though Home Assistant treats the script editor's required flag primarily as UI metadata.

The model cannot choose a different script, supply undeclared fields, or bypass the initiating user's script permission. The integration waits for the selected script to finish and returns its bounded, JSON-safe response to the conversation. If the script has no response, the tool still reports confirmed completion. Selected scripts remain available when general Home Assistant control is disabled because choosing each script is a separate, narrower permission grant.

For best results, give the script a clear alias and description and configure selectors for every input. Avoid selecting scripts that open doors, disarm alarms, change locks, or perform similarly sensitive actions without their own explicit safety checks.

### Local skill packs

Local skills are reusable, declarative instruction packs managed entirely by the Home Assistant owner. Put each pack in a direct-child TOML file at:

```text
/config/openai_oauth_conversation/skills/<skill_id>.toml
```

The filename, without `.toml`, is the stable skill ID. It may contain lowercase letters, numbers, underscores, and hyphens, must start with a letter or number, and may be at most 64 characters. Adding a file does nothing by itself: open the assistant profile's **Reconfigure** screen and explicitly choose it under **Local skill packs**. Only a selected pack's name, instructions, output format, and applicable policy guidance are added to ChatGPT requests. Edits to an already selected valid file take effect on the next conversation request without restarting Home Assistant.

This complete `kegerator_assistant.toml` example uses every supported field:

```toml
schema_version = 1
name = "Kegerator Assistant"
description = "Monitors the bar kegerator and guides routine maintenance."
instructions = """
Use measured values instead of guessing. Explain abnormal temperature or power
readings plainly. Use only the selected maintenance scripts and scheduled-action
tools that are actually available. Never bypass a script's own safety checks.
"""
suggested_tools = ["selected_scripts", "scheduled_actions"]
output_format = """
Lead with the current finding. Follow with at most two recommended actions and
state clearly when a value is unavailable.
"""
web_search = "disabled"
confirmation = "inherit"
voice_max_words = 80
allowed_entities = [
  "sensor.kegerator_temperature",
  "switch.kegerator",
  "script.kegerator_maintenance",
]
allowed_areas = ["Bar"]
```

Supported settings are:

| Setting | Meaning |
|---|---|
| `schema_version` | Required and currently `1`. |
| `name` | Required human-readable pack name. |
| `instructions` | Required instructions added literally to the selected assistant's prompt. Jinja-looking text is not rendered. |
| `description` | Optional local human-readable explanation retained as validated pack metadata; it is not added to the model instructions. |
| `suggested_tools` | Optional preferences for already available tool categories: `home_assistant`, `history`, `camera_analysis`, `image_generation`, `ai_task`, `selected_scripts`, or `scheduled_actions`. Suggestions never enable a tool or service. |
| `output_format` | Optional response-structure guidance. |
| `web_search` | `inherit`, `disabled`, or `required`. A pack may tighten the profile's policy, but cannot turn disabled search on, enable live access or location sharing, or remove domain restrictions. |
| `confirmation` | `inherit`, `sensitive`, or `always`. `sensitive` and `always` withhold generic Assist control and every selected-script tool instead of pretending those APIs have a trusted confirmation gate. The scheduler remains eligible: `sensitive` confirms its defined sensitive targets, while `always` confirms every scheduled device action. The value is guidance only for other remaining tools. |
| `voice_max_words` | Optional target from 20 through 500 words. The shortest selected-pack limit wins. |
| `allowed_entities` | Optional entity IDs that activate hard scoped mode. |
| `allowed_areas` | Optional area names or aliases that activate hard scoped mode and resolve to exposed, readable entities in those areas. |

Multiple selected packs combine in their selected order. Tool suggestions and scopes are unioned and deduplicated. `disabled` is the strictest web-search policy, and `always` is the strictest confirmation guidance.

#### Hard scoped mode

If any selected pack declares `allowed_entities` or `allowed_areas`, those values form a real, fail-closed tool boundary for that request—not merely a sentence asking the model to stay in scope. Home Assistant currently provides no public way for an integration to apply a per-request entity filter to its generic Assist API. ChatGPT OAuth therefore removes generic Home Assistant Assist tools, history tools, AI Task tools, and camera/image tools while that scoped pack is active.

With `confirmation = "inherit"`, only selected-script tools whose fixed script entity is inside the combined resolved scope and the scheduled-action tools remain eligible. With `confirmation = "sensitive"` or `confirmation = "always"`, selected scripts are also withheld and only the separately enforced scheduler remains available for Home Assistant mutations. Normal Assist exposure and initiating-user permissions still apply. If the configured scope resolves to no accessible entities, no general Home Assistant tools are exposed. A script can act on entities beyond its own script entity, so its internal sequence must enforce any additional scope or safety rules.

This behavior makes selected, strongly typed Home Assistant scripts the preferred way to provide controlled workflows to a scoped skill. Packs without either scope field provide guidance only and do not narrow the profile's normal tools.

Hard scoped mode narrows Home Assistant tools; it does not itself disable hosted web search. Use `web_search = "disabled"` in the pack when the scoped role must not retrieve external information. The profile's live-access, domain, source-display, and location-sharing limits remain the privacy ceiling in every mode.

The current request's opt-in room-entity context and restricted-Jinja entity values are also intersected with the resolved scope. This is still a tool and integration-supplied context boundary, not a redaction engine: text that the user or assistant already wrote in the visible conversation history is not rewritten. Start a new Home Assistant conversation when switching an existing conversation to a role with a narrower information policy.

#### File and privacy boundaries

The loader accepts only direct, regular `.toml` files with the documented keys. It rejects symlinked roots or files, nested packs, unknown keys, invalid UTF-8 or TOML, and unsupported schemas. The strict schema has no way to define tools, arbitrary services, includes, downloads, remote imports, secret or environment-variable expansion, or Python or shell execution. Skill files and their instruction text are never executed: code-looking text inside `instructions` remains literal prompt text and is transmitted as such. Do not put credentials, tokens, addresses, or other secrets in a pack, and review every selected instruction as carefully as any other system prompt.

Loading is bounded to 32 packs, 256 scanned directory entries, 64 KiB per file, and 512 KiB total. A profile may select at most 8 packs. Each pack allows up to 12,000 instruction characters, 2,000 output-format characters, 20 tool suggestions, 100 entity IDs, and 20 areas. The final composed local-skill section is capped at 24,000 characters; a whole pack that would exceed the aggregate pack budget is skipped rather than partially applied.

Skill IDs, names, file paths, instructions, output formats, and scopes are excluded from diagnostics. Diagnostics report only bounded catalog and selection counts. If any explicitly selected pack is missing, invalid, or skipped because the aggregate budget is exceeded, it stops applying and the request enters safe mode: all Home Assistant tools and web search are withheld until every selected pack is available, valid, and within the active limits. Missing or invalid selections appear as unavailable in the next Reconfigure form; aggregate-budget skips are reported only as ID-free counts in diagnostics. Reconfigure the profile to fix or remove the affected selection. The integration does not silently restore the profile's broader tool or web access.

Home Assistant does not provide a generic trusted two-turn confirmation API. When a selected pack requests `confirmation = "sensitive"` or `confirmation = "always"`, ChatGPT OAuth therefore withholds generic Assist control and all selected-script tools rather than relying on model wording. The scheduler described below is the only remaining mutation path: it always enforces two turns for its sensitive targets, and `always` extends that enforcement to every scheduled device action. Confirmation text remains guidance only for other non-scheduler tools, so their own safety behavior still matters.

### Persistent reminders and scheduled actions

Enable **Allow reminders and scheduled actions** for an assistant profile to let it create a deliberately narrow set of future work. The setting is disabled by default. Outside local-skill safe mode, reminder creation and the applicable management tools are available whenever this setting is on. The two device tools are added only when **Enable Home Assistant control** is also on and any active hard scope resolves to at least one accessible entity. The complete tool set is:

- `ScheduleReminder`
- `ScheduleHassTurnOn`
- `ScheduleHassTurnOff`
- `ListScheduledActions`
- `CancelScheduledAction`
- `ConfirmScheduledAction`

This supports requests such as “Remind me in half an hour to check the keg,” “Turn the fan off in 20 minutes,” and “Switch the diffuser back on at 6:00.” It does not schedule arbitrary service calls, scripts, automations, alarm changes, toggles, camera actions, or update installations. A future action may contain up to 40 fixed targets, each Home Assistant user may have up to 25 active items, and execution must be between 5 seconds and one year in the future. A sensitive device action must be more than 15 seconds away so the later confirmation can occur.

The integration resolves a spoken entity, area, or floor name immediately and stores the resulting fixed targets. Every device target must be exposed to Assist and controllable by the initiating user when the item is created. Those permissions, exposure, target existence, service availability, the profile's scheduled-action and Home Assistant control settings, and any current local-skill scope are checked again when it becomes due; scheduling is not a way to preserve access after permission is removed or a feature is disabled. When a hard-scoped local skill is active, scheduled device targets must be inside that resolved scope at creation and execution. Narrowing, invalidating, or removing a scope prevents an affected stored action from running.

Only explicit on and off semantics are supported:

| Entity | Scheduled **on** | Scheduled **off** |
|---|---|---|
| Normal supported entity | `turn_on` | `turn_off` |
| Cover | Open | Close |
| Lock | Lock | Unlock |
| Valve | Open | Close |
| Button or input button | Press once | Not supported |

Locks, valves, buttons, input buttons, sirens, and door, garage, gate, or window covers are treated as sensitive. The first request creates only a five-minute `awaiting_confirmation` item; it does not schedule the device operation. To approve it, the same Home Assistant user must send a later message to the same assistant profile and same nonempty Home Assistant conversation whose entire content is `Confirm scheduled action ABCD1234EFGH`, using the action's returned 12-character reference. Matching is case-insensitive and permits surrounding whitespace plus one optional final `.`, `!`, or `?`, but no other words. The later request must also have a new Home Assistant Context and arrive before both the five-minute confirmation deadline and the scheduled run time. A model-generated `ConfirmScheduledAction` tool call cannot authorize anything by itself; that tool is exposed only after the raw user message matches the reserved phrase and only for its matching reference. Confirmation in the original request, another conversation or profile, or by another household member cannot approve the action.

Each user can list or cancel only that user's active items for the current assistant profile through Assist. During a hard-scoped request, Assist can list, cancel, or confirm only device records whose complete fixed target set remains inside the current scope; reminders and other records are hidden from those management tools. A record created under a scope also stays hidden if that scope is later removed. Items for the account still appear in the native **Scheduled actions** calendar, normally as `calendar.scheduled_actions` when Home Assistant does not need to add a suffix. The calendar is intentionally not an action editor: it supports deletion only and remains the local way to remove work hidden by a changed skill scope. Deleting a pending or awaiting-confirmation event cancels and removes it, while an action already executing cannot be cancelled or deleted. Completed history may also be deleted. Completed, failed, missed, expired, and cancelled records are otherwise retained for seven days; oldest terminal records are pruned when the store would exceed 200 records without discarding active work.

Items are stored in Home Assistant's private persistent storage and restored after a restart. Before restart recovery, every persisted record is revalidated against the scheduler's schema and fixed-operation allowlist; a tampered or invalid record is discarded rather than executed. The scheduler maintains only the nearest-deadline timer. A device action that is more than 15 minutes overdue is marked missed instead of running unexpectedly; a reminder has a 24-hour delivery grace period. Execution is at most once: if Home Assistant restarts while a record is marked executing, that record is marked interrupted and is never retried automatically.

When a reminder becomes due, ChatGPT OAuth creates a Home Assistant persistent notification using the requested title and message. Completion of an actual due reminder or device execution fires `chatgpt_oauth.scheduled_action_finished`; cancellation, confirmation expiry, and an overdue item becoming missed do not fire it. Calendar entries show the reminder title, status, creator display name, action reference, and display target names as applicable, but not the reminder body. Conversation tool-list results, diagnostics, and the completion event's data payload omit Home Assistant entity IDs, user IDs, reminder bodies, and stored tool arguments. Home Assistant's standard local event Context retains the creator's user ID and the creation request's parent Context ID for local auditing and traceability; those Context fields are not event data or model output, and firing the event does not send them to ChatGPT. The reminder body remains only in Home Assistant's private storage and its due persistent notification. Prompts and assistant responses are never copied wholesale into scheduled records.

The calendar is shared according to normal Home Assistant entity permissions. Anyone allowed to read it can see scheduled titles, target display names, statuses, references, and creator display names; anyone allowed to control/delete its events can remove non-executing records. Restrict access to this calendar entity if those human-readable details are sensitive in your household.

### Restricted Jinja system prompts

System prompts support a restricted Jinja environment rendered separately for every Assist request. Available variables are:

- `user_name`, when **Use the current user's display name** is enabled
- `area_name` and `room_name`, when room context is enabled
- `satellite_name` and `device_name`, when satellite context is enabled
- `room_entities`, when room-entity context is enabled
- `local_time` and `now()` in Home Assistant's configured time zone
- `states()`, `is_state()`, and `state_attr()` for only the entities chosen under **Entities the system prompt may read**

Example:

```jinja
You are Jeeves, the voice assistant in {{ area_name }}.
The current user is {{ user_name }}.
The local time is {{ now().strftime('%-I:%M %p') }}.
Quiet mode is {{ states('input_boolean.quiet_mode') }}.
Keep spoken answers under three sentences.
```

An unselected, missing, or unreadable entity returns `unknown` from `states()`, `false` from `is_state()`, and `None` from `state_attr()`. The template does not receive the unrestricted Home Assistant state object, config entries, secrets, environment variables, service calls, the configured home address, or coordinates. User and room variables remain empty unless their existing privacy controls are enabled.

Prompt source and rendered output are size-limited. Entity values are bounded and template syntax contained in state data is neutralized before Home Assistant builds the final prompt, preventing a state value from causing a second template evaluation. A rendering error falls back to the default system prompt instead of crashing Assist.

### AI Task, cameras, and generated images

Enable **Let Assist analyze cameras and create images** for an assistant profile under **Settings → Devices & services → ChatGPT OAuth → Reconfigure**. The conversation agent can then use this integration's own AI Task entity for all of its supported generation modes:

- Generate, transform, summarize, or analyze text and data.
- Analyze an image entity or one fresh, on-demand snapshot from a camera.
- Create a new image or derive an edited image from exposed camera or image references.

For example, you can ask “What's happening at the front door?”, “Create an image of a cozy reading room,” or “Turn the latest driveway camera image into a watercolor painting.” Generated images appear in an Assist card with a local Home Assistant link.

Camera access is deliberately bounded. A camera or image entity must be explicitly exposed to Assist, and the Home Assistant user who started the conversation must have permission to read it. AI Task entities must belong to this integration, support the requested feature, and be controllable by that user. Camera analysis captures one still image only when requested; it does not start continuous monitoring or send a live video stream.

These media tools send display names instead of internal entity IDs. Generated image bytes, camera contents, prompts, and tool arguments are not added to diagnostics or `chatgpt_oauth.conversation_finished` events. The setting is disabled by default and is independent of general Home Assistant entity control.

Home Assistant stores generated images in its AI Task media folder and returns a temporary signed URL. Image generation therefore requires a working Home Assistant media directory.

### Current user, satellite, and room

Each assistant profile has three privacy controls, all disabled by default:

| Setting | Information sent to ChatGPT |
|---|---|
| **Use the current user's display name** | The resolved display name of the Home Assistant user who started this request. Internal user IDs and other users are not included. |
| **Use the voice satellite and current room** | Human-readable labels for the satellite, its associated device, and its Home Assistant area. Device, entity, and area IDs are not included. |
| **Include exposed entities in the current room** | Names, types, and current states for up to 40 relevant entities in that area. Only entities already exposed to Assist are included. |

This lets phrases such as “turn the lights off in here,” “is it warm in this room?”, and “what window is open near me?” resolve against the satellite's current area. The current user's display name can also help the model choose user-labeled calendar and notification entities.

The request context never adds the configured home name, address, latitude, longitude, or unrelated household members. The separate web-search location settings remain independent; **Share precise home location** still sends the location details described in [OpenAI web search](#openai-web-search) when enabled.

### Tool safety limits

Each assistant profile can allow **1–10 Home Assistant tool calls per message** and **10–120 seconds of combined Home Assistant tool execution time**. The defaults are 5 calls and 60 seconds.

The integration also stops repeated calls with identical arguments, repeated failures for one target, alternating no-progress calls, more than 10 hosted web-search actions, and new tool calls after a completed tool result has already produced a final answer. Instead of a generic iteration error, Assist receives a specific explanation such as: “I could not complete that because the same device action failed repeatedly.”

### Conversation-completed event

After every Assist request, the integration fires `chatgpt_oauth.conversation_finished`. The event contains operational metadata only:

- `agent_entity_id`, `conversation_id`, `model`, and `thinking_level`
- `duration_ms`, `tool_names`, `tool_call_count`, and `web_search_used`
- `continued_listening`, `success`, and `error_type`
- `satellite_device_id` and `area_id` when Home Assistant supplied enough satellite context

It never contains the user prompt, assistant response, OAuth data, attachments, or tool arguments. The satellite device and area IDs remain inside Home Assistant's local event bus and are useful for per-room automations.

Example failure notification:

```yaml
automation:
  - alias: Notify when ChatGPT OAuth Assist fails
    triggers:
      - trigger: event
        event_type: chatgpt_oauth.conversation_finished
    conditions:
      - condition: template
        value_template: "{{ not trigger.event.data.success }}"
    actions:
      - action: persistent_notification.create
        data:
          title: ChatGPT OAuth Assist issue
          message: >-
            {{ trigger.event.data.agent_entity_id }} ended with
            {{ trigger.event.data.error_type or 'an unknown error' }} after
            {{ trigger.event.data.duration_ms }} ms.
```

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

- **Reconfigure** to change the entry name, model, Home Assistant control access, AI Task and exposed-camera access, persistent scheduled actions, selected scripts, local skill packs, system prompt, thinking level, source-display behavior, or other web-search defaults.
- **Reauthenticate** when Home Assistant reports that the OAuth session has expired or been revoked.
- **Download diagnostics** when filing a bug report. Diagnostics exclude tokens, account identifiers, prompts, attachments, conversation text, search queries, source contents, and generated output.

## Privacy and security

Prompts, enabled Home Assistant tool context, images, PDFs, and web-search queries used in a request are transmitted to the hosted ChatGPT service. When live web access is enabled, the search service may retrieve external pages. Review the service's terms and privacy controls before sending sensitive content.

- Web content is untrusted and may contain prompt-injection attempts. Treat searched instructions as advisory and verify important results.
- Approximate location sharing sends only Home Assistant's country and time zone. Precise location sharing is a separate, disabled-by-default option that sends exact latitude, longitude, and the configured home name. Home Assistant does not expose a separate street-address field, but exact coordinates can identify the home address.
- OAuth access tokens and refresh tokens are stored in Home Assistant's config-entry storage.
- Do not expose `.storage`, callback URLs, debug logs containing credentials, or unredacted request captures.
- Only expose the Home Assistant entities that the Assist agent genuinely needs.
- AI Task camera tools can access only exposed camera/image entities, use one on-demand still per analysis call, and honor the initiating user's entity permissions.
- Selected-script tools can invoke only scripts explicitly chosen for that assistant, reject undeclared fields, honor the initiating user's control permission, and exclude script IDs and arguments from diagnostics.
- Persistent scheduled actions are disabled by default, allow only reminders and explicit device on/off operations, recheck permissions at execution, and require the same user to send the reserved whole-message phrase `Confirm scheduled action <12-character reference>` in a later turn for sensitive targets. A tool call alone cannot grant confirmation.
- Calendar entries, scheduler tool results, diagnostics, and scheduler event data omit scheduled entity IDs, user IDs, reminder bodies, and stored arguments. The standard local Home Assistant event Context retains its creator user and parent Context for auditing. Reminder content remains only in Home Assistant's private storage and its due persistent notification.
- Local skill packs are loaded only from explicitly selected, direct-child TOML files. Their schema cannot download content, execute code, define arbitrary services, reveal Home Assistant secrets, or expand profile permissions; skill files and literal instruction text are never executed, but selected instructions are sent to ChatGPT and must not contain secrets. A missing, invalid, or aggregate-budget-skipped selected pack activates safe mode, withholding all Home Assistant tools and web search until fixed.
- A local skill with an entity or area scope disables generic Assist, history, AI Task, and media APIs for that request so the scope fails closed. In-scope selected scripts remain only with `confirmation = "inherit"`; the separately enforced scheduler remains available when enabled.
- Restricted prompt templates can read only explicitly selected entities that the initiating user may read; prompts and selected entity IDs remain excluded from diagnostics.
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
- Scheduled actions are limited to reminders and explicit on/off operations; use a selected Home Assistant script or automation when a future workflow needs richer logic or its own confirmation and safety checks.
- Home Assistant has no generic trusted confirmation API. A skill pack requesting `sensitive` or `always` confirmation therefore removes generic Assist control and selected scripts; it is only guidance for other remaining tools. Scheduled actions enforce their own later-turn, exact-phrase flow, with `always` applying it to every scheduled device action.
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

### Assist cannot analyze a camera or create an image

- Enable **Let Assist analyze cameras and create images** under the relevant assistant profile's **Reconfigure** screen.
- Expose the camera or image entity to Assist and confirm the initiating Home Assistant user can read it.
- Confirm the ChatGPT OAuth AI Task entity is enabled and that the user can control it.
- For generated images, confirm Home Assistant's media directory is available and writable.

### A selected script does not appear as a tool

- Open the relevant assistant profile's **Reconfigure** screen and add it under **Scripts this assistant may run**.
- Confirm the script is enabled, loaded, and runnable by the Home Assistant user starting the conversation.
- Add selectors and descriptions to the script's fields so the model receives clear, typed inputs.
- Restart Home Assistant after updating the integration itself; ordinary script edits do not require an integration restart.

### A local skill pack does not appear or apply

- Confirm the file is a direct-child regular file under `/config/openai_oauth_conversation/skills` and has a lowercase `.toml` filename with a valid skill ID.
- Confirm it uses UTF-8, `schema_version = 1`, all required fields, and only the documented keys and values. Symlinks and nested files are rejected. The schema cannot define includes or executable behavior; text that merely looks like code inside `instructions` is treated as literal prompt text and is never run.
- Reopen the relevant assistant profile's **Reconfigure** screen and explicitly select it under **Local skill packs**. Merely creating the file does not enable it.
- An edited selected pack applies on the next conversation request. A removed or invalid pack stops applying and appears as unavailable when Reconfigure is opened again; an aggregate-budget-skipped pack remains selected and is reported through the ID-free skipped count in diagnostics. In either case, safe mode withholds all Home Assistant tools and web search instead of falling back to broader profile access.
- If an entity or area scope is present, generic Home Assistant, history, AI Task, and media tools disappear by design. Add the required selected-script entity to the scope or remove the scope only if the wider profile permissions are intended.
- If `confirmation` is `sensitive` or `always`, generic Assist control and all selected-script tools are withheld by design. Enable scheduled actions for the enforced future-action path, or use `inherit` only when the selected scripts provide their own required safety checks.

### A scheduled action does not run

- Confirm **Allow reminders and scheduled actions** is enabled for the assistant profile.
- Confirm the scheduled time is at least 5 seconds and no more than one year away, and that the user has fewer than 25 active scheduled items. Sensitive device actions need more than 15 seconds for confirmation.
- For a device action, also enable **Home Assistant control** and confirm every target is available, exposed to Assist, permitted for the creating user, and inside any active local-skill scope when created. Availability, exposure, permission, profile settings, current scope, and service support are checked again when the item becomes due; a narrowed, missing, invalid, or removed scope blocks affected work.
- Sensitive targets remain pending until the same user sends `Confirm scheduled action <12-character reference>` as the whole message in a later turn of the same nonempty Home Assistant conversation and assistant profile. The match is case-insensitive, allows only surrounding whitespace and one optional final punctuation mark (`.`, `!`, or `?`), and expires after five minutes. Extra words, a reused request Context, or a different profile, conversation, or user cannot confirm it; neither can an ungrounded tool call.
- Ask Assist to list scheduled actions. An overdue device action is marked missed after 15 minutes rather than running unexpectedly, and an action interrupted during execution is not retried.
- Check Home Assistant persistent notifications for reminders and the ChatGPT OAuth calendar for item status.

### A system-prompt template shows `unknown`

- Add every entity referenced by `states()`, `is_state()`, or `state_attr()` under **Entities the system prompt may read**.
- Confirm the initiating user can read that entity.
- Enable the corresponding user or room privacy setting before using `user_name`, `area_name`, `satellite_name`, or `room_entities`.

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

Open **Settings → Devices & services → ChatGPT OAuth → Reconfigure** and disable **Include sources in response text**. Assist will speak only the natural answer. Interfaces that support response cards can still display source details, and integration actions retain structured `citations`, `sources`, and `searches` metadata.

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

- Upgrading from 1.7.1 to 1.8.0 preserves existing profiles and adds persistent scheduled actions as disabled and local skill selections as empty. No new tool, device, file, web-search, or prompt access is granted until explicitly configured.
- Upgrading from 1.5.0 to 1.6.0 preserves existing settings and adds AI Task/camera tools as a disabled-by-default privacy option.
- Upgrading from 1.4.0 to 1.5.0 preserves existing settings, keeps all user and room context disabled, and adds five-call and 60-second tool-safety defaults.
- Upgrading from 1.2.0 to 1.2.1 changes only repository ownership metadata and public release packaging; Home Assistant configuration and runtime behavior are unchanged.
- Upgrading from 1.1.1 to 1.2.0 adds configurable source presentation. Existing entries default to voice-friendly text without appended sources; re-enable **Include sources in response text** to preserve the v1.1 behavior.
- Upgrading from 1.1.0 to 1.1.1 changes only HACS packaging and release automation; Home Assistant configuration and runtime behavior are unchanged.
- Upgrading from 1.0.0 to 1.1.x preserves existing entries and leaves web search disabled until explicitly enabled.
- Upgrading from 0.5.x preserves the stable domain, config-entry data, service namespace, conversation unique ID, and AI Task unique ID.

See [MIGRATION.md](MIGRATION.md) for details.

## Removal

Review and cancel any scheduled items before removing the integration. Removing the config entry deletes its private scheduled-action store and **Scheduled actions** calendar; pending device work and reminders will not run afterward.

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
