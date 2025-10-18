"""Constants for the Rituals Perfume Genie integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TypedDict

from asyncio import Lock

from pyrituals import Account  # type: ignore[import-untyped]

DOMAIN = "rituals_perfume_genie"

CONF_STORED_EMAIL = "email"
CONF_STORED_PASSWORD = "password"

# The API provided by Rituals is currently rate limited to 30 requests
# per hour per IP address. To avoid hitting this limit, we scale the
# polling interval with the number of diffusers a user owns.
BASE_UPDATE_INTERVAL = timedelta(minutes=3)


class RitualsRuntimeData(TypedDict):
    """Runtime data stored per config entry."""

    account: Account
    coordinators: dict[str, "RitualsDataUpdateCoordinator"]
    reauth_lock: Lock
