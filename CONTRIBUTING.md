# Contributing

Thank you for helping improve ChatGPT OAuth for Home Assistant.

## Before opening a change

- Search existing issues and pull requests.
- Use an issue for behavior changes or new features before investing in a large implementation.
- Never include OAuth tokens, callback URLs, `.storage` content, private prompts, images, PDFs, or unredacted Home Assistant logs.
- Keep the internal domain `openai_oauth_conversation` unchanged. It is a stable compatibility identifier.

## Development setup

A supported Home Assistant development environment is recommended. For a lightweight local environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_test.txt
```

Run validation before submitting a pull request:

```bash
ruff format --check .
ruff check .
pytest
python -m compileall -q custom_components/openai_oauth_conversation
```

HACS validation and Hassfest also run in GitHub Actions.

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md) for the release validation
scope and [OWNER_RELEASE_CHECKLIST.md](OWNER_RELEASE_CHECKLIST.md) for the
maintainer-only publication sequence.

## Design principles

- Preserve existing config entries, unique IDs, and action names.
- Prefer Home Assistant helpers and shared clients over custom global resources.
- Do not log credentials, authorization codes, attachment bodies, prompts, or complete backend responses.
- Keep network operations asynchronous and move blocking file/serialization work to the executor.
- Bound external input, attachment sizes, redirects, streamed events, timeouts, and tool iterations.
- Use the model capability catalog as the single source of truth for models and thinking levels.
- Add focused tests for every behavior change and regression fix.
- Public documentation should describe current supported behavior, not development history.

## Pull requests

A pull request should include:

- A clear description of the user-visible change.
- Tests covering normal behavior and failure behavior.
- Documentation updates when setup, actions, models, limits, or compatibility change.
- A changelog entry for user-visible changes.
- Confirmation that no secrets or private content are included.

By contributing, you agree that your contribution is licensed under the repository's MIT License and that you will follow the Code of Conduct.
