"""Config flow for Rituals Perfume Genie integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from pyrituals import Account, AuthenticationException  # type: ignore[import-untyped]
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STORED_EMAIL, CONF_STORED_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class RitualsPerfumeGenieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rituals Perfume Genie."""

    VERSION = 2
    _reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=USER_DATA_SCHEMA)

        errors: dict[str, str] = {}

        try:
            await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except ClientError:
            _LOGGER.exception("Unexpected response from Rituals API")
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001 - bubble to flow UI
            _LOGGER.exception("Unexpected exception validating credentials")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_EMAIL],
                data={
                    CONF_STORED_EMAIL: user_input[CONF_EMAIL],
                    CONF_STORED_PASSWORD: user_input[CONF_PASSWORD],
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication with updated credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt the user to re-authenticate."""
        assert self._reauth_entry is not None  # For type checkers
        default_email = self._reauth_entry.data.get(CONF_STORED_EMAIL, "")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=default_email): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=data_schema
            )

        errors: dict[str, str] = {}
        try:
            await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except ClientError:
            _LOGGER.exception("Unexpected response from Rituals API")
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001 - bubble to flow UI
            _LOGGER.exception("Unexpected exception validating credentials")
            errors["base"] = "unknown"
        else:
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={
                    CONF_STORED_EMAIL: user_input[CONF_EMAIL],
                    CONF_STORED_PASSWORD: user_input[CONF_PASSWORD],
                },
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=data_schema, errors=errors
        )

    async def _async_validate_credentials(self, email: str, password: str) -> None:
        """Validate the provided credentials against the Rituals API."""
        session = async_get_clientsession(self.hass)
        account = Account(email=email, password=password, session=session)
        await account.authenticate()
        await account.get_devices()
