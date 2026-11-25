"""Read-only API verification script for AniMelo (single GETs, explicit timeouts)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anilab_desktop.api.transport import AniMeloTransport, BASE_URL


def _summarize_value(val: object) -> str:
    if isinstance(val, dict):
        return f"dict(keys={list(val.keys())})"
    if isinstance(val, list):
        return f"list(len={len(val)})"
    return repr(val)


def _find_first_anime_id(home_json: object) -> int | None:
    if isinstance(home_json, dict):
        for k, v in home_json.items():
            if k == "id" and isinstance(v, int) and v > 0:
                return v
            found = _find_first_anime_id(v)
            if found is not None:
                return found
    elif isinstance(home_json, list):
        for item in home_json:
            found = _find_first_anime_id(item)
            if found is not None:
                return found
    return None


def main() -> int:
    if not BASE_URL:
        print(
            "ANILAB_API_BASE_URL is not set. Set ANILAB_API_BASE_URL (and ANILAB_WIRE_SECRET if required) to run live API verification."
        )
        return 1
    transport = AniMeloTransport()
    with httpx.Client(
        transport=transport,
        base_url=BASE_URL,
        timeout=httpx.Timeout(15.0, connect=10.0),
    ) as client:
        print("1) GET config")
        r_cfg = client.get("config")
        print(f"   status={r_cfg.status_code}, content-type={r_cfg.headers.get('Content-Type')}")
        if r_cfg.status_code != 200:
            print("   body:", r_cfg.text[:300])
            return 1
        cfg = r_cfg.json()
        print("   top-level keys:", list(cfg.keys()))
        player_cfg = cfg.get("player")
        print("   player:", json.dumps(player_cfg, indent=2) if player_cfg else None)

        print("\n2) GET home")
        r_home = client.get("home")
        print(f"   status={r_home.status_code}, content-type={r_home.headers.get('Content-Type')}")
        if r_home.status_code != 200:
            print("   body:", r_home.text[:300])
            return 1
        home = r_home.json()
        print("   top-level keys:", list(home.keys()) if isinstance(home, dict) else _summarize_value(home))

        anime_id = _find_first_anime_id(home)
        if anime_id is None:
            print("   No anime id found in home response.")
            return 0

        print(f"\n3) GET anime/{anime_id}")
        r_anime = client.get(f"anime/{anime_id}")
        print(f"   status={r_anime.status_code}, content-type={r_anime.headers.get('Content-Type')}")
        if r_anime.status_code != 200:
            print("   body:", r_anime.text[:300])
            return 1
        anime = r_anime.json()
        print("   title:", anime.get("title"))
        print("   useProvidersPage:", anime.get("useProvidersPage"))
        print("   providers:", json.dumps(anime.get("providers"), indent=2))
        print("   player:", json.dumps(anime.get("player"), indent=2))

        if anime.get("useProvidersPage"):
            print(f"\n4) GET anime/{anime_id}/providers")
            r_prov = client.get(f"anime/{anime_id}/providers")
            print(f"   status={r_prov.status_code}, content-type={r_prov.headers.get('Content-Type')}")
            if r_prov.status_code == 200:
                print("   body:", json.dumps(r_prov.json(), indent=2))
            else:
                print("   body:", r_prov.text[:300])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
