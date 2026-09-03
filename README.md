# Bilresa Remote for Home Assistant

Custom Home Assistant integration for the **IKEA BILRESA scroll wheel remote** (Matter). It is a native port of the popular [Ikea_bilresa_scroll_wheel blueprint](https://gist.github.com/jhol-byte/b2731a4d2476f530d76b9ff409f7f3a4) by [@jhol-byte](https://gist.github.com/jhol-byte) ([community thread](https://community.home-assistant.io/t/ikea-bilresa-scroll-wheel-blueprint-matter/965365)) — no YAML, no blueprint import, and no external helper scripts required.

## Features

- **3 channels**, selected with the channel switch on the remote.
- **Button actions** per channel: click, double-click, triple-click, long-click, and a repeatable on-hold action (full automation actions editor in the UI).
- **Scroll wheel modes** per channel:
  - `lights: dim` — brightness stepping with minimum limit
  - `lights: on/off` — toggle lights on/off
  - `lights: color temp and color hue` / `temp only` / `hue only` — built into the integration (the blueprint's external helper scripts are reimplemented natively, clamped to each light's supported range)
  - `media: volume control` — for media players
  - `fan: speed control` — percentage-based fan stepping, turns fan on/off at the ends
  - `dynamic: choose from input_select` — switch scroll mode at runtime via an `input_select`
  - `user defined` — run your own actions with `scroll_clicks` and `scroll_direction` variables
- **Relaxed** (one action after scrolling) and **instant** (continuous actions while scrolling) evaluation per channel.
- **Copy channel configuration**: move a full channel setup (actions, targets, modes) to another channel with a single dropdown selection.
- Queued event handling like the blueprint (`mode: queued` with configurable max, silent overflow).

## Installation

### HACS (recommended)

1. Make sure [HACS](https://hacs.xyz) is installed.
2. Add this repository as a custom repository: **HACS → ⋮ → Custom repositories →** `https://github.com/rohanod/ha-bilresa-remote` (category *Integration*).
3. Install **Bilresa Remote** from HACS and restart Home Assistant.

### Manual

Copy `custom_components/bilresa_remote/` into the `custom_components/` folder of your Home Assistant configuration and restart.

## Configuration

1. **Settings → Devices & Services → Add Integration → Bilresa Remote**, then pick your BILRESA remote device. That's the whole setup — everything else is optional.
2. Open **Configure** on the integration entry. The options are menu-driven, one small page per area:
   - **Light / Media player / Fan / Miscellaneous settings** — steps and limits, applied to all channels.
   - **Channels** — each channel has two collapsible groups: *Button actions* (click/double/triple/long-press/hold) and *Scroll wheel* (mode, target entities, evaluation mode, user-defined action). Defaults work out of the box for dimming lights.
   - **Copy channel configuration** — pick e.g. `1 → 2 & 3` to clone a channel's full config (actions, targets, modes) onto other channels. The source channel is left unchanged.
   - **Remove channel configuration** — reset one or more channels back to their defaults.
   - **Save and close** — applies everything; the entry reloads automatically.

### Removing / deleting

- **Reset a channel**: Configure → *Remove channel configuration* → select the channels.
- **Delete the integration entirely**: Settings → Devices & Services → Bilresa Remote → ⋮ → **Delete**. The remote stops responding to the integration immediately (the device itself keeps working in its default Matter behavior).

### Instant mode

For `instant` evaluation you must enable the **9 hidden sensor entities** of the BILRESA device: **Settings → Devices & Services → Devices → your BILRESA device → ⚙ (gear) → enable the hidden sensor entities**.

### Migrating from the blueprint

Remove the blueprint automation and recreate your actions in the integration options. Action sequences use the same format — you can copy them from your old automation's YAML editor and paste them into the actions editor via the YAML mode (⋮ → Edit in YAML) of each action block.

## Debug logging

```yaml
logger:
  logs:
    custom_components.bilresa_remote: debug
```

## Credits

Based on the [Ikea_bilresa_scroll_wheel blueprint](https://gist.github.com/jhol-byte/b2731a4d2476f530d76b9ff409f7f3a4) by jhol-byte. Licensed under [MIT](LICENSE).
