from __future__ import annotations

import asyncio

import pytest

import tg_music.telegram_client as tc
from tg_music.cli import build_parser


class FakeSession:
    def __init__(self, dc_id=1, server_address="149.154.175.59", port=443):
        self.dc_id = dc_id
        self.server_address = server_address
        self.port = port
        self.set_dc_calls: list[tuple[int, str, int]] = []

    def set_dc(self, dc_id, server_address, port):
        self.dc_id = dc_id
        self.server_address = server_address
        self.port = port
        self.set_dc_calls.append((dc_id, server_address, port))

    def save(self):
        return None


class FakeClient:
    def __init__(self, session=None, start_effects=None):
        self.session = session if session is not None else FakeSession()
        self.start_effects = list(start_effects or [])
        self.start_calls = 0
        self.disconnect_calls = 0

    async def start(self, **kwargs):
        self.start_calls += 1
        if self.start_effects:
            effect = self.start_effects.pop(0)
            if isinstance(effect, BaseException):
                raise effect
            return effect
        return self

    async def disconnect(self):
        self.disconnect_calls += 1


def test_dc_fallback_ips_base_first_excludes_current():
    assert tc.dc_fallback_ips(1, "149.154.175.59") == [
        "149.154.175.50",
        "149.154.175.51",
        "149.154.175.52",
    ]
    assert tc.dc_fallback_ips(1, "149.154.175.50") == [
        "149.154.175.51",
        "149.154.175.52",
        "149.154.175.53",
    ]


def test_dc_fallback_ips_unknown_dc():
    assert tc.dc_fallback_ips(99, "1.2.3.4") == []
    assert tc.dc_fallback_ips(None, "1.2.3.4") == []


def test_get_dc_ip_override_env_and_flag(monkeypatch):
    monkeypatch.setenv("TG_MUSIC_DC_IP", "149.154.175.50")
    assert tc.get_dc_ip_override() == "149.154.175.50"
    assert tc.get_dc_ip_override("149.154.175.51") == "149.154.175.51"
    monkeypatch.setenv("TG_MUSIC_DC_IP", "not-an-ip")
    assert tc.get_dc_ip_override() is None
    monkeypatch.delenv("TG_MUSIC_DC_IP", raising=False)
    assert tc.get_dc_ip_override() is None


def test_format_dc_connection_error_names_dc_and_ip():
    message = tc.format_dc_connection_error(1, "149.154.175.59", 443, tried=["149.154.175.59", "149.154.175.50"])
    assert "DC 1" in message
    assert "149.154.175.59" in message
    assert "TG_MUSIC_DC_IP" in message


def test_start_client_retries_on_fallback_ip():
    client = FakeClient(start_effects=[ConnectionError("Connection to Telegram failed 5 time(s)")])
    result = asyncio.run(tc.start_client(client))
    assert result is client
    assert client.start_calls == 2
    assert client.session.server_address == "149.154.175.50"
    assert client.session.dc_id == 1


def test_start_client_raises_with_dc_and_ip_after_all_fallbacks_fail():
    client = FakeClient(start_effects=[ConnectionError("fail")] * 5)
    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(tc.start_client(client))
    assert "DC 1" in str(excinfo.value)
    assert "149.154.175.59" in str(excinfo.value)
    assert client.start_calls == 4  # 1 initial + 3 fallbacks


def test_start_client_applies_dc_ip_override(monkeypatch):
    monkeypatch.setenv("TG_MUSIC_DC_IP", "149.154.175.50")
    client = FakeClient()
    result = asyncio.run(tc.start_client(client))
    assert result is client
    assert client.session.server_address == "149.154.175.50"


def test_start_client_does_not_retry_non_connection_errors():
    client = FakeClient(start_effects=[ValueError("wrong code")])
    with pytest.raises(ValueError, match="wrong code"):
        asyncio.run(tc.start_client(client))
    assert client.start_calls == 1


def test_login_parser_accepts_dc_ip():
    args = build_parser().parse_args(["login", "--dc-ip", "149.154.175.50"])
    assert args.dc_ip == "149.154.175.50"
    assert build_parser().parse_args(["login"]).dc_ip is None
