"""Tests for the pure entity-mapping helper (no Home Assistant required)."""

from custom_components.bilresa_remote.mapping import map_device_entities


def test_channel1_mapping():
    entities = [
        "event.bilresa_remote_button_3",
        "event.bilresa_remote_scroller_2",
        "event.bilresa_remote_scroller_1",
        "sensor.bilresa_remote_scroller_2",
        "sensor.bilresa_remote_scroller_1",
    ]
    mapped = map_device_entities(entities)
    assert mapped[(1, "button")] == "event.bilresa_remote_button_3"
    assert mapped[(1, "scroll_left")] == "event.bilresa_remote_scroller_2"
    assert mapped[(1, "scroll_right")] == "event.bilresa_remote_scroller_1"
    assert mapped[(1, "scroll_left_ext")] == "sensor.bilresa_remote_scroller_2"
    assert mapped[(1, "scroll_right_ext")] == "sensor.bilresa_remote_scroller_1"


def test_channel2_and_3_mapping():
    entities = [
        "event.bilresa_remote_button_6",
        "event.bilresa_remote_scroller_5",
        "event.bilresa_remote_scroller_4",
        "event.bilresa_remote_button_9",
        "event.bilresa_remote_scroller_8",
        "event.bilresa_remote_scroller_7",
    ]
    mapped = map_device_entities(entities)
    assert mapped[(2, "button")] == "event.bilresa_remote_button_6"
    assert mapped[(2, "scroll_left")] == "event.bilresa_remote_scroller_5"
    assert mapped[(2, "scroll_right")] == "event.bilresa_remote_scroller_4"
    assert mapped[(3, "button")] == "event.bilresa_remote_button_9"
    assert mapped[(3, "scroll_left")] == "event.bilresa_remote_scroller_8"
    assert mapped[(3, "scroll_right")] == "event.bilresa_remote_scroller_7"


def test_unrelated_entities_ignored():
    # Device filtering happens upstream (engine passes only the device's own
    # entities), so an unrelated event.*_3 entity still matches by design, same
    # as the original blueprint's regexes.
    mapped = map_device_entities(
        ["event.bilresa_remote_button", "sensor.bilresa_remote_scroller_3", "light.kitchen"]
    )
    assert mapped == {}
