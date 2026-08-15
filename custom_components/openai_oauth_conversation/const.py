"""Constants for the ChatGPT OAuth integration."""

from __future__ import annotations

import logging
from typing import Final

DOMAIN: Final = "openai_oauth_conversation"
INTEGRATION_NAME: Final = "ChatGPT OAuth"
INTEGRATION_VERSION: Final = "1.6.2"
LOGGER = logging.getLogger(__package__)

REPOSITORY_URL: Final = "https://github.com/julianrinaldi/homeassistant-chatgpt-oauth"
ISSUE_TRACKER_URL: Final = f"{REPOSITORY_URL}/issues"

SUBENTRY_TYPE_ASSISTANT: Final = "assistant"
HISTORY_LLM_API_ID: Final = f"{DOMAIN}_history"
AI_MEDIA_LLM_API_ID: Final = f"{DOMAIN}_ai_media"

CONF_ACCESS_TOKEN: Final = "access_token"
CONF_ACCOUNT_ID: Final = "account_id"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_EXPIRES: Final = "expires"
CONF_ENABLE_HASS_CONTROL: Final = "enable_home_assistant_control"
CONF_ENABLE_HISTORY_TOOLS: Final = "enable_history_tools"
CONF_ENABLE_AI_MEDIA_TOOLS: Final = "enable_ai_media_tools"
CONF_INCLUDE_USER_CONTEXT: Final = "include_user_context"
CONF_INCLUDE_SATELLITE_ROOM_CONTEXT: Final = "include_satellite_room_context"
CONF_INCLUDE_ROOM_ENTITIES: Final = "include_room_entities"
CONF_MAX_TOOL_CALLS: Final = "max_tool_calls_per_turn"
CONF_MAX_TOOL_TIME: Final = "max_total_tool_time"
CONF_MODEL: Final = "model"
CONF_PROMPT: Final = "prompt"
CONF_REASONING_EFFORT: Final = "reasoning_effort"
CONF_WEB_SEARCH_MODE: Final = "web_search_mode"
CONF_WEB_SEARCH_CONTEXT_SIZE: Final = "web_search_context_size"
CONF_WEB_SEARCH_INCLUDE_SOURCES: Final = "web_search_include_sources"
CONF_WEB_SEARCH_LIVE_ACCESS: Final = "web_search_live_access"
CONF_WEB_SEARCH_USE_HASS_LOCATION: Final = "web_search_use_home_assistant_location"
CONF_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: Final = (
    "web_search_use_home_assistant_precise_location"
)
CONF_MEMORY_MODE: Final = "memory_mode"
CONF_MEMORY_MAX_TURNS: Final = "memory_max_turns"
CONF_MEMORY_MAX_CHARACTERS: Final = "memory_max_characters"

MEMORY_MODE_CURRENT_TURN: Final = "current_turn"
MEMORY_MODE_RECENT: Final = "recent"
MEMORY_MODE_SUMMARIZED: Final = "summarized"
MEMORY_MODE_FULL: Final = "full"
MEMORY_MODES: Final = (
    MEMORY_MODE_CURRENT_TURN,
    MEMORY_MODE_RECENT,
    MEMORY_MODE_SUMMARIZED,
    MEMORY_MODE_FULL,
)

DEFAULT_NAME: Final = INTEGRATION_NAME
DEFAULT_ENABLE_HASS_CONTROL: Final = True
DEFAULT_ENABLE_HISTORY_TOOLS: Final = False
DEFAULT_ENABLE_AI_MEDIA_TOOLS: Final = False
DEFAULT_INCLUDE_USER_CONTEXT: Final = False
DEFAULT_INCLUDE_SATELLITE_ROOM_CONTEXT: Final = False
DEFAULT_INCLUDE_ROOM_ENTITIES: Final = False
DEFAULT_MAX_TOOL_CALLS: Final = 5
DEFAULT_MAX_TOOL_TIME: Final = 60
DEFAULT_MODEL: Final = "gpt-5.6-terra"
DEFAULT_PROMPT: Final = (
    "You are a helpful voice assistant for Home Assistant. "
    "Answer concisely, naturally, and accurately."
)
DEFAULT_WEB_SEARCH_MODE: Final = "disabled"
DEFAULT_WEB_SEARCH_CONTEXT_SIZE: Final = "medium"
DEFAULT_WEB_SEARCH_INCLUDE_SOURCES: Final = False
DEFAULT_WEB_SEARCH_LIVE_ACCESS: Final = True
DEFAULT_WEB_SEARCH_USE_HASS_LOCATION: Final = False
DEFAULT_WEB_SEARCH_USE_HASS_PRECISE_LOCATION: Final = False
DEFAULT_MEMORY_MODE: Final = MEMORY_MODE_RECENT
DEFAULT_MEMORY_MAX_TURNS: Final = 12
DEFAULT_MEMORY_MAX_CHARACTERS: Final = 16_000
# Existing entries used the complete Home Assistant chat log before v1.3.0.
# Migration keeps that behavior with a generous safety ceiling.
MIGRATED_MEMORY_MODE: Final = MEMORY_MODE_FULL
MIGRATED_MEMORY_MAX_CHARACTERS: Final = 64_000
MIN_MEMORY_MAX_TURNS: Final = 1
MAX_MEMORY_MAX_TURNS: Final = 50
MIN_MEMORY_MAX_CHARACTERS: Final = 2_000
MAX_MEMORY_MAX_CHARACTERS: Final = 100_000
MAX_MEMORY_SUMMARY_CHARACTERS: Final = 4_000
MAX_MEMORY_SUMMARY_SOURCE_CHARACTERS: Final = 60_000
MAX_MEMORY_SUMMARY_CACHE_ENTRIES: Final = 100
MIN_TOOL_CALLS: Final = 1
MAX_TOOL_CALLS: Final = 10
MIN_TOOL_TIME: Final = 10
MAX_TOOL_TIME: Final = 120
MAX_WEB_SEARCH_ACTIONS: Final = 10
MAX_ROOM_CONTEXT_ENTITIES: Final = 40

EVENT_CONVERSATION_FINISHED: Final = "chatgpt_oauth.conversation_finished"

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

MAX_HISTORY_ENTITY_IDS: Final = 5
MAX_HISTORY_DAYS: Final = 31
DEFAULT_HISTORY_HOURS: Final = 24
DEFAULT_HISTORY_POINTS: Final = 100
MAX_HISTORY_POINTS: Final = 200
MAX_STATISTIC_IDS: Final = 5
MAX_STATISTICS_DAYS: Final = 366
DEFAULT_STATISTICS_DAYS: Final = 7
DEFAULT_STATISTICS_POINTS: Final = 200
MAX_STATISTICS_POINTS: Final = 400
DEFAULT_ENERGY_DAYS: Final = 7
DEFAULT_ENERGY_POINTS: Final = 100
MAX_ENERGY_POINTS: Final = 200

# This key is assembled to prevent accidental copy/paste back into a request
# payload while still allowing migration and defensive validation.
LEGACY_OUTPUT_LIMIT_KEY: Final = "max_output_tokens"
