"""BROAD (远大新风) Fresh Lung ventilators through the vendor cloud."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .api import BroadAuthError, BroadClient, BroadError

DOMAIN = "broad_freshlung"
PLATFORMS = [Platform.FAN, Platform.SENSOR, Platform.BUTTON]
_LOGGER = logging.getLogger(__name__)


class FreshLungCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls every Fresh Lung device on the account; data maps eq_guid to its status."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=30))
        self.client = BroadClient(async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        self.devices: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            if not self.devices:
                self.devices = {d["eq_guid"]: d for d in await self.client.devices()}
            return {guid: await self.client.status(guid) for guid in self.devices}
        except BroadAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BroadError as err:
            raise UpdateFailed(str(err)) from err

    async def control(self, guid: str, op: str, value: str = "") -> None:
        """Send an operation and apply the live state it returns."""
        try:
            state = await self.client.control(guid, op, value)
        except BroadError as err:
            raise UpdateFailed(str(err)) from err
        if state:
            self.async_set_updated_data({**self.data, guid: state})
        else:
            await self.async_request_refresh()


class FreshLungEntity(CoordinatorEntity[FreshLungCoordinator]):
    """Base for entities of one device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreshLungCoordinator, guid: str, key: str) -> None:
        super().__init__(coordinator)
        self.guid = guid
        info = coordinator.devices[guid]
        self._attr_unique_id = f"{guid}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, guid)},
            manufacturer="BROAD 远大",
            model=info.get("product_model"),
            # the cloud names every unit after its product line until the user renames it in the app
            name=info.get("eq_name") if info.get("eq_name") not in (None, "", info.get("product_name")) else "远大新风",
            connections={("mac", ":".join(info["eq_address"][i : i + 2] for i in range(0, 12, 2)).lower())}
            if len(info.get("eq_address") or "") == 12
            else set(),
        )

    @property
    def status(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self.guid, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self.status)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = FreshLungCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
