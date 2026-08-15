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

## Maintainer release process

Release validation and publishing are deliberately separate. The `Build release`
workflow validates the tagged source, builds both installation archives, verifies
their layouts, generates checksums, and uploads the three files as a workflow
artifact. It does not create or modify a GitHub release.

GitHub releases must be published from a GitHub CLI session authenticated as the
repository owner. A release created with the workflow's automatic token would be
attributed to `github-actions[bot]`, even when a maintainer pushed the tag.

Before tagging a release, update the integration and project versions, write the
changelog and release notes, run the complete test suite, and confirm the working
tree is clean. Then use the following process, replacing the example values and
absolute release-notes path:

```bash
REPOSITORY="julianrinaldi/homeassistant-chatgpt-oauth"
RELEASE_TAG="vX.Y.Z"
RELEASE_TITLE="ChatGPT OAuth X.Y.Z — Short human-readable summary"
RELEASE_NOTES="/absolute/path/to/release-notes.md"

test "$(gh api user --jq .login)" = "julianrinaldi"
test "$(gh repo view "$REPOSITORY" --json owner --jq .owner.login)" = "julianrinaldi"
test -s "$RELEASE_NOTES"
test -z "$(git status --short)"

git push origin main
git tag -a "$RELEASE_TAG" -m "$RELEASE_TITLE"
git push origin "$RELEASE_TAG"
```

The tag push starts the release build. Wait for that exact tag's workflow run and
download only its validated artifact:

```bash
RUN_ID=""
for attempt in {1..30}; do
  RUN_ID="$(gh run list \
    --repo "$REPOSITORY" \
    --workflow release-check.yml \
    --branch "$RELEASE_TAG" \
    --event push \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId')"
  test -z "$RUN_ID" || break
  sleep 2
done
test -n "$RUN_ID"
gh run watch "$RUN_ID" --repo "$REPOSITORY" --exit-status

RELEASE_ASSET_DIR="$(mktemp -d \
  "${TMPDIR:-/tmp}/chatgpt-oauth-release.XXXXXX")"
gh run download "$RUN_ID" \
  --repo "$REPOSITORY" \
  --name chatgpt-oauth-release-assets \
  --dir "$RELEASE_ASSET_DIR"

test -f "$RELEASE_ASSET_DIR/chatgpt_oauth.zip"
test -f "$RELEASE_ASSET_DIR/chatgpt-oauth-manual.zip"
test -f "$RELEASE_ASSET_DIR/SHA256SUMS.txt"
(
  cd "$RELEASE_ASSET_DIR"
  shasum -a 256 -c SHA256SUMS.txt
)
```

Publish with the same verified, owner-authenticated GitHub CLI session. The
`--verify-tag` option prevents the release command from silently creating or
moving a tag.

```bash
test "$(gh api user --jq .login)" = "julianrinaldi"
gh release create "$RELEASE_TAG" \
  "$RELEASE_ASSET_DIR/chatgpt_oauth.zip" \
  "$RELEASE_ASSET_DIR/chatgpt-oauth-manual.zip" \
  "$RELEASE_ASSET_DIR/SHA256SUMS.txt" \
  --repo "$REPOSITORY" \
  --verify-tag \
  --title "$RELEASE_TITLE" \
  --notes-file "$RELEASE_NOTES" \
  --latest

test "$(gh api \
  "repos/$REPOSITORY/releases/tags/$RELEASE_TAG" \
  --jq .author.login)" = "julianrinaldi"
gh release view "$RELEASE_TAG" --repo "$REPOSITORY" --web
```

Never add release creation back to the workflow with `${{ github.token }}`. Keep
the downloaded directory until the published release's title, notes, assets, and
author have been checked.

## Security invariants

Changes to scheduled actions and local skills must preserve these boundaries:

- Scheduled-action confirmation is authorization derived from the raw user message, not from the model's choice to call a tool. The entire later message must match `Confirm scheduled action <12-character reference>` case-insensitively, with only surrounding whitespace and one optional terminal `.`, `!`, or `?`. The confirmation must remain bound to the same Home Assistant user, assistant profile, nonempty conversation, a new request Context, the five-minute lifetime, and the scheduled run time. Do not expose `ConfirmScheduledAction` without the trusted raw-message match.
- Persisted scheduled records must be schema-checked and revalidated against the fixed-operation allowlist before restart recovery. Invalid or tampered records must be discarded, never executed or repaired into a broader action.
- The scheduled-action completion event's data must stay privacy-safe. Home Assistant's standard local event Context intentionally retains the creator user ID and parent Context ID for auditing; do not describe those Context fields as event data or send them to the model.
- Local skill TOML is declarative prompt and policy data. The schema cannot define executable tools, arbitrary services, includes, downloads, secret expansion, or Python or shell execution, and neither files nor instruction text are ever executed. Code-looking instruction text is still literal prompt content, not something the loader rejects solely for looking like code.
- If any explicitly selected local pack is missing, invalid, or skipped by an aggregate limit, keep the request in safe mode with general Home Assistant tools and web search withheld until every selected pack is available, valid, and within the active limits. Never fall back silently to broader profile permissions.


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
