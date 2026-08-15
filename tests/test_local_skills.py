"""Tests for local, explicitly enabled conversation skill packs."""

from __future__ import annotations

from pathlib import Path

import pytest

from custom_components.openai_oauth_conversation.local_skills import (
    CONFIRMATION_ALWAYS,
    LOCAL_SKILL_SCHEMA_VERSION,
    MAX_ENABLED_LOCAL_SKILLS,
    MAX_LOCAL_SKILL_ACTIVE_CHARACTERS,
    MAX_LOCAL_SKILL_FILE_BYTES,
    WEB_POLICY_DISABLED,
    LocalSkillCatalog,
    LocalSkillPack,
    ResolvedLocalSkillPolicy,
    apply_local_skill_web_search_policy,
    async_load_local_skill_catalog,
    compose_local_skill_instructions,
    load_local_skill_catalog,
    normalize_enabled_local_skill_ids,
    resolve_local_skill_policy,
)
from custom_components.openai_oauth_conversation.web_search import (
    WEB_SEARCH_AUTO,
    WEB_SEARCH_DISABLED,
    WEB_SEARCH_REQUIRED,
    WebSearchOptions,
)


def _write_skill(directory: Path, skill_id: str, content: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{skill_id}.toml"
    path.write_text(content, encoding="utf-8")
    return path


def _minimal_skill(
    *,
    name: str = "Energy Analyst",
    instructions: str = "Explain measured energy use clearly.",
    extra: str = "",
) -> str:
    return f'''schema_version = 1
name = "{name}"
instructions = "{instructions}"
{extra}
'''


def test_loads_a_complete_toml_skill_pack(tmp_path: Path) -> None:
    """All supported declarative fields are parsed without executable content."""
    skills_path = tmp_path / "openai_oauth_conversation" / "skills"
    _write_skill(
        skills_path,
        "energy_analyst",
        '''schema_version = 1
name = "Energy Analyst"
description = "Explains measured household energy use"
instructions = """Compare recent measurements with earlier periods.
Never present an estimate as a measured fact."""
suggested_tools = ["history", "home_assistant"]
output_format = "Lead with the finding, then list supporting measurements."
web_search = "disabled"
confirmation = "sensitive"
voice_max_words = 80
allowed_entities = ["sensor.house_energy", "sensor.solar_power"]
allowed_areas = ["Utility Room", "Kitchen"]
''',
    )

    catalog = load_local_skill_catalog(skills_path)

    assert catalog.root_available is True
    assert catalog.loaded_count == 1
    assert catalog.invalid_file_count == 0
    pack = catalog.get("energy_analyst")
    assert pack is not None
    assert pack.schema_version == LOCAL_SKILL_SCHEMA_VERSION
    assert pack.name == "Energy Analyst"
    assert pack.suggested_tools == ("history", "home_assistant")
    assert pack.output_format == (
        "Lead with the finding, then list supporting measurements."
    )
    assert pack.allowed_entities == (
        "sensor.house_energy",
        "sensor.solar_power",
    )
    assert pack.allowed_areas == ("Utility Room", "Kitchen")
    assert catalog.selection_options() == [
        {"value": "energy_analyst", "label": "Energy Analyst"}
    ]


def test_loader_uses_direct_regular_toml_files_only(tmp_path: Path) -> None:
    """Nested files, unrelated files, and links cannot become skill packs."""
    skills_path = tmp_path / "skills"
    _write_skill(skills_path, "valid", _minimal_skill())
    (skills_path / "README.md").write_text("not a skill", encoding="utf-8")
    _write_skill(skills_path / "nested", "nested", _minimal_skill())
    external = _write_skill(tmp_path / "external", "linked", _minimal_skill())
    (skills_path / "linked.toml").symlink_to(external)

    catalog = load_local_skill_catalog(skills_path)

    assert set(catalog.packs) == {"valid"}
    assert catalog.invalid_file_count == 1
    assert catalog.ignored_entry_count == 2


def test_loader_rejects_a_symlinked_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    _write_skill(real_root, "valid", _minimal_skill())
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    catalog = load_local_skill_catalog(linked_root)

    assert catalog.loaded_count == 0
    assert catalog.root_available is False
    assert catalog.invalid_file_count == 1


@pytest.mark.parametrize(
    "content",
    [
        _minimal_skill(extra='unknown_key = "typo"'),
        _minimal_skill(extra='suggested_tools = ["arbitrary_service"]'),
        _minimal_skill(extra='allowed_entities = ["not-an-entity"]'),
        """schema_version = 1
name = "Unsafe include"
instructions = !include secrets.yaml
""",
        """schema_version = 1
name = "Unsafe environment"
instructions = !env_var HOME
""",
        """schema_version = 1
name = "Unsafe secret"
instructions = !secret oauth_token
""",
        """schema_version = 2
name = "Future"
instructions = "Unsupported schema"
""",
    ],
)
def test_invalid_or_nondeclarative_files_fail_closed(
    tmp_path: Path,
    content: str,
) -> None:
    skills_path = tmp_path / "skills"
    _write_skill(skills_path, "invalid", content)

    catalog = load_local_skill_catalog(skills_path)

    assert catalog.loaded_count == 0
    assert catalog.invalid_file_count == 1


def test_loader_rejects_oversized_files(tmp_path: Path) -> None:
    skills_path = tmp_path / "skills"
    content = _minimal_skill(instructions="x" * MAX_LOCAL_SKILL_FILE_BYTES)
    _write_skill(skills_path, "too_large", content)

    catalog = load_local_skill_catalog(skills_path)

    assert catalog.loaded_count == 0
    assert catalog.invalid_file_count == 1


def test_jinja_looking_text_remains_literal(tmp_path: Path) -> None:
    """The loader never evaluates templates, includes, secrets, or environment data."""
    skills_path = tmp_path / "skills"
    _write_skill(
        skills_path,
        "literal",
        _minimal_skill(instructions="Keep {{ states('sensor.private') }} literal."),
    )

    catalog = load_local_skill_catalog(skills_path)
    policy = resolve_local_skill_policy(catalog, ["literal"])
    instructions = compose_local_skill_instructions(policy)

    assert "{{ states('sensor.private') }}" in instructions


def test_policy_composition_is_deterministic_and_restrictive(tmp_path: Path) -> None:
    skills_path = tmp_path / "skills"
    _write_skill(
        skills_path,
        "camera",
        _minimal_skill(
            name="Camera Analyst",
            instructions="Analyze only current snapshots.",
            extra="""suggested_tools = ["camera_analysis", "history"]
web_search = "required"
confirmation = "sensitive"
voice_max_words = 120
allowed_entities = ["camera.kitchen"]
allowed_areas = ["Kitchen"]""",
        ),
    )
    _write_skill(
        skills_path,
        "private",
        _minimal_skill(
            name="Private Mode",
            instructions="Keep the answer local.",
            extra="""suggested_tools = ["history"]
web_search = "disabled"
confirmation = "always"
voice_max_words = 60
allowed_entities = ["sensor.kitchen_temperature"]
allowed_areas = ["kitchen", "Bedroom"]""",
        ),
    )

    policy = resolve_local_skill_policy(
        load_local_skill_catalog(skills_path),
        ["camera", "missing", "private"],
    )

    assert [pack.skill_id for pack in policy.packs] == ["camera", "private"]
    assert policy.missing_skill_ids == ("missing",)
    assert policy.suggested_tools == ("camera_analysis", "history")
    assert policy.web_search_policy == WEB_POLICY_DISABLED
    assert policy.confirmation_policy == CONFIRMATION_ALWAYS
    assert policy.voice_max_words == 60
    assert policy.allowed_entities == (
        "camera.kitchen",
        "sensor.kitchen_temperature",
    )
    assert policy.allowed_areas == ("Kitchen", "Bedroom")
    assert policy.has_scope is True


def test_web_policy_never_expands_profile_permissions(tmp_path: Path) -> None:
    skills_path = tmp_path / "skills"
    _write_skill(
        skills_path,
        "requires_search",
        _minimal_skill(extra='web_search = "required"'),
    )
    required = resolve_local_skill_policy(
        load_local_skill_catalog(skills_path),
        ["requires_search"],
    )

    disabled_options = WebSearchOptions(
        mode=WEB_SEARCH_DISABLED,
        live_access=False,
        use_home_assistant_precise_location=False,
    )
    assert (
        apply_local_skill_web_search_policy(disabled_options, required)
        == disabled_options
    )

    automatic_options = WebSearchOptions(
        mode=WEB_SEARCH_AUTO,
        live_access=False,
        use_home_assistant_precise_location=False,
    )
    tightened = apply_local_skill_web_search_policy(automatic_options, required)
    assert tightened.mode == WEB_SEARCH_REQUIRED
    assert tightened.live_access is False
    assert tightened.use_home_assistant_precise_location is False


def test_disabled_web_policy_overrides_required(tmp_path: Path) -> None:
    skills_path = tmp_path / "skills"
    _write_skill(
        skills_path,
        "disabled",
        _minimal_skill(extra='web_search = "disabled"'),
    )
    policy = resolve_local_skill_policy(
        load_local_skill_catalog(skills_path),
        ["disabled"],
    )

    result = apply_local_skill_web_search_policy(
        WebSearchOptions(mode=WEB_SEARCH_REQUIRED),
        policy,
    )

    assert result.mode == WEB_SEARCH_DISABLED


def test_missing_enabled_skill_forces_conservative_web_policy() -> None:
    """An unavailable selected pack cannot restore the profile's web policy."""
    policy = resolve_local_skill_policy(LocalSkillCatalog(packs={}), ["missing"])

    assert policy.missing_skill_ids == ("missing",)
    assert policy.web_search_policy == WEB_POLICY_DISABLED
    effective = apply_local_skill_web_search_policy(
        WebSearchOptions(mode=WEB_SEARCH_AUTO),
        policy,
    )
    assert effective.mode == WEB_SEARCH_DISABLED
    instructions = compose_local_skill_instructions(policy)
    assert "Safe mode is active" in instructions
    assert "do not use Home Assistant tools" in instructions
    assert "do not use web search" in instructions
    assert "missing" not in instructions


def test_composed_instructions_name_only_available_suggested_tools(
    tmp_path: Path,
) -> None:
    skills_path = tmp_path / "skills"
    _write_skill(
        skills_path,
        "media",
        _minimal_skill(
            name="Media Helper",
            extra="""suggested_tools = ["camera_analysis", "image_generation"]
output_format = "One sentence followed by the image."
voice_max_words = 50""",
        ),
    )
    policy = resolve_local_skill_policy(
        load_local_skill_catalog(skills_path),
        ["media"],
    )

    instructions = compose_local_skill_instructions(
        policy,
        available_tool_names=(
            "ChatGPT_OAuth_AI_Task__AnalyzeCamera",
            "UnrelatedTool",
        ),
    )

    assert "ChatGPT_OAuth_AI_Task__AnalyzeCamera" in instructions
    assert "GenerateImage" not in instructions
    assert "UnrelatedTool" not in instructions
    assert "One sentence followed by the image." in instructions
    assert "50 words or fewer" in instructions


def test_enabled_ids_are_normalized_and_bounded() -> None:
    raw = [" VALID ", "valid", "../unsafe", 42] + [
        f"skill_{index}" for index in range(20)
    ]

    result = normalize_enabled_local_skill_ids(raw)

    assert result[0] == "valid"
    assert len(result) == MAX_ENABLED_LOCAL_SKILLS
    assert "../unsafe" not in result


def test_aggregate_instruction_budget_skips_whole_packs() -> None:
    def pack(skill_id: str) -> LocalSkillPack:
        restrictive = skill_id == "two"
        return LocalSkillPack(
            skill_id=skill_id,
            name=skill_id,
            description="",
            instructions="x" * 12_000,
            suggested_tools=("scheduled_actions",) if restrictive else (),
            output_format=None,
            web_search_policy="disabled" if restrictive else "inherit",
            confirmation_policy="always" if restrictive else "inherit",
            voice_max_words=40 if restrictive else None,
            allowed_entities=("sensor.restricted",) if restrictive else (),
            allowed_areas=("Private Room",) if restrictive else (),
        )

    catalog = LocalSkillCatalog(packs={"one": pack("one"), "two": pack("two")})

    policy = resolve_local_skill_policy(catalog, ["one", "two"])

    assert [item.skill_id for item in policy.packs] == ["one"]
    assert policy.skipped_skill_ids == ("two",)
    assert policy.web_search_policy == "disabled"
    assert policy.confirmation_policy == "always"
    assert policy.voice_max_words == 40
    assert policy.suggested_tools == ("scheduled_actions",)
    assert policy.allowed_entities == ("sensor.restricted",)
    assert policy.allowed_areas == ("Private Room",)


def test_composition_keeps_whole_packs_and_trailing_policy_guidance() -> None:
    """Bounded tool suggestions cannot truncate pack or safety sections."""

    def pack(skill_id: str, character: str, size: int) -> LocalSkillPack:
        marker = f"-{skill_id}-end"
        return LocalSkillPack(
            skill_id=skill_id,
            name=skill_id.title(),
            description="",
            instructions=character * (size - len(marker)) + marker,
            suggested_tools=("home_assistant",),
            output_format=None,
            web_search_policy="disabled",
            confirmation_policy="always",
            voice_max_words=50,
            allowed_entities=("sensor.restricted",),
            allowed_areas=(),
        )

    policy = ResolvedLocalSkillPolicy(
        packs=(pack("first", "a", 12_000), pack("second", "b", 9_000)),
        suggested_tools=("home_assistant",),
        web_search_policy="disabled",
        confirmation_policy="always",
        voice_max_words=50,
        allowed_entities=("sensor.restricted",),
    )
    available_tools = tuple(
        f"Assist__HassTool{index:03d}_{'x' * 40}" for index in range(100)
    )

    instructions = compose_local_skill_instructions(
        policy,
        available_tool_names=available_tools,
    )

    assert len(instructions) <= MAX_LOCAL_SKILL_ACTIVE_CHARACTERS
    assert "-first-end" in instructions
    assert "-second-end" in instructions
    assert "Do not use web search" in instructions
    assert "Ask the user for confirmation" in instructions
    assert "50 words or fewer" in instructions
    assert instructions.endswith(
        "Do not ask for unrelated household data or attempt to work around that "
        "boundary."
    )
    assert sum(tool_name in instructions for tool_name in available_tools) <= 20


def test_scheduled_action_suggestion_includes_management_tools() -> None:
    pack = LocalSkillPack(
        skill_id="scheduler",
        name="Scheduler",
        description="",
        instructions="Manage scheduled work.",
        suggested_tools=("scheduled_actions",),
        output_format=None,
        web_search_policy="inherit",
        confirmation_policy="inherit",
        voice_max_words=None,
        allowed_entities=(),
        allowed_areas=(),
    )
    tools = (
        "ScheduleReminder",
        "ScheduleHassTurnOn",
        "ScheduleHassTurnOff",
        "ListScheduledActions",
        "CancelScheduledAction",
        "ConfirmScheduledAction",
    )

    instructions = compose_local_skill_instructions(
        ResolvedLocalSkillPolicy(
            packs=(pack,),
            suggested_tools=("scheduled_actions",),
        ),
        available_tool_names=tools,
    )

    assert all(tool_name in instructions for tool_name in tools)


async def test_async_loader_uses_the_home_assistant_config_directory(hass) -> None:
    skills_path = Path(hass.config.config_dir) / "openai_oauth_conversation" / "skills"
    _write_skill(skills_path, "local", _minimal_skill())

    catalog = await async_load_local_skill_catalog(hass)

    assert catalog.get("local") is not None
