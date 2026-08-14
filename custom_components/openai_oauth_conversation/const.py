"""Constants for the ChatGPT OAuth integration."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "openai_oauth_conversation"
INTEGRATION_NAME: Final = "ChatGPT OAuth"
INTEGRATION_VERSION: Final = "1.1.1"
LOGGER = logging.getLogger(__package__)

REPOSITORY_URL: Final = "https://github.com/hebs/homeassistant-chatgpt-oauth"
ISSUE_TRACKER_URL: Final = f"{REPOSITORY_URL}/issues"

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_EXPIRES: Final = "expires"
CONF_ENABLE_HASS_CONTROL: Final = "enable_home_assistant_control"
CONF_MODEL: Final = "model"
CONF_PROMPT: Final = "prompt"
CONF_REASONING_EFFORT: Final = "reasoning_effort"
CONF_WEB_SEARCH_MODE: Final = "web_search_mode"
CONF_WEB_SEARCH_CONTEXT_SIZE: Final = "web_search_context_size"
CONF_WEB_SEARCH_LIVE_ACCESS: Final = "web_search_live_access"
CONF_WEB_SEARCH_USE_HASS_LOCATION: Final = "web_search_use_home_assistant_location"

DEFAULT_NAME: Final = INTEGRATION_NAME
DEFAULT_ENABLE_HASS_CONTROL: Final = True
DEFAULT_MODEL: Final = "gpt-5.6-terra"
DEFAULT_PROMPT: Final = (
    "You are a helpful voice assistant for Home Assistant. "
    "Answer concisely, naturally, and accurately."
)
DEFAULT_WEB_SEARCH_MODE: Final = "disabled"
DEFAULT_WEB_SEARCH_CONTEXT_SIZE: Final = "medium"
DEFAULT_WEB_SEARCH_LIVE_ACCESS: Final = True
DEFAULT_WEB_SEARCH_USE_HASS_LOCATION: Final = False

DEFAULT_AI_TASK_SYSTEM_PROMPT: Final = (
    "You are a Home Assistant expert. Follow the user's task instructions and "
    "return only the requested result."
)

CLIENT_ID: Final = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL: Final = "https://auth.openai.com/oauth/authorize"
TOKEN_URL: Final = "https://auth.openai.com/oauth/token"
CODEX_RESPONSES_URL: Final = "https://chatgpt.com/backend-api/codex/responses"
REDIRECT_URI: Final = "http://localhost:1455/auth/callback"
SCOPE: Final = "openid profile email offline_access"

# The hosted backend expects a Codex-compatible request identity.
ORIGINATOR: Final = "codex_cli_rs"
CODEX_CLIENT_VERSION: Final = "0.146.1"
CODEX_USER_AGENT: Final = (
    f"codex_cli_rs/{CODEX_CLIENT_VERSION} "
    f"(Home Assistant; ChatGPT OAuth/{INTEGRATION_VERSION})"
)

SERVICE_GENERATE_CONTENT: Final = "generate_content"
SERVICE_ANALYZE_IMAGE: Final = "analyze_image"
SERVICE_WEB_SEARCH: Final = "web_search"

MAX_TOOL_ITERATIONS: Final = 10
TEXT_REQUEST_TIMEOUT: Final = 180
IMAGE_REQUEST_TIMEOUT: Final = 300
OAUTH_REQUEST_TIMEOUT: Final = 30
TOKEN_REFRESH_MARGIN_MS: Final = 5 * 60 * 1000

MAX_IMAGE_ATTACHMENTS: Final = 10
MAX_ATTACHMENT_BYTES: Final = 50 * 1024 * 1024
MAX_ATTACHMENTS_TOTAL_BYTES: Final = 50 * 1024 * 1024
MAX_REMOTE_IMAGE_BYTES: Final = 20 * 1024 * 1024
MAX_REDIRECTS: Final = 5

# This key is assembled to prevent accidental copy/paste back into a request
# payload while still allowing migration and defensive validation.
LEGACY_OUTPUT_LIMIT_KEY: Final = "max_" "output_tokens"
