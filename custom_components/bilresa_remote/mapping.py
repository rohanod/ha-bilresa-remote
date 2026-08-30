"""Pure helpers mapping BILRESA device entities to channels and roles.

No Home Assistant imports so this stays unit-testable without a HA install.

Entity numbering follows the original blueprint:
  channel 1: button _3, scroll-left _2, scroll-right _1
  channel 2: button _6, scroll-left _5, scroll-right _4
  channel 3: button _9, scroll-left _8, scroll-right _7
Event entities expose button presses and relaxed scroll events;
sensor entities (hidden by default) are used for instant scroll evaluation.
"""

from __future__ import annotations

import re

Role = str
Key = tuple[int, Role]

_EVENT_SUFFIX: dict[Role, tuple[int, int, int]] = {
    "button": (3, 6, 9),
    "scroll_left": (2, 5, 8),
    "scroll_right": (1, 4, 7),
}
_SENSOR_SUFFIX: dict[Role, tuple[int, int, int]] = {
    "scroll_left_ext": (2, 5, 8),
    "scroll_right_ext": (1, 4, 7),
}


def _build_patterns() -> tuple[tuple[Key, re.Pattern[str]], ...]:
    patterns: list[tuple[Key, re.Pattern[str]]] = []
    for role, suffixes in _EVENT_SUFFIX.items():
        for ch, suffix in enumerate(suffixes, start=1):
            patterns.append(((ch, role), re.compile(rf"event\..+[a-zA-Z]_{suffix}")))
    for role, suffixes in _SENSOR_SUFFIX.items():
        for ch, suffix in enumerate(suffixes, start=1):
            patterns.append(((ch, role), re.compile(rf"sensor\..+[a-zA-Z]_{suffix}")))
    return tuple(patterns)


_PATTERNS = _build_patterns()


def map_device_entities(entity_ids: list[str]) -> dict[Key, str]:
    """Map entity ids of a BILRESA device to (channel, role) keys."""
    result: dict[Key, str] = {}
    for entity_id in sorted(entity_ids):
        for key, pattern in _PATTERNS:
            if key not in result and pattern.fullmatch(entity_id):
                result[key] = entity_id
    return result
