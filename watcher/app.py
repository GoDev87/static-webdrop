#!/usr/bin/env python3
"""Watch a directory of static websites and sync them into Homarr Apps.

A folder named "docs" under SITES_DIR becomes:
  https://docs.${SITES_BASE_DOMAIN}

This intentionally does not talk to Nginx Proxy Manager. Use one wildcard NPM
proxy host: *.${SITES_BASE_DOMAIN} -> static-sites:8080.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


SITE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
DEFAULT_ICON = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg/nginx.svg"


@dataclass(frozen=True)
class Settings:
    sites_dir: Path
    base_domain: str
    scan_interval: int
    homarr_enabled: bool
    homarr_url: str
    homarr_api_key: str
    homarr_auth_mode: str
    homarr_icon_url: str
    homarr_description: str
    delete_removed: bool
    state_file: Path


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    base_domain = os.getenv("SITES_BASE_DOMAIN", "").strip().lower().strip(".")
    if not base_domain:
        print("ERROR: SITES_BASE_DOMAIN is required", file=sys.stderr)
        sys.exit(2)

    try:
        interval = int(os.getenv("SCAN_INTERVAL", "30"))
    except ValueError:
        interval = 30

    return Settings(
        sites_dir=Path(os.getenv("SITES_DIR", "/sites")),
        base_domain=base_domain,
        scan_interval=max(5, interval),
        homarr_enabled=env_bool("HOMARR_ENABLED", False),
        homarr_url=os.getenv("HOMARR_URL", "http://homarr:7575").rstrip("/"),
        homarr_api_key=os.getenv("HOMARR_API_KEY", ""),
        homarr_auth_mode=os.getenv("HOMARR_AUTH_MODE", "apikey").lower(),
        homarr_icon_url=os.getenv("HOMARR_ICON_URL", DEFAULT_ICON),
        homarr_description=os.getenv("HOMARR_DESCRIPTION", "Static website managed by static-webdrop"),
        delete_removed=env_bool("DELETE_REMOVED", False),
        state_file=Path(os.getenv("STATE_FILE", "/data/state.json")),
    )


def site_url(site: str, settings: Settings) -> str:
    return f"https://{site}.{settings.base_domain}"


def scan_sites(settings: Settings) -> dict[str, dict[str, str]]:
    sites: dict[str, dict[str, str]] = {}
    if not settings.sites_dir.exists():
        print(f"WARN: sites dir does not exist: {settings.sites_dir}")
        return sites

    for child in sorted(settings.sites_dir.iterdir()):
        if not child.is_dir():
            continue

        name = child.name.lower()
        if not SITE_NAME_RE.fullmatch(name):
            print(f"WARN: ignoring invalid folder name {child.name!r}; use lowercase letters, numbers, and hyphens")
            continue

        if not (child / "index.html").exists():
            print(f"WARN: ignoring {child.name!r}; missing index.html")
            continue

        sites[name] = {
            "name": name,
            "url": site_url(name, settings),
            "path": str(child),
        }
    return sites


def read_state(settings: Settings) -> dict[str, Any]:
    try:
        return json.loads(settings.state_file.read_text())
    except FileNotFoundError:
        return {"sites": {}}
    except Exception as exc:
        print(f"WARN: failed to read state file: {exc}")
        return {"sites": {}}


def write_state(settings: Settings, state: dict[str, Any]) -> None:
    settings.state_file.parent.mkdir(parents=True, exist_ok=True)
    settings.state_file.write_text(json.dumps(state, indent=2, sort_keys=True))


class HomarrClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

        if settings.homarr_auth_mode in {"apikey", "both"}:
            self.session.headers["ApiKey"] = settings.homarr_api_key
        if settings.homarr_auth_mode in {"bearer", "both"}:
            self.session.headers["Authorization"] = f"Bearer {settings.homarr_api_key}"

    def _url(self, path: str) -> str:
        return f"{self.settings.homarr_url}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = self.session.request(method, self._url(path), timeout=15, **kwargs)
        if response.status_code >= 400:
            body = response.text[:500].replace("\n", " ")
            raise RuntimeError(f"Homarr {method} {path} failed: HTTP {response.status_code}: {body}")
        return response

    def list_apps(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/apps").json()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("items", "apps", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def find_app(self, apps: list[dict[str, Any]], name: str, href: str) -> dict[str, Any] | None:
        wanted_names = {name, f"Static: {name}"}
        for app in apps:
            if app.get("href") == href:
                return app
        for app in apps:
            if app.get("name") in wanted_names:
                return app
        return None

    def payload(self, name: str, href: str, *, include_managed_metadata: bool = True) -> dict[str, Any]:
        payload = {
            "name": f"Static: {name}",
            "description": self.settings.homarr_description,
            "iconUrl": self.settings.homarr_icon_url,
            "href": href,
            "pingUrl": href,
        }
        if not include_managed_metadata:
            for key in ("name", "description", "iconUrl"):
                payload.pop(key)
        return payload

    def upsert_site(self, name: str, href: str, apps_cache: list[dict[str, Any]]) -> str:
        existing = self.find_app(apps_cache, name, href)

        if existing:
            app_id = existing.get("id") or existing.get("appId")
            if not app_id:
                print(f"WARN: found existing app for {href}, but it has no id; skipping update")
                return "skipped"
            payload = self.payload(name, href, include_managed_metadata=False)
            self._request("PATCH", f"/api/apps/{app_id}", json={"id": app_id, **payload})
            return "updated"

        payload = self.payload(name, href)
        created = self._request("POST", "/api/apps", json=payload).json()
        app_id = created.get("id") or created.get("appId") if isinstance(created, dict) else None
        if app_id:
            apps_cache.append({"id": app_id, **payload})
        return "created"

    def delete_site(self, name: str, href: str, apps_cache: list[dict[str, Any]]) -> str:
        existing = self.find_app(apps_cache, name, href)
        if not existing:
            return "missing"
        app_id = existing.get("id") or existing.get("appId")
        if not app_id:
            return "skipped"
        self._request("DELETE", f"/api/apps/{app_id}")
        return "deleted"


def sync_once(settings: Settings) -> None:
    sites = scan_sites(settings)
    state = read_state(settings)
    old_sites = state.get("sites", {}) if isinstance(state, dict) else {}

    print(f"Found {len(sites)} valid static site(s): {', '.join(sites) or '-'}")

    if settings.homarr_enabled:
        if not settings.homarr_api_key or settings.homarr_api_key == "replace_me":
            print("WARN: HOMARR_ENABLED=1 but HOMARR_API_KEY is empty/placeholder; skipping Homarr sync")
        else:
            client = HomarrClient(settings)
            try:
                apps = client.list_apps()
                for name, info in sites.items():
                    status = client.upsert_site(name, info["url"], apps)
                    print(f"Homarr {status}: {name} -> {info['url']}")

                if settings.delete_removed:
                    removed = sorted(set(old_sites) - set(sites))
                    for name in removed:
                        href = old_sites[name].get("url") or site_url(name, settings)
                        status = client.delete_site(name, href, apps)
                        print(f"Homarr removal {status}: {name} -> {href}")
            except Exception as exc:
                print(f"ERROR: Homarr sync failed: {exc}", file=sys.stderr)
    else:
        print("Homarr sync disabled. Set HOMARR_ENABLED=1 after filling HOMARR_API_KEY.")

    write_state(settings, {"sites": sites, "updatedAt": int(time.time())})


def main() -> None:
    settings = load_settings()
    print("static-webdrop watcher started")
    print(f"Sites dir: {settings.sites_dir}")
    print(f"Base domain: {settings.base_domain}")
    print(f"Homarr sync: {'enabled' if settings.homarr_enabled else 'disabled'}")

    while True:
        sync_once(settings)
        time.sleep(settings.scan_interval)


if __name__ == "__main__":
    main()
