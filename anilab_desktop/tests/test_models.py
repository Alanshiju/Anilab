"""Unit tests for Pydantic models, LocalStore, and AniMeloClient."""

from __future__ import annotations

from pathlib import Path

import httpx

from anilab_desktop.api.client import AniMeloClient
from anilab_desktop.api.crypto import WireCrypto, canonical_request
from anilab_desktop.api.transport import AniMeloTransport
from anilab_desktop.models import (
    AccountUser,
    AnimeDetails,
    AnimeListResponse,
    AnimeProvidersResponse,
    AppConfigResponse,
    ContinueWatchingItem,
    HomeResponse,
    SessionData,
)
from anilab_desktop.playback.launcher import format_player_launch_summary
from anilab_desktop.state.store import LocalStore


def test_config_and_player_model_parsing() -> None:
    payload = {
        "refreshAfterSeconds": 3600,
        "messages": [],
        "player": {
            "appName": "KYOTO Player",
            "androidPackageId": "com.kyotoplayer",
            "androidActivity": "com.kyotoplayer.ui.screens.EpisodesActivity",
            "downloadsActivity": "com.kyotoplayer.ui.screens.DownloadsActivity",
            "launchExtras": {},
            "playStoreUrl": "market://details?id=com.kyotoplayer",
            "installPrompt": {
                "title": "Install KYOTO Player",
                "buttonLabel": "Open Play Store",
            },
        },
        "q0": {"enabled": True},
        "unknownFutureField": "ignored",
    }
    cfg = AppConfigResponse.model_validate(payload)
    assert cfg.refreshAfterSeconds == 3600
    assert cfg.access == {"enabled": True}
    assert cfg.player is not None
    assert cfg.player.appName == "KYOTO Player"
    assert cfg.player.androidPackageId == "com.kyotoplayer"


def test_home_and_details_model_parsing() -> None:
    home = HomeResponse.model_validate(
        {
            "spotlight": [{"id": 1230, "title": "Detective Conan", "score": "8.2"}],
            "sections": {
                "trending": [{"id": 6482, "title": "Black Clover Season 2"}]
            },
        }
    )
    assert home.spotlight[0].id == 1230
    assert home.sections["trending"][0].title == "Black Clover Season 2"

    details = AnimeDetails.model_validate(
        {
            "id": 1230,
            "title": "Detective Conan",
            "useProvidersPage": False,
            "providers": [
                {
                    "id": "crunchyroll",
                    "name": "Crunchyroll",
                    "url": "http://www.crunchyroll.com/series-263367",
                }
            ],
            "player": {
                "appName": "KYOTO Player",
                "androidPackageId": "com.kyotoplayer",
                "androidActivity": "com.kyotoplayer.ui.screens.EpisodesActivity",
                "launchExtras": {
                    "POST_ID": "animelo-1230",
                    "POST_TITLE": "Detective Conan",
                },
            },
        }
    )
    assert details.useProvidersPage is False
    assert details.providers[0].name == "Crunchyroll"
    assert details.player is not None
    assert details.player.launchExtras["POST_ID"] == "animelo-1230"

    summary = format_player_launch_summary(details.player, player_token="ptok")
    assert "com.kyotoplayer" in summary
    assert "POST_ID: animelo-1230" in summary
    assert "USER_TOKEN: <present>" in summary


def test_providers_search_and_account_models() -> None:
    provs = AnimeProvidersResponse.model_validate(
        {
            "title": "Sample",
            "providers": [
                {"name": "Crunchyroll", "url": "https://www.crunchyroll.com/"}
            ],
        }
    )
    assert provs.providers[0].url == "https://www.crunchyroll.com/"

    search = AnimeListResponse.model_validate(
        {"nextPage": 2, "data": [{"id": 3341, "title": "Zero's Tea Time"}]}
    )
    assert search.nextPage == 2
    assert search.data[0].id == 3341

    user = AccountUser.model_validate(
        {"id": 1, "name": "User", "email": "u@example.com", "playerToken": "pt"}
    )
    cw = ContinueWatchingItem.model_validate(
        {"anime": {"id": 1230, "title": "Detective Conan"}, "watchedAtMs": 1000}
    )
    assert user.playerToken == "pt"
    assert cw.anime.id == 1230


def test_store_and_client_integration(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "state.json")
    store.set_session(
        SessionData(
            token="api-tok",
            user=AccountUser(id=1, name="Tester", playerToken="ptok"),
        )
    )
    reloaded = LocalStore(tmp_path / "state.json")
    assert reloaded.get_token() == "api-tok"
    assert reloaded.get_player_token() == "ptok"

    crypto = WireCrypto(b"unit-test-wire-secret-32-bytes!!")

    def handler(request: httpx.Request) -> httpx.Response:
        req_nonce = request.headers["X-Nonce"]
        canonical = canonical_request(request.method, request.url.path, "")
        assert crypto.decrypt_seal(request.headers["X-Seal"], req_nonce, canonical) == "api-tok"
        resp_nonce = WireCrypto.generate_nonce()
        enc = crypto.encrypt_response_body(
            b'{"spotlight":[{"id":1,"title":"Test"}],"sections":{}}',
            "application/json",
            resp_nonce,
            req_nonce,
        )
        return httpx.Response(200, headers={"X-Nonce": resp_nonce}, content=enc)

    transport = AniMeloTransport(
        inner=httpx.MockTransport(handler),
        crypto=crypto,
        token_provider=reloaded.get_token,
    )
    with AniMeloClient(
        store=reloaded, base_url="https://example.test/api/", transport=transport
    ) as client:
        home = client.get_home()
    assert home.spotlight[0].title == "Test"
