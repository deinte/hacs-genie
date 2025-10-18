"""Support for Rituals Perfume Genie humidifier entity."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, RitualsRuntimeData
from .coordinator import RitualsDataUpdateCoordinator
from .entity import DiffuserEntity

MODE_MAP = {
    1: "low",
    2: "medium",
    3: "high",
}

MODE_REVERSE_MAP = {mode: amount for amount, mode in MODE_MAP.items()}


@dataclass(frozen=True, kw_only=True)
class RitualsHumidifierEntityDescription(HumidifierEntityDescription):
    """Class describing the humidifier entity."""


ENTITY_DESCRIPTION = RitualsHumidifierEntityDescription(
    key="diffuser",
    translation_key="diffuser",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser humidifier entity."""
    entry_data: RitualsRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    coordinators: dict[str, RitualsDataUpdateCoordinator] = entry_data["coordinators"]

    async_add_entities(
        RitualsHumidifierEntity(coordinator, ENTITY_DESCRIPTION)
        for coordinator in coordinators.values()
    )


class RitualsHumidifierEntity(DiffuserEntity, HumidifierEntity):
    """Representation of the diffuser as a humidifier."""

    _attr_available_modes = list(MODE_REVERSE_MAP.keys())
    _attr_supported_features = HumidifierEntityFeature.MODES

    @property
    def is_on(self) -> bool:
        """Return whether the diffuser is currently running."""
        return self.coordinator.diffuser.is_on

    @property
    def mode(self) -> str | None:
        """Return the active mode mapped from perfume amount."""
        amount = self.coordinator.diffuser.perfume_amount
        return MODE_MAP.get(amount)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the diffuser on."""
        await self.coordinator.diffuser.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the diffuser off."""
        await self.coordinator.diffuser.turn_off()
        self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the perfume amount via humidifier mode."""
        if mode not in MODE_REVERSE_MAP:
            raise ValueError(f"Unsupported mode: {mode}")
        await self.coordinator.diffuser.set_perfume_amount(MODE_REVERSE_MAP[mode])
        self.async_write_ha_state()
