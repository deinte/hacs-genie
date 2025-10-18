"""The Rituals Perfume Genie data update coordinator."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiohttp import ClientError
from pyrituals import Account, AuthenticationException, Diffuser  # type: ignore[import-untyped]

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RitualsDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching Rituals Perfume Genie device data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass,
        config_entry: ConfigEntry,
        account: Account,
        diffuser: Diffuser,
        update_interval: timedelta,
        reauth_lock: asyncio.Lock,
    ) -> None:
        """Initialize global Rituals Perfume Genie data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{diffuser.hublot}",
            update_interval=update_interval,
        )
        self.account = account
        self.diffuser = diffuser
        self._reauth_lock = reauth_lock

    async def _async_update_data(self) -> None:
        """Fetch data from Rituals."""
        try:
            await self.diffuser.update_data()
        except AuthenticationException as err:
            await self._async_handle_auth_failure(err)
            await self.diffuser.update_data()
        except ClientError as err:
            raise UpdateFailed(f"Error communicating with Rituals API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating Rituals data: {err}") from err

    async def _async_handle_auth_failure(self, err: AuthenticationException) -> None:
        """Attempt to reauthenticate, raising if credentials are invalid."""
        async with self._reauth_lock:
            try:
                await self.account.authenticate()
            except AuthenticationException as auth_err:
                raise ConfigEntryAuthFailed from auth_err
            except ClientError as client_err:
                raise UpdateFailed(
                    f"Error refreshing Rituals authentication: {client_err}"
                ) from client_err
