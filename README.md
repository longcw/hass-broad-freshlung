# 远大新风 BROAD Air for Home Assistant

Home Assistant integration for BROAD (远大) fresh-air ventilators that the 远大新风 app lists as **新风肺保** (Fresh Lung), such as the FF100-Pro. It talks to the same cloud API as the app, so the app keeps working alongside it.

## Install

1. HACS → ⋮ → Custom repositories → add `longcw/hass-broad-freshlung`, type **Integration**, then download it.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **远大新风 BROAD Air**, then log in with the phone number and password of your 远大新风 app account.

## Entities

- **Fan:** power, speed by gear (1–3, or 1–6 on larger units), and a `sleep` preset.
- **Sensors:** airflow (m³/h), running gear, coarse and HEPA filter life, fault. PM2.5 and CO2 appear only on units fitted with those modules.
- **Switch:** sleep mode, on and off.
- **Buttons:** reset the coarse and HEPA filter timers after a clean or a replacement.

State is polled every minute. After a command it reads the live state again within a few seconds, until the device shows the change.

## Notes

- Central fresh-air units (the app's 新风机) use a different API and are not supported; see [Team-Cyan/broadair-hass-integration](https://github.com/Team-Cyan/broadair-hass-integration) for those.
- The command codes come from the app's own web bundle; the login signature scheme is the one the app uses. All traffic goes to `https://broadair.remotcon.mobi` with TLS verification on.
