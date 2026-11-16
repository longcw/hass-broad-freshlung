"""Client for the BROAD (远大) cloud API, Fresh Lung (新风肺保) devices only."""

from __future__ import annotations

import hashlib
import json
import random
import time
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

BASE_URL = "https://broadair.remotcon.mobi"
# static app token the vendor's login signature is built from
APP_TOKEN = "8q7l82AxXB8Qo99vesUUvy1ED5tIuPT31NoIL6ZE5THH7clkfN"
FRESH_LUNG_EQ_TYPE = "03"
# head code for a missing or expired session; the app logs in again only on this one
SESSION_EXPIRED = 600

# SetFreshLung operations ("sjx"), taken from the vendor app's fb_mainV.html
OP_REALTIME = "1"
OP_OFF = "2"
OP_ON = "3"
OP_GEAR = "4"
OP_SLEEP = "5"
OP_RESET_COARSE = "8"
OP_RESET_HEPA = "9"


class BroadError(Exception):
    """The BROAD cloud failed or returned an error."""


class BroadAuthError(BroadError):
    """The BROAD cloud rejected the credentials."""


class BroadClient:
    """Signed-login session against the BROAD cloud."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None

    async def login(self) -> None:
        """Log in and keep the session token."""
        # the signature is rejected when the timestamp drifts from the server clock
        try:
            async with self._session.head(f"{BASE_URL}/api/Account/Login", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                ts = str(int(parsedate_to_datetime(resp.headers["Date"]).timestamp()))
        except (aiohttp.ClientError, TimeoutError, KeyError, ValueError, TypeError):
            ts = str(int(time.time()))
        nonce = f"{random.randint(0, 999999):06d}"
        data = await self._post(
            "Account/Login",
            {
                "user_id": self._username,
                "pass_word": self._password,
                "token": APP_TOKEN,
                "nonce": nonce,
                "timestamp": ts,
                "sign": hashlib.md5(f"{APP_TOKEN}{nonce}{ts}".encode()).hexdigest(),
            },
            auth=False,
        )
        if not isinstance(data, dict) or not data.get("token"):
            raise BroadAuthError("login returned no token")
        self._token = str(data["token"])

    async def devices(self) -> list[dict[str, Any]]:
        """Return the Fresh Lung devices bound to the account."""
        data = await self._post(
            "Equipment/GetEquipmentsList",
            {"user_id": self._username, "eqType": FRESH_LUNG_EQ_TYPE, "pageIndex": "1", "pageSize": "100"},
        )
        return [d for d in _unwrap(data) or [] if isinstance(d, dict) and d.get("eq_guid")]

    async def status(self, guid: str) -> dict[str, Any]:
        """Ask the device for live state, falling back to the cloud's last stored copy."""
        try:
            state = await self.control(guid, OP_REALTIME, "")
        except BroadAuthError:
            raise
        except BroadError:
            state = None
        if state:
            return state
        stored = _unwrap(await self._post("Equipment/GetFreshLung", {"eq_guid": guid}))
        if not isinstance(stored, dict):
            raise BroadError("no status for device")
        return stored

    async def control(self, guid: str, op: str, value: str) -> dict[str, Any] | None:
        """Send one SetFreshLung operation; the reply carries live state when the device answers."""
        state = _unwrap(await self._post("Equipment/SetFreshLung", {"eq_guid": guid, "sjx": op, "cs": value}))
        return state if isinstance(state, dict) else None

    async def _post(self, path: str, payload: dict[str, Any], *, auth: bool = True, retry: bool = True) -> Any:
        headers = {"Content-Type": "application/json"}
        if auth:
            if self._token is None:
                await self.login()
            headers["token"] = self._token or ""
        try:
            async with self._session.post(
                f"{BASE_URL}/api/{path}", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                resp.raise_for_status()
                envelope = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BroadError(f"{path}: {err}") from err
        head = envelope.get("Head") if isinstance(envelope, dict) else None
        code = head.get("Code") if isinstance(head, dict) else None
        if code == 200:
            return (envelope.get("Body") or {}).get("Data")
        msg = f"{path}: {head.get('Msg') if isinstance(head, dict) else envelope}"
        if not auth:
            # only login runs unauthenticated, and a refused login means bad credentials
            raise BroadAuthError(msg)
        if code == SESSION_EXPIRED:
            if retry:
                self._token = None
                return await self._post(path, payload, retry=False)
            raise BroadAuthError(msg)
        # other codes (such as 获取数据失败 when the device does not answer) are transient
        raise BroadError(msg)


def _unwrap(data: Any) -> Any:
    # Body.Data is usually a JSON document encoded as a string
    if isinstance(data, str):
        try:
            return json.loads(data)
        except ValueError:
            return data
    return data
