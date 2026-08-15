"""Local, explicitly enabled instruction packs for conversation profiles."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
import os
from pathlib import Path
import re
import stat
import tomllib
from types import MappingProxyType
from typing import Final

from homeassistant.core import HomeAssistant, valid_entity_id

from .const import (
    CONF_ENABLED_LOCAL_SKILLS,
    DEFAULT_ENABLED_LOCAL_SKILLS,
    LOGGER,
    MAX_ENABLED_LOCAL_SKILLS,
)
from .web_search import (
    WEB_SEARCH_DISABLED,
    WEB_SEARCH_REQUIRED,
    WebSearchOptions,
)

__all__ = [
    "CONF_ENABLED_LOCAL_SKILLS",
    "DEFAULT_ENABLED_LOCAL_SKILLS",
    "MAX_ENABLED_LOCAL_SKILLS",
    "LocalSkillCatalog",
    "LocalSkillPack",
    "ResolvedLocalSkillPolicy",
    "apply_local_skill_web_search_policy",
    "async_load_local_skill_catalog",
    "compose_local_skill_instructions",
    "load_local_skill_catalog",
    "local_skills_path",
    "normalize_enabled_local_skill_ids",
    "resolve_local_skill_policy",
]

LOCAL_SKILLS_DIRECTORY: Final = ("openai_oauth_conversation", "skills")
LOCAL_SKILL_SCHEMA_VERSION: Final = 1
MAX_LOCAL_SKILL_FILES: Final = 32
MAX_LOCAL_SKILL_DIRECTORY_ENTRIES: Final = 256
MAX_LOCAL_SKILL_FILE_BYTES: Final = 64 * 1024
MAX_LOCAL_SKILL_TOTAL_BYTES: Final = 512 * 1024
MAX_LOCAL_SKILL_NAME_CHARACTERS: Final = 80
MAX_LOCAL_SKILL_DESCRIPTION_CHARACTERS: Final = 500
MAX_LOCAL_SKILL_INSTRUCTION_CHARACTERS: Final = 12_000
MAX_LOCAL_SKILL_OUTPUT_FORMAT_CHARACTERS: Final = 2_000
MAX_LOCAL_SKILL_ACTIVE_CHARACTERS: Final = 24_000
# Leave room inside the final limit for policy, voice, scope, and tool guidance.
MAX_LOCAL_SKILL_ACTIVE_PACK_CHARACTERS: Final = 22_000
MAX_LOCAL_SKILL_SUGGESTED_TOOLS: Final = 20
MAX_LOCAL_SKILL_MATCHED_TOOL_NAMES: Final = 20
MAX_LOCAL_SKILL_MATCHED_TOOL_CHARACTERS: Final = 768
MAX_LOCAL_SKILL_AVAILABLE_TOOL_NAMES: Final = 256
MAX_LOCAL_SKILL_TOOL_NAME_CHARACTERS: Final = 128
MAX_LOCAL_SKILL_ENTITIES: Final = 100
MAX_LOCAL_SKILL_AREAS: Final = 20
MAX_LOCAL_SKILL_AREA_NAME_CHARACTERS: Final = 120
MIN_LOCAL_SKILL_VOICE_WORDS: Final = 20
MAX_LOCAL_SKILL_VOICE_WORDS: Final = 500

WEB_POLICY_INHERIT: Final = "inherit"
WEB_POLICY_DISABLED: Final = "disabled"
WEB_POLICY_REQUIRED: Final = "required"
WEB_POLICIES: Final = frozenset(
    {WEB_POLICY_INHERIT, WEB_POLICY_DISABLED, WEB_POLICY_REQUIRED}
)

CONFIRMATION_INHERIT: Final = "inherit"
CONFIRMATION_SENSITIVE: Final = "sensitive"
CONFIRMATION_ALWAYS: Final = "always"
CONFIRMATION_POLICIES: Final = frozenset(
    {CONFIRMATION_INHERIT, CONFIRMATION_SENSITIVE, CONFIRMATION_ALWAYS}
)

TOOL_CATEGORY_HOME_ASSISTANT: Final = "home_assistant"
TOOL_CATEGORY_HISTORY: Final = "history"
TOOL_CATEGORY_CAMERA_ANALYSIS: Final = "camera_analysis"
TOOL_CATEGORY_IMAGE_GENERATION: Final = "image_generation"
TOOL_CATEGORY_AI_TASK: Final = "ai_task"
TOOL_CATEGORY_SELECTED_SCRIPTS: Final = "selected_scripts"
TOOL_CATEGORY_SCHEDULED_ACTIONS: Final = "scheduled_actions"
SUGGESTED_TOOL_CATEGORIES: Final = frozenset(
    {
        TOOL_CATEGORY_HOME_ASSISTANT,
        TOOL_CATEGORY_HISTORY,
        TOOL_CATEGORY_CAMERA_ANALYSIS,
        TOOL_CATEGORY_IMAGE_GENERATION,
        TOOL_CATEGORY_AI_TASK,
        TOOL_CATEGORY_SELECTED_SCRIPTS,
        TOOL_CATEGORY_SCHEDULED_ACTIONS,
    }
)

_SKILL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ALLOWED_KEYS = frozenset(
    {
        "schema_version",
        "name",
        "description",
        "instructions",
        "suggested_tools",
        "output_format",
        "web_search",
        "confirmation",
        "voice_max_words",
        "allowed_entities",
        "allowed_areas",
    }
)


@dataclass(frozen=True, slots=True)
class LocalSkillPack:
    """One validated local instruction pack."""

    skill_id: str
    name: str
    description: str
    instructions: str
    suggested_tools: tuple[str, ...]
    output_format: str | None
    web_search_policy: str
    confirmation_policy: str
    voice_max_words: int | None
    allowed_entities: tuple[str, ...]
    allowed_areas: tuple[str, ...]
    schema_version: int = LOCAL_SKILL_SCHEMA_VERSION

    @property
    def has_scope(self) -> bool:
        """Return whether the pack narrows entity or area access."""
        return bool(self.allowed_entities or self.allowed_areas)


@dataclass(frozen=True, slots=True)
class LocalSkillCatalog:
    """A bounded snapshot of locally available skill packs."""

    packs: Mapping[str, LocalSkillPack]
    invalid_file_count: int = 0
    ignored_entry_count: int = 0
    scanned_entry_count: int = 0
    root_available: bool = False

    @property
    def loaded_count(self) -> int:
        """Return the number of valid local skill packs."""
        return len(self.packs)

    def get(self, skill_id: str) -> LocalSkillPack | None:
        """Return one pack by its stable local identifier."""
        return self.packs.get(skill_id)

    def selection_options(self) -> list[dict[str, str]]:
        """Return stable, human-readable Home Assistant selector options."""
        return [
            {
                "value": pack.skill_id,
                "label": pack.name,
            }
            for pack in sorted(
                self.packs.values(),
                key=lambda item: (item.name.casefold(), item.skill_id),
            )
        ]


@dataclass(frozen=True, slots=True)
class ResolvedLocalSkillPolicy:
    """Combined behavior for the valid enabled packs on one profile."""

    packs: tuple[LocalSkillPack, ...] = ()
    missing_skill_ids: tuple[str, ...] = ()
    skipped_skill_ids: tuple[str, ...] = ()
    suggested_tools: tuple[str, ...] = ()
    web_search_policy: str = WEB_POLICY_INHERIT
    confirmation_policy: str = CONFIRMATION_INHERIT
    voice_max_words: int | None = None
    allowed_entities: tuple[str, ...] = ()
    allowed_areas: tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        """Return whether at least one enabled pack was usable."""
        return bool(self.packs)

    @property
    def has_scope(self) -> bool:
        """Return whether enabled packs define a hard narrowing scope."""
        return bool(self.allowed_entities or self.allowed_areas)


class LocalSkillValidationError(ValueError):
    """Raised when one local skill file is not valid."""


def local_skills_path(hass: HomeAssistant) -> Path:
    """Return the persistent user-managed local skill directory."""
    return Path(hass.config.path(*LOCAL_SKILLS_DIRECTORY))


async def async_load_local_skill_catalog(
    hass: HomeAssistant,
) -> LocalSkillCatalog:
    """Load local skills outside the event loop without following links."""
    return await hass.async_add_executor_job(
        load_local_skill_catalog,
        local_skills_path(hass),
    )


def load_local_skill_catalog(skills_path: str | os.PathLike[str]) -> LocalSkillCatalog:
    """Load a bounded catalog from direct-child TOML files only."""
    root = Path(skills_path)
    try:
        root_stat = root.lstat()
    except FileNotFoundError:
        return _catalog({})
    except OSError:
        return _catalog({}, invalid_file_count=1)

    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        return _catalog({}, invalid_file_count=1)

    candidates: list[tuple[str, Path]] = []
    invalid_count = 0
    ignored_count = 0
    scanned_count = 0
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                if scanned_count >= MAX_LOCAL_SKILL_DIRECTORY_ENTRIES:
                    ignored_count += 1
                    break
                scanned_count += 1
                if not entry.name.endswith(".toml"):
                    ignored_count += 1
                    continue
                skill_id = entry.name.removesuffix(".toml")
                if not _SKILL_ID_PATTERN.fullmatch(skill_id):
                    invalid_count += 1
                    continue
                try:
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        invalid_count += 1
                        continue
                except OSError:
                    invalid_count += 1
                    continue
                candidates.append((skill_id, root / entry.name))
    except OSError:
        return _catalog(
            {},
            invalid_file_count=invalid_count + 1,
            ignored_entry_count=ignored_count,
            scanned_entry_count=scanned_count,
            root_available=True,
        )

    candidates.sort()
    if len(candidates) > MAX_LOCAL_SKILL_FILES:
        invalid_count += len(candidates) - MAX_LOCAL_SKILL_FILES
        candidates = candidates[:MAX_LOCAL_SKILL_FILES]

    packs: dict[str, LocalSkillPack] = {}
    total_bytes = 0
    for skill_id, path in candidates:
        remaining_bytes = MAX_LOCAL_SKILL_TOTAL_BYTES - total_bytes
        if remaining_bytes <= 0:
            invalid_count += 1
            continue
        try:
            raw = _read_regular_file_without_links(
                path,
                maximum=min(MAX_LOCAL_SKILL_FILE_BYTES, remaining_bytes),
            )
            total_bytes += len(raw)
            pack = _parse_local_skill(skill_id, raw)
        except (
            LocalSkillValidationError,
            OSError,
            UnicodeError,
            tomllib.TOMLDecodeError,
        ):
            invalid_count += 1
            LOGGER.warning("Ignored invalid local skill pack %s", skill_id)
            continue
        packs[skill_id] = pack

    return _catalog(
        packs,
        invalid_file_count=invalid_count,
        ignored_entry_count=ignored_count,
        scanned_entry_count=scanned_count,
        root_available=True,
    )


def normalize_enabled_local_skill_ids(value: object) -> list[str]:
    """Return a unique, bounded list of syntactically valid skill IDs."""
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, (list, tuple, set, frozenset)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            continue
        skill_id = item.strip().lower()
        if not _SKILL_ID_PATTERN.fullmatch(skill_id) or skill_id in seen:
            continue
        seen.add(skill_id)
        result.append(skill_id)
        if len(result) >= MAX_ENABLED_LOCAL_SKILLS:
            break
    return result


def resolve_local_skill_policy(
    catalog: LocalSkillCatalog,
    enabled_skill_ids: object,
) -> ResolvedLocalSkillPolicy:
    """Resolve enabled packs and combine their restrictive behavior."""
    selected_ids = normalize_enabled_local_skill_ids(enabled_skill_ids)
    valid_packs: list[LocalSkillPack] = []
    instruction_packs: list[LocalSkillPack] = []
    missing: list[str] = []
    skipped: list[str] = []
    active_characters = 0

    for skill_id in selected_ids:
        if (pack := catalog.get(skill_id)) is None:
            missing.append(skill_id)
            continue
        valid_packs.append(pack)
        pack_characters = _pack_instruction_size(pack)
        if active_characters + pack_characters > MAX_LOCAL_SKILL_ACTIVE_PACK_CHARACTERS:
            skipped.append(skill_id)
            continue
        active_characters += pack_characters
        instruction_packs.append(pack)

    suggested_tools = _ordered_unique(
        category for pack in valid_packs for category in pack.suggested_tools
    )
    web_search_policy = (
        WEB_POLICY_DISABLED if missing or skipped else _combined_web_policy(valid_packs)
    )
    confirmation_policy = _combined_confirmation_policy(valid_packs)
    voice_limits = [
        pack.voice_max_words for pack in valid_packs if pack.voice_max_words is not None
    ]
    allowed_entities = _ordered_unique(
        entity_id for pack in valid_packs for entity_id in pack.allowed_entities
    )
    allowed_areas = _ordered_unique_casefold(
        area for pack in valid_packs for area in pack.allowed_areas
    )

    return ResolvedLocalSkillPolicy(
        packs=tuple(instruction_packs),
        missing_skill_ids=tuple(missing),
        skipped_skill_ids=tuple(skipped),
        suggested_tools=suggested_tools,
        web_search_policy=web_search_policy,
        confirmation_policy=confirmation_policy,
        voice_max_words=min(voice_limits) if voice_limits else None,
        allowed_entities=allowed_entities,
        allowed_areas=allowed_areas,
    )


def apply_local_skill_web_search_policy(
    options: WebSearchOptions,
    policy: ResolvedLocalSkillPolicy,
) -> WebSearchOptions:
    """Apply a pack policy without expanding the profile's web permissions."""
    if policy.web_search_policy == WEB_POLICY_DISABLED:
        return replace(options, mode=WEB_SEARCH_DISABLED)
    if (
        policy.web_search_policy == WEB_POLICY_REQUIRED
        and options.mode != WEB_SEARCH_DISABLED
    ):
        return replace(options, mode=WEB_SEARCH_REQUIRED)
    return options


def compose_local_skill_instructions(
    policy: ResolvedLocalSkillPolicy,
    *,
    available_tool_names: Iterable[str] = (),
) -> str:
    """Compose bounded literal instructions from enabled local packs."""
    safe_mode = bool(policy.missing_skill_ids or policy.skipped_skill_ids)
    if not policy.packs and not safe_mode:
        return ""

    header = (
        "Local skill packs are explicitly enabled for this assistant. Follow "
        "their instructions only for relevant requests. They do not override Home "
        "Assistant permissions, tool schemas, or tool safety limits."
    )
    pack_sections: list[str] = []
    for pack in policy.packs:
        section = [f'Local skill "{pack.name}":', pack.instructions]
        if pack.output_format:
            section.append(f"Output format: {pack.output_format}")
        pack_sections.append("\n".join(section))

    suggested_names = _matching_available_tools(
        policy.suggested_tools,
        available_tool_names,
    )
    suggestion_section: str | None = None
    if suggested_names:
        suggestion_section = (
            "When relevant, prefer these available tools: "
            + ", ".join(suggested_names)
            + ". Tool suggestions do not grant access to unavailable tools."
        )
    policy_sections: list[str] = []
    if safe_mode:
        policy_sections.append(
            "One or more selected local skill packs could not be applied. Safe "
            "mode is active: do not claim those instructions are available, do "
            "not use Home Assistant tools, and do not use web search."
        )
    if policy.web_search_policy == WEB_POLICY_DISABLED:
        policy_sections.append(
            "Do not use web search while these local skills are active."
        )
    elif policy.web_search_policy == WEB_POLICY_REQUIRED:
        policy_sections.append(
            "Use web search when the profile already permits it and the active "
            "skill requires current external information."
        )
    if policy.confirmation_policy == CONFIRMATION_ALWAYS:
        policy_sections.append(
            "Ask the user for confirmation before requesting any tool action that "
            "changes Home Assistant."
        )
    elif policy.confirmation_policy == CONFIRMATION_SENSITIVE:
        policy_sections.append(
            "Ask the user for confirmation before requesting a sensitive action "
            "involving security, access, alarms, locks, doors, or safety equipment."
        )
    if policy.voice_max_words is not None:
        policy_sections.append(
            "Keep the spoken answer to approximately "
            f"{policy.voice_max_words} words or fewer unless safety or correctness "
            "requires a longer response."
        )
    if policy.has_scope:
        policy_sections.append(
            "Stay within the locally configured entity and area scope. Do not ask "
            "for unrelated household data or attempt to work around that boundary."
        )

    # Policy guidance is mandatory. Tool suggestions are optional, and pack prose is
    # removed only as a whole if a future schema change exceeds the fixed envelope.
    # Restrictive policy metadata from such a pack remains active in ``policy``.
    while True:
        sections = [header, *pack_sections]
        if suggestion_section is not None:
            sections.append(suggestion_section)
        sections.extend(policy_sections)
        result = "\n\n".join(sections).strip()
        if len(result) <= MAX_LOCAL_SKILL_ACTIVE_CHARACTERS:
            return result
        if suggestion_section is not None:
            suggestion_section = None
            continue
        if pack_sections:
            pack_sections.pop()
            continue
        # Every policy field is independently bounded, so this is defensive only.
        raise LocalSkillValidationError("Combined local skill policy is too large")


def _catalog(
    packs: Mapping[str, LocalSkillPack],
    *,
    invalid_file_count: int = 0,
    ignored_entry_count: int = 0,
    scanned_entry_count: int = 0,
    root_available: bool = False,
) -> LocalSkillCatalog:
    return LocalSkillCatalog(
        packs=MappingProxyType(dict(packs)),
        invalid_file_count=invalid_file_count,
        ignored_entry_count=ignored_entry_count,
        scanned_entry_count=scanned_entry_count,
        root_available=root_available,
    )


def _read_regular_file_without_links(path: Path, *, maximum: int) -> bytes:
    """Read one regular file by descriptor and reject link races."""
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode):
            raise LocalSkillValidationError("Local skill is not a regular file")
        if file_stat.st_size > maximum:
            raise LocalSkillValidationError("Local skill file is too large")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > maximum:
            raise LocalSkillValidationError("Local skill file is too large")
        return data
    finally:
        os.close(descriptor)


def _parse_local_skill(skill_id: str, raw: bytes) -> LocalSkillPack:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as err:
        raise LocalSkillValidationError("Local skill must use UTF-8") from err
    data = tomllib.loads(text)
    if not isinstance(data, dict):
        raise LocalSkillValidationError("Local skill must be a TOML table")
    unknown_keys = set(data).difference(_ALLOWED_KEYS)
    if unknown_keys:
        raise LocalSkillValidationError("Local skill contains unsupported keys")
    if _strict_integer(data.get("schema_version")) != LOCAL_SKILL_SCHEMA_VERSION:
        raise LocalSkillValidationError("Unsupported local skill schema version")

    name = _required_text(
        data.get("name"),
        label="name",
        maximum=MAX_LOCAL_SKILL_NAME_CHARACTERS,
        multiline=False,
    )
    description = _optional_text(
        data.get("description"),
        label="description",
        maximum=MAX_LOCAL_SKILL_DESCRIPTION_CHARACTERS,
        multiline=True,
    )
    instructions = _required_text(
        data.get("instructions"),
        label="instructions",
        maximum=MAX_LOCAL_SKILL_INSTRUCTION_CHARACTERS,
        multiline=True,
    )
    suggested_tools = _string_choices(
        data.get("suggested_tools", []),
        label="suggested_tools",
        choices=SUGGESTED_TOOL_CATEGORIES,
        maximum=MAX_LOCAL_SKILL_SUGGESTED_TOOLS,
    )
    output_format = _optional_text(
        data.get("output_format"),
        label="output_format",
        maximum=MAX_LOCAL_SKILL_OUTPUT_FORMAT_CHARACTERS,
        multiline=True,
        none_if_missing=True,
    )
    web_search_policy = _choice(
        data.get("web_search", WEB_POLICY_INHERIT),
        label="web_search",
        choices=WEB_POLICIES,
    )
    confirmation_policy = _choice(
        data.get("confirmation", CONFIRMATION_INHERIT),
        label="confirmation",
        choices=CONFIRMATION_POLICIES,
    )
    voice_max_words = _optional_bounded_integer(
        data.get("voice_max_words"),
        label="voice_max_words",
        minimum=MIN_LOCAL_SKILL_VOICE_WORDS,
        maximum=MAX_LOCAL_SKILL_VOICE_WORDS,
    )
    allowed_entities = _entity_ids(data.get("allowed_entities", []))
    allowed_areas = _area_names(data.get("allowed_areas", []))

    return LocalSkillPack(
        skill_id=skill_id,
        name=name,
        description=description,
        instructions=instructions,
        suggested_tools=suggested_tools,
        output_format=output_format,
        web_search_policy=web_search_policy,
        confirmation_policy=confirmation_policy,
        voice_max_words=voice_max_words,
        allowed_entities=allowed_entities,
        allowed_areas=allowed_areas,
    )


def _strict_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _required_text(
    value: object,
    *,
    label: str,
    maximum: int,
    multiline: bool,
) -> str:
    result = _checked_text(
        value,
        label=label,
        maximum=maximum,
        multiline=multiline,
    )
    if not result:
        raise LocalSkillValidationError(f"{label} cannot be empty")
    return result


def _optional_text(
    value: object,
    *,
    label: str,
    maximum: int,
    multiline: bool,
    none_if_missing: bool = False,
) -> str | None:
    if value is None:
        return None if none_if_missing else ""
    result = _checked_text(
        value,
        label=label,
        maximum=maximum,
        multiline=multiline,
    )
    return result or (None if none_if_missing else "")


def _checked_text(
    value: object,
    *,
    label: str,
    maximum: int,
    multiline: bool,
) -> str:
    if not isinstance(value, str):
        raise LocalSkillValidationError(f"{label} must be text")
    result = value.strip()
    if len(result) > maximum:
        raise LocalSkillValidationError(f"{label} is too long")
    if not multiline and any(character in result for character in "\r\n"):
        raise LocalSkillValidationError(f"{label} must be one line")
    if any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"}
        for character in result
    ):
        raise LocalSkillValidationError(f"{label} contains control characters")
    return result


def _choice(value: object, *, label: str, choices: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise LocalSkillValidationError(f"{label} has an unsupported value")
    return value


def _string_choices(
    value: object,
    *,
    label: str,
    choices: frozenset[str],
    maximum: int,
) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > maximum:
        raise LocalSkillValidationError(f"{label} must be a bounded list")
    result: list[str] = []
    for item in value:
        choice = _choice(item, label=label, choices=choices)
        if choice not in result:
            result.append(choice)
    return tuple(result)


def _optional_bounded_integer(
    value: object,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int | None:
    if value is None:
        return None
    result = _strict_integer(value)
    if result is None or not minimum <= result <= maximum:
        raise LocalSkillValidationError(f"{label} is outside its supported range")
    return result


def _entity_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_LOCAL_SKILL_ENTITIES:
        raise LocalSkillValidationError("allowed_entities must be a bounded list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise LocalSkillValidationError("allowed_entities must contain text")
        entity_id = item.strip().lower()
        if not valid_entity_id(entity_id):
            raise LocalSkillValidationError("allowed_entities contains an invalid ID")
        if entity_id not in result:
            result.append(entity_id)
    return tuple(result)


def _area_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_LOCAL_SKILL_AREAS:
        raise LocalSkillValidationError("allowed_areas must be a bounded list")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        area = _required_text(
            item,
            label="allowed_areas",
            maximum=MAX_LOCAL_SKILL_AREA_NAME_CHARACTERS,
            multiline=False,
        )
        folded = area.casefold()
        if folded not in seen:
            seen.add(folded)
            result.append(area)
    return tuple(result)


def _pack_instruction_size(pack: LocalSkillPack) -> int:
    return len(pack.name) + len(pack.instructions) + len(pack.output_format or "") + 64


def _combined_web_policy(packs: Sequence[LocalSkillPack]) -> str:
    policies = {pack.web_search_policy for pack in packs}
    if WEB_POLICY_DISABLED in policies:
        return WEB_POLICY_DISABLED
    if WEB_POLICY_REQUIRED in policies:
        return WEB_POLICY_REQUIRED
    return WEB_POLICY_INHERIT


def _combined_confirmation_policy(packs: Sequence[LocalSkillPack]) -> str:
    policies = {pack.confirmation_policy for pack in packs}
    if CONFIRMATION_ALWAYS in policies:
        return CONFIRMATION_ALWAYS
    if CONFIRMATION_SENSITIVE in policies:
        return CONFIRMATION_SENSITIVE
    return CONFIRMATION_INHERIT


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)


def _ordered_unique_casefold(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        folded = value.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        result.append(value)
    return tuple(result)


def _matching_available_tools(
    categories: Sequence[str],
    available_tool_names: Iterable[str],
) -> tuple[str, ...]:
    tools: list[str] = []
    seen_tools: set[str] = set()
    for raw_name in available_tool_names:
        if len(tools) >= MAX_LOCAL_SKILL_AVAILABLE_TOOL_NAMES:
            break
        if not raw_name:
            continue
        tool_name = str(raw_name)
        if (
            len(tool_name) > MAX_LOCAL_SKILL_TOOL_NAME_CHARACTERS
            or tool_name in seen_tools
        ):
            continue
        seen_tools.add(tool_name)
        tools.append(tool_name)

    result: list[str] = []
    result_characters = 0
    for category in categories:
        for tool_name in tools:
            base_name = tool_name.rsplit("__", 1)[-1]
            if _tool_matches_category(base_name, category) and tool_name not in result:
                separator_characters = 2 if result else 0
                if (
                    len(result) >= MAX_LOCAL_SKILL_MATCHED_TOOL_NAMES
                    or result_characters + separator_characters + len(tool_name)
                    > MAX_LOCAL_SKILL_MATCHED_TOOL_CHARACTERS
                ):
                    return tuple(result)
                result.append(tool_name)
                result_characters += separator_characters + len(tool_name)
    return tuple(result)


def _tool_matches_category(tool_name: str, category: str) -> bool:
    if category == TOOL_CATEGORY_HOME_ASSISTANT:
        return tool_name.startswith("Hass") or tool_name in {
            "GetLiveContext",
            "GetDateTime",
            "calendar_get_events",
            "todo_get_items",
        }
    if category == TOOL_CATEGORY_HISTORY:
        return tool_name in {
            "GetEntityHistory",
            "GetEntityStatistics",
            "GetEnergySummary",
        }
    if category == TOOL_CATEGORY_CAMERA_ANALYSIS:
        return tool_name == "AnalyzeCamera"
    if category == TOOL_CATEGORY_IMAGE_GENERATION:
        return tool_name == "GenerateImage"
    if category == TOOL_CATEGORY_AI_TASK:
        return tool_name == "RunAITask"
    if category == TOOL_CATEGORY_SELECTED_SCRIPTS:
        return tool_name.startswith("selected_script_")
    if category == TOOL_CATEGORY_SCHEDULED_ACTIONS:
        return (
            tool_name.startswith("Schedule")
            or tool_name
            in {
                "ListScheduledActions",
                "CancelScheduledAction",
                "ConfirmScheduledAction",
            }
            or tool_name.startswith("scheduled_action_")
        )
    return False
