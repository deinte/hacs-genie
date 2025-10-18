"""Minimal Rituals Perfume Genie API client.

This module is a trimmed copy of the `pyrituals` 0.0.7 client so the custom
component does not rely on external PyPI downloads. The public surface we rely
on (Account, Diffuser, AuthenticationException) matches the upstream package.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from aiohttp import ClientError, ClientSession, FormData

AUTH_URL = "https://rituals.sense-company.com/ocapi/login"
ACCOUNT_URL = "https://rituals.sense-company.com/api/account/hubs"
HUB_URL = "https://rituals.sense-company.com/api/account/hub"
UPDATE_URL = "https://rituals.sense-company.com/api/hub/update/attr"

_BASE = "https://rituals.apiv2.sense-company.com"
_AUTH_V2 = f"{_BASE}/apiv2/account/token"
_HUBS_V2 = f"{_BASE}/apiv2/account/hubs"
_ATTR_V2 = f"{_BASE}/apiv2/hubs/{{hub}}/attributes/{{attr}}"
_SENS_V2 = f"{_BASE}/apiv2/hubs/{{hub}}/sensors/{{sensor}}"


class AuthenticationException(Exception):
    """Raised when authentication fails."""


class _Api:
    def __init__(self, session: ClientSession | None) -> None:
        self._session = session
        self._own = False
        self._token: str | None = None

    async def __aenter__(self) -> "_Api":
        if self._session is None:
            self._session = ClientSession()
            self._own = True
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._own and self._session:
            await self._session.close()

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("Client session is not available")
        return self._session

    def set_token(self, token: str) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "*/*"}
        if self._token:
            headers["Authorization"] = self._token
        return headers

    async def get_json(self, url: str) -> Any:
        async with self.session.get(url, headers=self._headers(), timeout=10) as resp:
            if resp.status == 401:
                raise AuthenticationException("Unauthorized (401)")
            resp.raise_for_status()
            text = await resp.text()
            if not text:
                return {}
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ClientError(f"Invalid JSON from {url}") from exc

    async def post_form(self, url: str, form: dict[str, str]) -> Any:
        request_form = FormData()
        for key, value in form.items():
            request_form.add_field(key, str(value))

        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        async with self.session.post(
            url, headers=headers, data=request_form, timeout=10
        ) as resp:
            if resp.status == 401:
                raise AuthenticationException("Unauthorized (401)")
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return await resp.json()
            return await resp.text()

    async def post_json(self, url: str, body: dict[str, Any]) -> Any:
        headers = self._headers()
        headers["Content-Type"] = "application/json"

        async with self.session.post(
            url, headers=headers, json=body, timeout=10
        ) as resp:
            resp.raise_for_status()
            return await resp.json()


class Account:
    """Rituals user account."""

    def __init__(
        self,
        email: str = "",
        password: str = "",
        session: ClientSession | None = None,
        account_hash: str = "",
    ) -> None:
        self._email = email
        self._password = password
        self._session = session
        self.account_hash: str = account_hash
        self.data: dict[str, Any] | None = None
        self._api = _Api(session)

    @property
    def email(self) -> str:
        return self._email

    async def authenticate(
        self,
        session: ClientSession | None = None,
        url: str = AUTH_URL,
    ) -> None:
        """Authenticate with the Rituals API."""
        del url  # Compatibility argument not used in v2.
        if session is None:
            session = self._session
        if session is not None:
            self._api._session = session

        try:
            response = await self._api.post_json(
                _AUTH_V2, {"email": self._email, "password": self._password}
            )
        except ClientError as exc:
            raise AuthenticationException(f"Auth HTTP error: {exc}") from exc

        token = response.get("success")
        if not token:
            raise AuthenticationException(response.get("message") or "No success token")
        self._api.set_token(token)
        self.data = {"email": self._email}
        self.account_hash = ""

    async def get_devices(
        self,
        session: ClientSession | None = None,
        url: str = ACCOUNT_URL,
    ) -> list["Diffuser"]:
        """Retrieve all diffusers linked to the account."""
        del url
        if session is None:
            session = self._session
        if session is not None:
            self._api._session = session

        hubs = await self._api.get_json(_HUBS_V2)
        if not isinstance(hubs, list):
            raise RuntimeError("Invalid hubs response")
        return [Diffuser({"hub": _v2_hub_to_v1_shape(h)}, self._api) for h in hubs]


def _v2_hub_to_v1_shape(hub: dict[str, Any]) -> dict[str, Any]:
    """Convert v2 hub JSON to the v1 structure expected by Diffuser."""
    attribute_values = hub.get("attributeValues") or {}
    return {
        "hash": hub.get("hash", ""),
        "hublot": hub.get("hublot", ""),
        "status": 1,
        "attributes": {
            "roomnamec": attribute_values.get("roomnamec", "Genie"),
        },
        "sensors": {},
    }


class Diffuser:
    """Representation of a Rituals diffuser."""

    def __init__(self, data: dict[str, Any], api: _Api) -> None:
        self.data = data
        self._api = api

    @property
    def hub_data(self) -> dict[str, Any]:
        return self.data["hub"]

    @property
    def hash(self) -> str:
        return self.hub_data["hash"]

    @property
    def hublot(self) -> str:
        return self.hub_data["hublot"]

    @property
    def name(self) -> str:
        return self.hub_data.get("attributes", {}).get("roomnamec", "Genie")

    @property
    def is_online(self) -> bool:
        return self.hub_data.get("status", 1) == 1

    @property
    def is_on(self) -> bool:
        return self.hub_data.get("attributes", {}).get("fanc", "0") == "1"

    @property
    def perfume_amount(self) -> int:
        try:
            return int(self.hub_data.get("attributes", {}).get("speedc", "1"))
        except (TypeError, ValueError):
            return 1

    @property
    def fill(self) -> str:
        return self.hub_data.get("sensors", {}).get("fillc", {}).get("title", "")

    @property
    def perfume(self) -> str:
        return self.hub_data.get("sensors", {}).get("rfidc", {}).get("title", "")

    @property
    def has_cartridge(self) -> bool:
        cartridge_id = (
            self.hub_data.get("sensors", {}).get("rfidc", {}).get("id")
        )
        return True if cartridge_id is None else cartridge_id != 19

    @property
    def has_battery(self) -> bool:
        return "battc" in self.hub_data.get("sensors", {})

    @property
    def charging(self) -> bool:
        return self.hub_data.get("sensors", {}).get("battc", {}).get("id") == 21

    @property
    def battery_percentage(self) -> int:
        icon = self.hub_data.get("sensors", {}).get("battc", {}).get("icon")
        mapping = {
            "battery-charge.png": 100,
            "battery-full.png": 100,
            "Battery-75.png": 50,
            "battery-50.png": 25,
            "battery-low.png": 10,
        }
        if icon not in mapping:
            raise KeyError("Battery info not available")
        return mapping[icon]

    @property
    def wifi_percentage(self) -> int:
        icon = self.hub_data.get("sensors", {}).get("wific", {}).get("icon")
        mapping = {
            "icon-signal.png": 100,
            "icon-signal-75.png": 75,
            "icon-signal-low.png": 25,
            "icon-signal-0.png": 0,
        }
        if icon not in mapping:
            raise KeyError("WiFi info not available")
        return mapping[icon]

    @property
    def room_size(self) -> int:
        try:
            return int(self.hub_data.get("attributes", {}).get("roomc", "1"))
        except (TypeError, ValueError):
            return 1

    @property
    def room_size_square_meter(self) -> int:
        return {1: 15, 2: 30, 3: 60, 4: 100}[self.room_size]

    @property
    def version(self) -> str:
        return self.hub_data.get("sensors", {}).get("versionc", "")

    async def update_data(
        self,
        session: ClientSession | None = None,
        url: str = HUB_URL,
    ) -> None:
        """Fetch latest attributes and sensors for the diffuser."""
        del url
        if session is not None:
            self._api._session = session

        hub_hash = self.hash
        fanc = await self._api.get_json(_ATTR_V2.format(hub=hub_hash, attr="fanc"))
        speed = await self._api.get_json(_ATTR_V2.format(hub=hub_hash, attr="speedc"))

        try:
            roomc = await self._api.get_json(_ATTR_V2.format(hub=hub_hash, attr="roomc"))
            room_value = roomc.get("value")
        except Exception:
            room_value = None

        fillc = await self._safe_get_json(_SENS_V2.format(hub=hub_hash, sensor="fillc"))
        rfidc = await self._safe_get_json(_SENS_V2.format(hub=hub_hash, sensor="rfidc"))
        battc = await self._safe_get_json(_SENS_V2.format(hub=hub_hash, sensor="battc"))
        wific = await self._safe_get_json(_SENS_V2.format(hub=hub_hash, sensor="wific"))
        versc = await self._safe_get_json(
            _SENS_V2.format(hub=hub_hash, sensor="versionc")
        )

        sensors: dict[str, Any] = {}
        if isinstance(fillc, dict):
            sensors["fillc"] = fillc
        if isinstance(rfidc, dict):
            sensors["rfidc"] = rfidc
        if isinstance(battc, dict):
            sensors["battc"] = battc
        if isinstance(wific, dict):
            sensors["wific"] = wific
        if isinstance(versc, dict):
            sensors["versionc"] = versc

        attributes = self.hub_data.get("attributes", {}).copy()
        attributes["fanc"] = str(fanc.get("value", "0"))
        attributes["speedc"] = str(speed.get("value", "1"))
        if room_value is not None:
            attributes["roomc"] = str(room_value)

        self.data = {
            "hub": {
                "hash": hub_hash,
                "hublot": self.hublot,
                "status": 1,
                "attributes": attributes,
                "sensors": sensors,
            }
        }

    async def turn_on(
        self,
        session: ClientSession | None = None,
        url: str = UPDATE_URL,
    ) -> None:
        del url
        if session is not None:
            self._api._session = session
        await self._api.post_form(
            _ATTR_V2.format(hub=self.hash, attr="fanc"),
            {"fanc": "1"},
        )
        self.hub_data.setdefault("attributes", {})["fanc"] = "1"

    async def turn_off(
        self,
        session: ClientSession | None = None,
        url: str = UPDATE_URL,
    ) -> None:
        del url
        if session is not None:
            self._api._session = session
        await self._api.post_form(
            _ATTR_V2.format(hub=self.hash, attr="fanc"),
            {"fanc": "0"},
        )
        self.hub_data.setdefault("attributes", {})["fanc"] = "0"

    async def set_perfume_amount(
        self,
        amount: int,
        session: ClientSession | None = None,
        url: str = UPDATE_URL,
    ) -> None:
        del url
        amount = int(amount)
        if amount not in (1, 2, 3):
            raise ValueError("Amount must be 1..3")
        if session is not None:
            self._api._session = session
        await self._api.post_form(
            _ATTR_V2.format(hub=self.hash, attr="speedc"),
            {"speedc": str(amount)},
        )
        self.hub_data.setdefault("attributes", {})["speedc"] = str(amount)

    async def set_room_size(
        self,
        size: int,
        session: ClientSession | None = None,
        url: str = UPDATE_URL,
    ) -> None:
        del url
        size = int(size)
        if size not in (1, 2, 3, 4):
            raise ValueError("Size must be 1..4")
        if session is not None:
            self._api._session = session
        await self._api.post_form(
            _ATTR_V2.format(hub=self.hash, attr="roomc"),
            {"roomc": str(size)},
        )
        self.hub_data.setdefault("attributes", {})["roomc"] = str(size)

    async def set_room_size_square_meter(
        self,
        size: int,
        session: ClientSession | None = None,
        url: str = UPDATE_URL,
    ) -> None:
        mapping = {15: 1, 30: 2, 60: 3, 100: 4}
        if size not in mapping:
            raise ValueError("Size must be 15, 30, 60 or 100")
        await self.set_room_size(mapping[size], session=session)

    async def _safe_get_json(self, url: str) -> Optional[dict[str, Any]]:
        try:
            data = await self._api.get_json(url)
        except Exception:
            return None
        return data if isinstance(data, dict) else None
