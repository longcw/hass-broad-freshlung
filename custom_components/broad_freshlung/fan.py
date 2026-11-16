"""Fan entity: power, gear as speed, and sleep as a preset."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from . import FreshLungEntity
from .api import OP_GEAR, OP_OFF, OP_ON, OP_SLEEP

PRESET_SLEEP = "sleep"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add(FreshLungFan(coordinator, guid, "fan") for guid in coordinator.devices)


class FreshLungFan(FreshLungEntity, FanEntity):
    """Gear 0 is the hardware's sleep mode, so speeds cover gears 1..max."""

    _attr_name = None
    _attr_preset_modes = [PRESET_SLEEP]
    _attr_supported_features = (
        FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF | FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
    )

    @property
    def _max_gear(self) -> int:
        # the app allows 3 gears on TYPE_SELECTION 1 (FE7-class units) and 6 on the rest
        return 3 if self.status.get("TYPE_SELECTION") == "1" else 6

    @property
    def speed_count(self) -> int:
        return self._max_gear

    @property
    def is_on(self) -> bool | None:
        return self.status.get("FB_ON") == "1"

    @property
    def percentage(self) -> int | None:
        gear = int(self.status.get("GEAR_POSITION") or 0)
        return ranged_value_to_percentage((1, self._max_gear), gear) if gear > 0 else 0

    @property
    def preset_mode(self) -> str | None:
        return PRESET_SLEEP if self.status.get("FB_SLEEPMODEL_ON") == "1" else None

    def _gear_ops(self, percentage: int) -> list[tuple[str, str]]:
        gear = max(1, round(percentage_to_ranged_value((1, self._max_gear), percentage)))
        # sleep keeps the stored gear and only drops the running one, so a gear change must leave sleep first
        leave_sleep = [(OP_SLEEP, "0")] if self.preset_mode == PRESET_SLEEP else []
        return [*leave_sleep, (OP_GEAR, str(gear))]

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        ops = [] if self.is_on else [(OP_ON, "")]
        if preset_mode:
            ops.append((OP_SLEEP, "1"))
        elif percentage:
            ops += self._gear_ops(percentage)
        await self.coordinator.control(self.guid, *ops)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.control(self.guid, (OP_OFF, ""))

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
        else:
            await self.coordinator.control(self.guid, *self._gear_ops(percentage))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.control(self.guid, (OP_SLEEP, "1"))
