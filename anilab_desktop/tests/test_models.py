"""Unit tests for Pydantic models, LocalStore, and JikanCatalogClient."""

from __future__ import annotations

from pathlib import Path

import httpx

from anilab_desktop.api.anilist import AniListCatalogClient
from anilab_desktop.api.client import FallbackCatalogClient
from anilab_desktop.api.jikan import JikanCatalogClient
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
            "appName": "External Player",
            "androidPackageId": "com.example.player",
            "androidActivity": "com.example.player.EpisodesActivity",
            "launchExtras": {},
        },
        "q0": {"enabled": True},
        "unknownFutureField": "ignored",
    }
    cfg = AppConfigResponse.model_validate(payload)
    assert cfg.refreshAfterSeconds == 3600
    assert cfg.access == {"enabled": True}
    assert cfg.player is not None
    assert cfg.player.appName == "External Player"


def test_home_and_details_model_parsing() -> None:
    home = HomeResponse.model_validate(
        {
            "spotlight": [{"id": 1, "title": "Cowboy Bebop", "score": "8.8"}],
            "sections": {
                "popular": [{"id": 2, "title": "Frieren"}]
            },
        }
    )
    assert home.spotlight[0].id == 1
    assert home.sections["popular"][0].title == "Frieren"

    details = AnimeDetails.model_validate(
        {
            "id": 1,
            "title": "Cowboy Bebop",
            "useProvidersPage": False,
            "providers": [
                {
                    "id": "crunchyroll",
                    "name": "Crunchyroll",
                    "url": "https://www.crunchyroll.com/",
                }
            ],
            "player": {
                "appName": "External Player",
                "androidPackageId": "com.example.player",
                "androidActivity": "com.example.player.EpisodesActivity",
                "launchExtras": {"POST_ID": "1", "POST_TITLE": "Cowboy Bebop"},
            },
        }
    )
    assert details.useProvidersPage is False
    assert details.providers[0].name == "Crunchyroll"
    summary = format_player_launch_summary(details.player, player_token="ptok")
    assert "POST_ID: 1" in summary
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
        {"nextPage": 2, "data": [{"id": 1, "title": "Sample"}]}
    )
    assert search.nextPage == 2

    user = AccountUser.model_validate(
        {"id": 1, "name": "User", "email": "u@example.com", "playerToken": "pt"}
    )
    cw = ContinueWatchingItem.model_validate(
        {"anime": {"id": 1, "title": "Sample"}, "watchedAtMs": 1000}
    )
    assert user.playerToken == "pt"
    assert cw.anime.id == 1


def test_jikan_catalog_client_mocked(tmp_path: Path) -> None:
    sample_item = {
        "mal_id": 52991,
        "title": "Sousou no Frieren",
        "title_english": "Frieren: Beyond Journey's End",
        "title_japanese": "葬送のフリーレン",
        "images": {
            "jpg": {
                "image_url": "https://cdn.myanimelist.net/images/anime/1015/138006.jpg",
                "large_image_url": "https://cdn.myanimelist.net/images/anime/1015/138006l.jpg",
            }
        },
        "type": "TV",
        "episodes": 28,
        "status": "Finished Airing",
        "score": 9.3,
        "season": "fall",
        "year": 2023,
        "duration": "24 min per ep",
        "synopsis": "An elf mage journeys after defeating the Demon King.",
        "trailer": {"embed_url": "https://www.youtube.com/embed/ZEkwCGJ3o7M"},
        "studios": [{"name": "Madhouse"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/seasons/now") or path.endswith("/top/anime"):
            return httpx.Response(
                200,
                json={
                    "data": [sample_item],
                    "pagination": {"has_next_page": False},
                },
            )
        if path.endswith("/anime"):
            return httpx.Response(
                200,
                json={
                    "data": [sample_item],
                    "pagination": {"has_next_page": True},
                },
            )
        if path.endswith("/anime/52991/full"):
            return httpx.Response(200, json={"data": sample_item})
        return httpx.Response(404)

    with JikanCatalogClient(
        min_interval=0.0, transport=httpx.MockTransport(handler)
    ) as client:
        home = client.get_home()
        assert len(home.spotlight) == 1
        assert home.spotlight[0].id == 52991
        assert home.spotlight[0].title == "Frieren: Beyond Journey's End"
        assert home.spotlight[0].score == "9.3"
        assert "airing" in home.sections

        srch = client.search("frieren")
        assert srch.nextPage == 2
        assert srch.data[0].id == 52991

        details = client.get_anime_details(52991)
        assert details.id == 52991
        assert details.episodeCount == 28
        assert details.premiered == "Fall 2023"
        assert details.studios == ["Madhouse"]
        assert details.trailerUrl == "https://www.youtube.com/embed/ZEkwCGJ3o7M"


def test_anilist_and_fallback_catalog_client_on_timeout(tmp_path: Path) -> None:
    anilist_media = {
        "id": 154587,
        "title": {
            "romaji": "Sousou no Frieren",
            "english": "Frieren: Beyond Journey's End",
            "native": "葬送のフリーレン",
        },
        "coverImage": {
            "extraLarge": "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587.jpg"
        },
        "format": "TV",
        "status": "FINISHED",
        "averageScore": 91,
        "episodes": 28,
        "season": "FALL",
        "seasonYear": 2023,
        "duration": 24,
        "description": "An <b>elf</b> mage.<br>Journey.",
        "trailer": {"id": "ZEkwCGJ3o7M", "site": "youtube"},
        "studios": {"nodes": [{"name": "Madhouse"}]},
    }

    def jikan_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    def anilist_handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        if "Media(id:" in body:
            return httpx.Response(200, json={"data": {"Media": anilist_media}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "Page": {
                        "pageInfo": {"hasNextPage": False},
                        "media": [anilist_media],
                    }
                }
            },
        )

    jikan = JikanCatalogClient(
        min_interval=0.0, transport=httpx.MockTransport(jikan_timeout)
    )
    anilist = AniListCatalogClient(
        transport=httpx.MockTransport(anilist_handler)
    )
    with FallbackCatalogClient(primary=jikan, fallback=anilist) as client:
        home = client.get_home()
        assert "latest" in home.sections
        assert home.sections["latest"][0].id == 154587
        assert home.sections["latest"][0].score == "9.1"

        details = client.get_anime_details(154587)
        assert details.title == "Frieren: Beyond Journey's End"
        assert details.synopsis == "An elf mage.\nJourney."
        assert details.trailerUrl == "https://www.youtube.com/watch?v=ZEkwCGJ3o7M"
        assert details.premiered == "Fall 2023"
        assert details.studios == ["Madhouse"]

    store = LocalStore(tmp_path / "state.json")
    store.set_session(
        SessionData(
            token="tok",
            user=AccountUser(id=1, name="Tester", playerToken="ptok"),
        )
    )
    reloaded = LocalStore(tmp_path / "state.json")
    assert reloaded.get_token() == "tok"
    assert reloaded.get_player_token() == "ptok"
