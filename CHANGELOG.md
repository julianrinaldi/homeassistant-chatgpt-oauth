# Changelog

All notable user-facing changes are documented in this file.

## [1.8.1] - 2026-09-03

### Fixed

- Declared `voluptuous-openapi==0.4.1` as a Home Assistant-managed runtime dependency, preventing startup from failing with `ModuleNotFoundError: No module named 'voluptuous_openapi'` on clean installations.
- Added the dependency to the developer test requirements and validated the runtime import during release packaging.

### Compatibility

- No configuration migration or reauthentication is required.
- Existing OAuth credentials, assistant profiles, entities, actions, automations, AI Tasks, scheduled actions, local skills, and settings remain unchanged.
- Restart Home Assistant Core after updating so Home Assistant installs and loads the newly declared dependency.

## [1.8.0] - 2026-08-15

### Added

- An opt-in **Allow reminders and scheduled actions** setting for each assistant profile, with restart-safe `ScheduleReminder`, `ListScheduledActions`, `CancelScheduledAction`, and `ConfirmScheduledAction` tools. `ScheduleHassTurnOn` and `ScheduleHassTurnOff` are also available when Home Assistant control is enabled and the active scope permits device targets.
- A native **Scheduled actions** Home Assistant calendar that displays pending and historical items and supports deletion to cancel pending work or remove history; it intentionally cannot create or edit arbitrary actions.
- Due reminders delivered as Home Assistant persistent notifications and a privacy-safe `chatgpt_oauth.scheduled_action_finished` event after actual due reminder or device execution.
- Explicitly selected, user-managed TOML skill packs loaded from `/config/openai_oauth_conversation/skills`, with reusable instructions, output-format guidance, bounded voice length, tool suggestions, web-search policy, confirmation guidance, and optional entity or area scopes.
- Per-request loading for already selected local packs, so reviewed file edits apply on the next conversation without restarting Home Assistant.

### Scheduled-action reliability and safety

- Scheduling is limited to reminders and explicit device on/off semantics. It cannot queue arbitrary services, scripts, automations, alarm changes, future toggles, camera actions, or update installations.
- Spoken entity, area, and floor targets resolve immediately to at most 40 fixed entities. Local-skill scope is enforced at creation and re-resolved at execution; narrowing, invalidating, or removing a scope blocks affected work. Target existence, Assist exposure, creating-user permissions, current profile control settings, and fixed service availability are also checked again before execution.
- Each Home Assistant user is limited to 25 active items, with a scheduling window from 5 seconds through one year.
- Locks, valves, buttons, input buttons, sirens, and door, garage, gate, or window covers require the same Home Assistant user to send `Confirm scheduled action <12-character reference>` as the entire later message to the same profile and same nonempty conversation. Matching is case-insensitive with only surrounding whitespace and one optional terminal `.`, `!`, or `?`; the request must have a new Home Assistant Context and arrive within five minutes. The tool is not exposed without that raw phrase, so a model tool call alone cannot authorize the action.
- Scheduled items persist across restarts and use one nearest-deadline timer. Device operations more than 15 minutes overdue are marked missed; reminders have a 24-hour delivery grace period.
- Execution is at most once. An item found in the executing state after a restart is marked interrupted instead of being retried and potentially repeating a device action.
- Persisted records are revalidated against the scheduler's schema and fixed-operation allowlist before restart recovery. Tampered or invalid records are discarded rather than executed.
- Pending items can be cancelled through Assist or calendar deletion, but an operation already executing cannot be cancelled. Terminal history is retained for seven days, with oldest terminal records pruned when the store would exceed 200 records without discarding active work.

### Local-skill boundaries

- A pack file has no effect until explicitly selected for an assistant profile; only selected pack prompt content and applicable policy guidance are transmitted to ChatGPT.
- The strict schema accepts only documented declarative TOML fields and rejects symlinked roots or files, nested packs, unknown keys, unsupported schema versions, and invalid UTF-8/TOML. It cannot define includes, secret expansion, downloads, remote imports, arbitrary tools or services, or Python or shell execution. Skill files and instruction text are never executed; code-looking instruction text remains literal prompt content.
- A missing, invalid, or aggregate-budget-skipped selected pack activates safe mode. All Home Assistant tools and web search remain withheld until every selected pack is available, valid, and within the active limits instead of silently returning broader profile access.
- Tool suggestions can prefer only tools already enabled by the profile and never enable a capability, service, live web access, precise location, or broader Home Assistant permission.
- Skill web policy can inherit or narrow the profile's search policy. A `required` pack cannot turn disabled search on, while `disabled` always keeps it off.
- Entity or area scopes activate a hard fail-closed mode. Generic Assist, history, AI Task, and camera/image APIs are removed for that request. In-scope selected-script tools remain only with `confirmation = "inherit"`; the independently permission-checked scheduler remains eligible when enabled.
- For `confirmation = "sensitive"` or `confirmation = "always"`, generic Assist control and every selected-script tool are withheld because Home Assistant has no generic trusted confirmation API. History and media may remain without a hard scope, and confirmation text is guidance only for those other tools. The scheduler separately enforces confirmation for sensitive targets, with `always` extending it to every scheduled device action.
- Loading is bounded to 32 catalog files, 64 KiB per file, 512 KiB total, 8 selected packs per profile, and strict per-field and combined instruction limits.

### Privacy

- Scheduled-action storage is private to Home Assistant. Calendar entries use human-readable titles, creator names, action references, statuses, and target display names without exposing Home Assistant entity or user IDs. Normal Home Assistant permissions determine who can read those details or delete non-executing calendar events.
- Scheduler tool-list results, diagnostics, and completion-event data omit reminder bodies, stored tool arguments, entity IDs, user IDs, complete prompts, and assistant responses. Home Assistant's standard local event Context retains the creator user ID and parent Context ID for auditing; those Context fields are not event data or model output and are not sent to ChatGPT by firing the event. The reminder body appears only in private storage and its due persistent notification; its title is also visible on the calendar.
- Skill IDs, names, paths, instructions, output formats, and entity or area scopes are excluded from diagnostics; only bounded catalog and selection counts are reported.
- Opt-in room-entity context and restricted-Jinja state lookups require an authenticated initiating Home Assistant user, honor that user's read permissions, and are intersected with an active local-skill scope.
- Both scheduled actions and local skill selections default to disabled or empty, so upgrading grants no new device, file, web-search, or prompt access.

### Release process and compatibility

- The automated release workflow is now read-only. It validates the tagged version, builds both installation archives, verifies their layouts, generates checksums, and uploads workflow artifacts without creating or changing a GitHub release.
- GitHub releases are published after that automated build through the authenticated `julianrinaldi` account, so releases show the human repository owner rather than `github-actions[bot]` as publisher.
- Config entries migrate automatically to version 14 with scheduled actions disabled and no selected local skills. Existing OAuth credentials, assistant profiles, entities, selected scripts, prompt templates, actions, and automations remain compatible; no reauthentication is required.

## [1.7.1] - 2026-08-15

### Fixed

- Clean GitHub Actions runners now install the exact requirements declared by the Home Assistant conversation and camera components before collecting integration tests.
- The release test matrix can validate both the minimum supported Home Assistant 2026.4.0 release and Home Assistant 2026.7.4 instead of failing because the runner omitted Home Assistant's dynamically installed component packages.

### Compatibility

- Integration behavior and config-entry version are unchanged from 1.7.0.
- The selected-script tools and restricted Jinja prompt features from 1.7.0 are included unchanged.
- No reauthentication or configuration change is required.

## [1.7.0] - 2026-08-15

### Added

- A per-profile **Scripts this assistant may run** selector that exposes only explicitly approved Home Assistant scripts as named conversation tools.
- Strongly typed script parameters derived from Home Assistant field selectors, including numeric bounds and select options, with independent runtime validation of required and undeclared fields.
- Blocking selected-script execution with bounded JSON-safe response data returned to the conversation model.
- Restricted Jinja system prompts rendered per Assist request with `user_name`, room, satellite, device, local-time, and `now()` variables.
- Per-profile **Entities the system prompt may read** selection for allowlisted `states()`, `is_state()`, and `state_attr()` lookups.

### Privacy and safety

- Selected scripts remain unavailable until explicitly chosen and still require the initiating user's control permission.
- The model cannot select an arbitrary script or add undeclared script arguments; selected scripts work independently of unrestricted Home Assistant control.
- Prompt templates cannot enumerate Home Assistant states, read config entries, secrets, environment variables, services, addresses, or coordinates.
- User and room template variables follow the existing disabled-by-default context settings, and selected entity states require the initiating user's read permission.
- Template-looking text inside entity data is neutralized before Home Assistant's final prompt expansion, and rendering failures fall back safely instead of crashing Assist.
- Prompts, selected entity IDs, script entity IDs, and tool arguments remain excluded from diagnostics and conversation-completed events.

### Compatibility

- Config entries migrate to version 13 with empty selected-script and prompt-entity lists, so upgrading grants no new access automatically.
- Existing credentials, assistant entities, prompts, actions, automations, and AI Task behavior remain compatible; no reauthentication is required.

## [1.6.3] - 2026-08-15

### Fixed

- AI media tool preparation now ignores Home Assistant's internal computed-name markers instead of trying to sort them together with text aliases.
- Enabling camera analysis no longer fails with `TypeError: '<' not supported between instances of 'str' and 'ComputedNameType'`.

### Compatibility

- Human-readable aliases continue to work across both older and newer Home Assistant entity-registry formats.
- No configuration migration or reauthentication is required.

## [1.6.2] - 2026-08-15

### Fixed

- Enabling **Let Assist analyze cameras and create images** no longer crashes the Assist pipeline on Home Assistant releases whose entity registry does not provide the `name_by_user` field.
- AI Task, camera-analysis, and image-generation tools now prepare human-readable entity aliases through a version-compatible registry lookup.

### Compatibility

- No configuration migration or reauthentication is required.
- Camera and image access remains opt-in and continues to require explicit Assist exposure and user read permission.

## [1.6.1] - 2026-08-15

### Fixed

- Web-search action responses no longer repeat an identical answer under `text`, `raw_text`, and `cited_text`.
- In the dedicated web-search action, `raw_text` and `cited_text` are now included only when they provide a genuinely different answer variant.
- Consulted source URLs remain in the web-search action's top-level `sources` list instead of being duplicated inside each item in the lower-level `searches` audit trail.

### Compatibility

- The primary `text`, structured `citations`, unique `sources`, and search-action metadata remain available.
- The response shape of `generate_content` and `analyze_image` remains unchanged.
- Config entries, OAuth credentials, entities, and settings require no migration or reauthentication.

## [1.6.0] - 2026-08-15

### Added

- An opt-in **Let Assist analyze cameras and create images** setting for every Assist conversation profile.
- A `RunAITask` conversation tool that delegates text, data, image-analysis, and transformation requests to this integration's AI Task entity without recursively exposing Home Assistant controls.
- An `AnalyzeCamera` conversation tool that captures and analyzes one fresh snapshot from a camera exposed to Assist.
- A `GenerateImage` conversation tool for new images and edits based on optional exposed camera or image references.
- Assist response cards for generated images, including a local signed Home Assistant media link.

### Privacy and safety

- AI Task entities must belong to this integration, support the requested feature, and be controllable by the initiating Home Assistant user.
- Camera and image sources must be explicitly exposed to Assist and readable by that user.
- Camera analysis is on demand and limited to one still image per call; it does not expose a continuous stream.
- The model receives human-readable provider and source labels instead of internal entity IDs.
- Generated image bytes, camera contents, prompts, and media tool arguments are excluded from diagnostics and conversation-completed events.

### Compatibility

- Config entries migrate to version 12 with AI Task and camera tools disabled by default.
- Existing OAuth credentials, assistant profiles, entities, actions, and automations remain compatible.

## [1.5.0] - 2026-08-15

### Added

- Opt-in current-user context that sends only the initiating Home Assistant user's resolved display name.
- Opt-in voice-satellite, associated-device, and current-room context using human-readable labels rather than registry IDs.
- Optional current-room entity context, limited to 40 relevant entities already exposed to Assist.
- Per-profile limits of 1–10 Home Assistant tool calls and 10–120 seconds of combined tool execution time.
- Detection for repeated identical calls, repeated target failures, alternating no-progress calls, excessive hosted web-search actions, and tool calls attempted after a final answer is available.
- A `chatgpt_oauth.conversation_finished` event with response timing, model, tool-usage, success, listening, satellite-device, and area metadata.

### Privacy and reliability

- User, satellite, room, and room-entity prompt context is disabled by default.
- Request context never includes opaque internal IDs, the configured home name, address, coordinates, or unrelated household members. The existing web-search location controls remain separate.
- Completion events never include prompts, assistant responses, OAuth information, attachments, or tool arguments.
- Tool safety stops now return a specific natural-language explanation instead of the generic maximum-iterations error.

### Compatibility

- Config entries migrate to version 11 with all new context settings off, a five-call default, and a 60-second tool-time default.
- Existing OAuth credentials, assistant profiles, entities, actions, and automations remain compatible.

## [1.4.0] - 2026-08-15

### Added

- An opt-in **Share precise home location** setting for web search. It supplies Home Assistant's exact latitude, longitude, configured home name, country, and time zone as trusted request context.
- A `web_search_use_home_assistant_precise_location` override for the `generate_content`, `analyze_image`, and dedicated `web_search` actions.

### Changed

- The existing country-and-time-zone option is now labeled **Share approximate location** so its privacy behavior is clear.
- Location settings now explain that Home Assistant does not provide a separate street-address field and that exact coordinates can identify a home address.

### Privacy and compatibility

- Precise location sharing is disabled by default. Existing entries retain their current approximate-location behavior and migrate with precise sharing off.
- Coordinates and the configured home name are never included in diagnostics or normal response metadata.
- Existing OAuth credentials, assistant profiles, entities, actions, and automations remain compatible.

## [1.3.1] - 2026-08-15

### Changed

- Replaced internal setting names with plain-language labels throughout account and assistant-profile setup and reconfiguration.
- Added clear explanations for Home Assistant history access, conversation memory modes and limits, and web-search source links.
- Renamed the four memory choices to describe what each one remembers.
- Replaced the optional memory-limit controls with standard number fields, removing the confusing extra enable checkbox.

### Compatibility

- Existing settings, OAuth credentials, assistant profiles, entities, actions, and automations are unchanged.
- The stable internal domain remains `openai_oauth_conversation`.

## [1.3.0] - 2026-08-15

### Added

- Multiple Assist conversation profiles can now share one ChatGPT OAuth account while keeping independent model, prompt, thinking-level, tool, web-search, and memory settings.
- Configurable conversation memory modes for the current turn, recent turns, summarized older turns, or bounded full history.
- Optional read-only LLM tools for entity history, long-term statistics, and Energy Dashboard data, with exposure checks and bounded query ranges.

### Changed

- Config entries migrate to version 9 and expose profile-specific, non-sensitive diagnostics.
- Existing entries retain full-history behavior with a 64,000-character safety limit; new profiles default to 12 recent turns and a 16,000-character limit.
- The package version is now 1.3.0 and declares the Home Assistant recorder and energy dependencies used by history tools.

### Compatibility

- The stable internal domain, default conversation unique ID, OAuth credentials, existing actions, and existing entity IDs remain unchanged.
- Read-only history tools are disabled by default and never permit database mutation.

## [1.2.1] - 2026-08-14

### Changed

- Corrected all repository URLs, code-owner entries, commit authors, committers, and annotated-tag metadata to use `julianrinaldi`.
- Removed maintainer-only release checklists, private build-validation reports, and tracked release-note staging files from the public repository.
- Changed release automation to generate GitHub release notes without depending on a tracked maintainer file.
- Rebuilt the public Git history beginning with v1.0.0 so historical tags contain the correct repository ownership and public file set.

### Compatibility

- No Home Assistant runtime behavior, OAuth data, config entries, entities, actions, models, thinking levels, web-search behavior, or automations change in this release.
- The stable internal domain remains `openai_oauth_conversation`.

## [1.2.0] - 2026-08-14

### Added

- A configurable **Include sources in response text** setting for OpenAI web search.
- Voice-friendly source presentation for Assist: speech contains only the natural answer while interfaces that support cards receive a separate **Web search sources** card with clickable citations.
- A `cited_text` field in `generate_content`, `analyze_image`, and dedicated `web_search` action responses.
- A per-call `web_search_include_sources` override for all integration text actions.
- Source-presentation state in sanitized diagnostics and AI Task entity attributes.

### Changed

- New and migrated entries default to source-free response text so voice pipelines do not speak citation numbers, URLs, or a source list.
- Citation annotations, unique sources, and reported search actions remain available even when source formatting is hidden from the main text.
- `text` follows the configured or per-call source-display setting; `raw_text` remains the unformatted answer; `cited_text` always provides the clickable cited version.
- Public repository metadata and links now use `julianrinaldi/homeassistant-chatgpt-oauth`.

### Compatibility

- Existing OAuth credentials, config entries, entity IDs, action names, models, thinking levels, and web-search modes are preserved.
- Users who prefer the v1.1 cited-text behavior can enable **Include sources in response text** under Reconfigure.
- The stable internal domain remains `openai_oauth_conversation`.

## [1.1.1] - 2026-08-14

### Fixed

- Corrected the repository and GitHub release packaging for HACS.
- Added a dedicated `chatgpt_oauth.zip` release asset whose integration files are located directly at the ZIP root, as required when HACS extracts a `zip_release` into the integration directory.
- Added a separate `chatgpt-oauth-manual.zip` archive with the normal `custom_components/openai_oauth_conversation` path for manual installation.
- Updated `hacs.json` to declare the exact HACS release filename and ZIP-release behavior.
- Updated the tag workflow to validate both archive layouts and create or update the GitHub release automatically.
- Removed the unnecessary `custom_components/__init__.py` repository file.

### Compatibility

- No integration runtime behavior, config-entry data, OAuth credentials, entities, actions, or automations change in this release.

## [1.1.0] - 2026-08-11

### Added

- Native OpenAI Responses API `web_search` support for Assist, `ai_task.generate_data`, `generate_content`, and `analyze_image`.
- Configurable web-search modes: disabled, automatic, and required.
- Low, medium, and high web-search context sizes.
- Live-internet or cache/index-only search selection through `external_web_access`.
- Optional country-and-time-zone-only Home Assistant location hints.
- A dedicated `openai_oauth_conversation.web_search` action that forces search and returns sourced text, raw text, URL citations, unique sources, and reported search actions.
- Optional domain allowlisting for the dedicated web-search action.
- Machine-readable citation and source metadata in the existing `generate_content` and `analyze_image` action responses.
- Web-search capability and settings in sanitized integration diagnostics and AI Task entity attributes.

### Changed

- GPT-5.6 web-search turns use the full Responses transport required by OpenAI's hosted web-search tool while function-only turns retain Responses Lite.
- Plain-text searched answers preserve the complete generated text, add clickable inline citation markers, and append a source list.
- Required mode validates that the response contains an actual search call or URL citation instead of silently accepting an unsearched answer.
- Web-search responses request complete source lists when supported.
- Setup and reconfiguration now include web-search defaults. Existing entries migrate with web search disabled to preserve previous behavior and privacy expectations.
- Public documentation now covers search configuration, automation use, source metadata, privacy, prompt-injection risk, and troubleshooting.

### Compatibility

- The internal domain remains `openai_oauth_conversation`.
- Existing config entries, OAuth credentials, service calls, entity-registry records, and automations are retained.
- Image generation and its 10-reference-image limit are unchanged.
- The client retries without individually rejected optional search controls and can fall back to `web_search_preview` only when that does not discard cache-only access or a domain allowlist.

## [1.0.0] - 2026-08-05

### Added

- Public identity: **ChatGPT OAuth for Home Assistant**.
- Native Home Assistant Assist conversation agent with a configuration switch for Home Assistant entity inspection and control.
- Native `ai_task.generate_data` support for text and structured output.
- Native `ai_task.generate_image` support for generation, editing, and reference images.
- Up to 10 image attachments per image-generation request.
- Image and PDF attachments for data-generation tasks.
- Model-specific thinking-level selection for GPT-5.6 Sol, Terra, Luna, and GPT-5.5.
- Camera, image entity, local-file, and remote-URL image analysis actions.
- Sanitized diagnostics.
- HACS, Hassfest, lint, test, and release-validation workflows.
- Public migration, security, contribution, and support documentation.

### Changed

- Public-facing integration name changed from **OpenAI OAuth Conversation** to **ChatGPT OAuth**.
- Runtime code is separated into authentication, request transport, content, SSE, response, and structured-output modules.
- OAuth refreshes are serialized per config entry to prevent concurrent token-rotation races.
- Backend errors are classified into authentication, validation, rate-limit, timeout, unavailable-service, and malformed-response failures.
- Attachments and streamed responses have explicit size and timeout protection.
- Image and PDF attachments are validated by file signature before transmission.
- The AI Task entity display name now reflects both data and image capabilities.
- The default model for new entries is GPT-5.6 Terra.
- Home Assistant control access can be enabled or disabled independently of the selected model.

### Compatibility

- The internal domain remains `openai_oauth_conversation`.
- Existing config entries, OAuth credentials, service calls, entity-registry records, and automations are retained.
- Existing conversation and AI Task unique IDs are unchanged.

[1.0.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/releases/tag/v1.0.0
[1.1.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.0.0...v1.1.0

[1.1.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.1.0...v1.1.1
[1.2.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.1.1...v1.2.0
[1.2.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.2.0...v1.2.1
[1.3.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.2.1...v1.3.0
[1.3.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.3.0...v1.3.1
[1.4.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.3.1...v1.4.0
[1.5.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.4.0...v1.5.0
[1.6.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.5.0...v1.6.0
[1.6.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.6.0...v1.6.1
[1.6.2]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.6.1...v1.6.2
[1.6.3]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.6.2...v1.6.3
[1.7.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.6.3...v1.7.0
[1.7.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.7.0...v1.7.1
[1.8.0]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.7.1...v1.8.0
[1.8.1]: https://github.com/julianrinaldi/homeassistant-chatgpt-oauth/compare/v1.8.0...v1.8.1
