"""Airflow, gear, filter life, and the optional PM2.5/CO2 modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDensity, UnitOfRatio, UnitOfTime, UnitOfVolumeFlowRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FreshLungEntity


def _num(key: str) -> Callable[[dict[str, Any]], float | None]:
    def read(s: dict[str, Any]) -> float | None:
        try:
            return float(s[key])
        except (KeyError, TypeError, ValueError):
            return None

    return read


def _life_left(used: str, life: str) -> Callable[[dict[str, Any]], float | None]:
    def read(s: dict[str, Any]) -> float | None:
        u, total = _num(used)(s), _num(life)(s)
        return round(max(0.0, 100 * (1 - u / total)), 1) if u is not None and total else None

    return read


@dataclass(frozen=True, kw_only=True)
class FreshLungSensorDescription(SensorEntityDescription):
    value: Callable[[dict[str, Any]], Any]
    # status flag that must be "1" for the sensor to exist (an optional hardware module)
    requires: str | None = None


SENSORS = (
    FreshLungSensorDescription(
        key="air_volume", translation_key="air_volume", value=_num("AIR_VOLUME"),
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE, native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FreshLungSensorDescription(key="gear", translation_key="gear", value=_num("RUNNING_GEAR"), state_class=SensorStateClass.MEASUREMENT),
    FreshLungSensorDescription(
        key="pm25", value=_num("PM_2_5_DUST_CONCENTRATION"), requires="DUST_MODULE_ACCESSORIES",
        device_class=SensorDeviceClass.PM25, native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FreshLungSensorDescription(
        key="co2", value=_num("CO2_CONCENTRATION"), requires="CO2_MODULE_ACCESSORIES",
        device_class=SensorDeviceClass.CO2, native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    FreshLungSensorDescription(
        key="coarse_filter_life", translation_key="coarse_filter_life", value=_life_left("COARSE_USED_TIME", "PRIMARY_CLEANING_CYCLE"),
        native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FreshLungSensorDescription(
        key="hepa_filter_life", translation_key="hepa_filter_life", value=_life_left("EFFICIENT_USED_TIME", "EFFICIENT_LIFE_CYCLE"),
        native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT, entity_category=EntityCategory.DIAGNOSTIC,
    ),
    FreshLungSensorDescription(
        key="coarse_filter_used", translation_key="coarse_filter_used", value=_num("COARSE_USED_TIME"),
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
    ),
    FreshLungSensorDescription(
        key="hepa_filter_used", translation_key="hepa_filter_used", value=_num("EFFICIENT_USED_TIME"),
        device_class=SensorDeviceClass.DURATION, native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
    ),
    FreshLungSensorDescription(
        key="fault", translation_key="fault", value=lambda s: s.get("ALLFAULT") or "none", entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    add(
        FreshLungSensor(coordinator, guid, d)
        for guid, status in coordinator.data.items()
        for d in SENSORS
        if d.requires is None or status.get(d.requires) == "1"
    )


class FreshLungSensor(FreshLungEntity, SensorEntity):
    entity_description: FreshLungSensorDescription

    def __init__(self, coordinator, guid: str, description: FreshLungSensorDescription) -> None:
        super().__init__(coordinator, guid, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.status)
