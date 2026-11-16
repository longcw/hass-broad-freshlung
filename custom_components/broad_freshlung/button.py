"""Filter-reset buttons, the same two the app offers."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FreshLungEntity
from .api import OP_RESET_COARSE, OP_RESET_HEPA


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add(
        FreshLungResetButton(coordinator, guid, key, op)
        for guid in coordinator.devices
        for key, op in (("reset_coarse_filter", OP_RESET_COARSE), ("reset_hepa_filter", OP_RESET_HEPA))
    )


class FreshLungResetButton(FreshLungEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, guid: str, key: str, op: str) -> None:
        super().__init__(coordinator, guid, key)
        self._attr_translation_key = key
        self._op = op

    async def async_press(self) -> None:
        await self.coordinator.control(self.guid, (self._op, "1"))
