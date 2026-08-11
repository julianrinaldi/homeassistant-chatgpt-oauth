# ChatGPT OAuth 1.1.0

ChatGPT OAuth 1.1.0 adds native OpenAI web search throughout the integration while preserving the existing Assist, AI Task, image-generation, attachment, and thinking-level functionality.

## Highlights

- OpenAI Responses API `web_search` support for Assist and plain-text AI Tasks.
- Web search in the existing Generate content and Analyze image actions.
- New `openai_oauth_conversation.web_search` action for forced, sourced searches.
- Disabled, automatic, or required search behavior.
- Low, medium, or high search-result context.
- Live internet access or cache/index-only mode.
- Optional country-and-time-zone-only Home Assistant location hints.
- Optional domain allowlisting in the dedicated action.
- Clickable inline citations, an appended source list, and machine-readable citation/source/search metadata.
- Required-search validation that refuses to silently return an unsearched answer.
- Privacy-preserving compatibility retries for optional controls and the legacy preview tool; cache-only and domain restrictions are never silently removed.

## Examples

Enable **Automatic** or **Required** search under:

```text
Settings → Devices & services → ChatGPT OAuth → Reconfigure
```

A dedicated sourced search can be called from an automation:

```yaml
- action: openai_oauth_conversation.web_search
  data:
    config_entry: 0123456789abcdef0123456789abcdef
    query: What is the latest stable Home Assistant release?
    web_search_context_size: high
    web_search_live_access: true
    allowed_domains:
      - home-assistant.io
      - github.com
  response_variable: research
```

The response exposes `text`, `raw_text`, `citations`, `sources`, `searches`, `model`, `reasoning_effort`, `search_context_size`, and `live_access`.

## Upgrade compatibility

The internal domain remains `openai_oauth_conversation`. Existing config entries, credentials, entity unique IDs, action names, and automations are preserved. Existing entries migrate with web search disabled, so no new external-search behavior is enabled without an explicit reconfiguration.

Image generation is unchanged and continues to support up to 10 reference images.

## Important notice

This is an unofficial community integration that uses a hosted ChatGPT/Codex OAuth backend. It is not affiliated with or endorsed by OpenAI or Home Assistant, and backend behavior can change without notice.

Web pages are untrusted input. Search results and citations should be reviewed before they are used for consequential actions.
