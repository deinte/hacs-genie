"""The Rituals Perfume Genie integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from aiohttp import ClientError
from .pyrituals import Account, AuthenticationException, Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    BASE_UPDATE_INTERVAL,
    CONF_STORED_EMAIL,
    CONF_STORED_PASSWORD,
    DOMAIN,
    RitualsRuntimeData,
)
from .coordinator import RitualsDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rituals Perfume Genie from a config entry."""
    data = entry.data
    email = data.get(CONF_STORED_EMAIL) or data.get(CONF_EMAIL)
    password = data.get(CONF_STORED_PASSWORD) or data.get(CONF_PASSWORD)

    if not email or not password:
        raise ConfigEntryAuthFailed("Credentials are missing, please reauthenticate.")

    session = async_get_clientsession(hass)
    account = Account(email=email, password=password, session=session)

    try:
        await account.authenticate()
    except AuthenticationException as err:
        raise ConfigEntryAuthFailed from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    try:
        diffusers = await account.get_devices()
    except AuthenticationException as err:
        raise ConfigEntryAuthFailed from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    if not diffusers:
        _LOGGER.warning("No Rituals Perfume Genie diffusers found for %s", email)

    update_interval = BASE_UPDATE_INTERVAL * max(1, len(diffusers))
    reauth_lock = asyncio.Lock()

    coordinators: dict[str, RitualsDataUpdateCoordinator] = {
        diffuser.hublot: RitualsDataUpdateCoordinator(
            hass,
            entry,
            account,
            diffuser,
            update_interval,
            reauth_lock,
        )
        for diffuser in diffusers
    }

    await _async_refresh_all(coordinators.values())
    _store_runtime_data(hass, entry, account, coordinators, reauth_lock)
    async_migrate_entities_unique_ids(hass, entry, diffusers)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def _async_refresh_all(coordinators: Iterable[RitualsDataUpdateCoordinator]) -> None:
    """Refresh all coordinators concurrently."""
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators
        ]
    )


def _store_runtime_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    account: Account,
    coordinators: dict[str, RitualsDataUpdateCoordinator],
    reauth_lock: asyncio.Lock,
) -> None:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = RitualsRuntimeData(
        account=account,
        coordinators=coordinators,
        reauth_lock=reauth_lock,
    )


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, diffusers: list[Diffuser]
) -> None:
    """Migrate unique_ids in the entity registry to the new format."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    conversion: dict[tuple[str, str], str] = {
        (Platform.BINARY_SENSOR, " Battery Charging"): "charging",
        (Platform.NUMBER, " Perfume Amount"): "perfume_amount",
        (Platform.SELECT, " Room Size"): "room_size_square_meter",
        (Platform.SENSOR, " Battery"): "battery_percentage",
        (Platform.SENSOR, " Fill"): "fill",
        (Platform.SENSOR, " Perfume"): "perfume",
        (Platform.SENSOR, " Wifi"): "wifi_percentage",
        (Platform.SWITCH, ""): "is_on",
    }

    for diffuser in diffusers:
        for registry_entry in registry_entries:
            if new_unique_id := conversion.get(
                (
                    registry_entry.domain,
                    registry_entry.unique_id.removeprefix(diffuser.hublot),
                )
            ):
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    new_unique_id=f"{diffuser.hublot}-{new_unique_id}",
                )
