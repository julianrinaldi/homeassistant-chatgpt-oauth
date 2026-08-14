# Validation report — ChatGPT OAuth 1.1.1

This release corrects the HACS distribution format without changing integration runtime behavior.

## Repository layout validated

The repository root contains:

```text
README.md
hacs.json
custom_components/openai_oauth_conversation/
```

There is exactly one integration directory beneath `custom_components`. The unnecessary `custom_components/__init__.py` file has been removed.

## HACS metadata validated

`hacs.json` declares:

```json
{
  "name": "ChatGPT OAuth",
  "content_in_root": false,
  "zip_release": true,
  "filename": "chatgpt_oauth.zip",
  "hide_default_branch": false,
  "homeassistant": "2026.4.0"
}
```

The manifest includes the required domain, name, documentation, issue tracker, code owners, and version fields. The domain matches the integration directory.

## Distribution archives validated

Three different layouts are intentionally produced:

1. **GitHub repository package** — repository files are at the ZIP root, including `README.md`, `hacs.json`, and `custom_components/openai_oauth_conversation`.
2. **HACS release asset (`chatgpt_oauth.zip`)** — integration files such as `__init__.py`, `manifest.json`, `config_flow.py`, `translations/`, and `brand/` are directly at the ZIP root. It contains no `custom_components` or enclosing integration directory.
3. **Manual archive (`chatgpt-oauth-manual.zip`)** — contains `custom_components/openai_oauth_conversation` so it can be extracted directly into `/config`.

The HACS archive validator rejects absolute paths, parent traversal, an enclosing `custom_components` path, an enclosing `openai_oauth_conversation` path, or missing required files.

## Source checks completed

- Python files compile successfully.
- JSON, YAML, and TOML metadata parse successfully.
- Manifest, project, constants, release notes, and package names use version `1.1.1` consistently.
- `strings.json` and `translations/en.json` remain identical.
- The stable internal domain remains `openai_oauth_conversation`.
- No `.storage`, `.env`, compiled Python, Python cache, Git metadata, or obvious credential files are included in the archives.
- Both distribution ZIPs pass ZIP integrity checks and extract to the intended paths.
- The release workflow builds both archives, generates SHA-256 checksums, validates their layouts, and uploads them to the GitHub release on a version tag.
- Existing web search, AI Task, image generation, attachment, thinking-level, OAuth-refresh, SSE, and request-serialization code is unchanged from 1.1.0.

## Checks requiring GitHub

The following remain authoritative after the repository is pushed:

- HACS Action.
- Hassfest Action.
- Ruff format and lint.
- Home Assistant test matrix.
- Tag-triggered release creation and asset upload.
- Clean HACS installation from the public GitHub release.

## Checks requiring a real account

A maintainer should perform live smoke tests for Assist, data generation, structured output, image generation, image/PDF analysis, Home Assistant tool calls, OAuth refresh, and OpenAI web search before requesting default HACS inclusion.
