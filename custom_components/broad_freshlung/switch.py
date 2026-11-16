"""Sleep switch: the fan preset can only enter sleep, this also leaves it."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FreshLungEntity
from .api import OP_SLEEP


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add(FreshLungSleepSwitch(coordinator, guid, "sleep") for guid in coordinator.devices)


class FreshLungSleepSwitch(FreshLungEntity, SwitchEntity):
    _attr_translation_key = "sleep"

    @property
    def is_on(self) -> bool | None:
        return self.status.get("FB_SLEEPMODEL_ON") == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.control(self.guid, (OP_SLEEP, "1"))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.control(self.guid, (OP_SLEEP, "0"))
