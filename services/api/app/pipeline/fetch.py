"""Polite, allow-list-bound HTTP fetching of seller pages.

- Only https hosts of allow-listed sellers can be requested, including after redirects.
- robots.txt is respected per host (cached for an hour).
- Requests to one host are spaced out (FETCH_MIN_INTERVAL_S).
- Bodies are capped (FETCH_MAX_BYTES).
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.robotparser import RobotFileParser

import httpx

from app.config import Settings
from app.pipeline.urls import host_of

ROBOTS_TTL_S = 3600


class FetchError(Exception):
    """A fetch failed. args[0] is a user-safe message."""


class FetchBlocked(FetchError):
    pass


@dataclass(frozen=True, slots=True)
class Page:
    url: str  # final URL after redirects
    status: int
    text: str
    content_type: str


class Fetcher(Protocol):
    async def get_page(self, url: str) -> Page: ...

    async def get_json(self, url: str) -> Any: ...

    async def aclose(self) -> None: ...


class HttpFetcher:
    def __init__(
        self,
        settings: Settings,
        host_allowed: Callable[[str], bool],
        transport: httpx.AsyncBaseTransport | None = None,  # tests inject httpx.MockTransport
    ) -> None:
        self._settings = settings
        self._host_allowed = host_allowed
        self._robots: dict[str, tuple[float, RobotFileParser]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_request: dict[str, float] = {}
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=settings.fetch_timeout_s,
            headers={"User-Agent": settings.fetch_user_agent, "Accept-Language": "en-US,en;q=0.8"},
            event_hooks={"request": [self._guard_host]},
            transport=transport,
        )

    async def _guard_host(self, request: httpx.Request) -> None:
        # Runs for every hop of a redirect chain, so a redirect can't leave the allow-list.
        if request.url.scheme != "https" or not self._host_allowed(request.url.host):
            raise FetchBlocked("That link leads outside the stores we support.")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_page(self, url: str) -> Page:
        return await self._request(url, accept="text/html,application/xhtml+xml")

    async def get_json(self, url: str) -> Any:
        page = await self._request(url, accept="application/json")
        try:
            return json.loads(page.text)
        except json.JSONDecodeError as exc:
            raise FetchError("The store returned data we couldn't read.") from exc

    async def _request(self, url: str, *, accept: str) -> Page:
        host = host_of(url)
        if not await self._robots_allows(url, host):
            raise FetchBlocked("This store doesn't allow automated checks of that page.")
        await self._throttle(host)
        try:
            async with self._client.stream("GET", url, headers={"Accept": accept}) as resp:
                status, final_url = resp.status_code, str(resp.url)
                content_type, encoding = resp.headers.get("content-type", ""), resp.encoding
                body = bytearray()
                if status < 400:
                    async for chunk in resp.aiter_bytes():
                        body += chunk
                        if len(body) > self._settings.fetch_max_bytes:
                            raise FetchError("That page is too large to check.")
        except FetchError:
            raise
        except httpx.TimeoutException as exc:
            raise FetchError("The store took too long to respond.") from exc
        except httpx.HTTPError as exc:
            raise FetchError("We couldn't reach the store.") from exc

        if status in (401, 403, 429):
            raise FetchBlocked("The store blocked our check. Try again later.")
        if status in (404, 410):
            raise FetchError("That product page doesn't exist anymore.")
        if status >= 400:
            raise FetchError("The store returned an error.")
        text = bytes(body).decode(encoding or "utf-8", errors="replace")
        return Page(url=final_url, status=status, text=text, content_type=content_type)

    async def _throttle(self, host: str) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._last_request.get(host, 0.0) + self._settings.fetch_min_interval_s - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request[host] = time.monotonic()

    async def _robots_allows(self, url: str, host: str) -> bool:
        cached = self._robots.get(host)
        if cached is None or time.monotonic() - cached[0] > ROBOTS_TTL_S:
            parser = RobotFileParser()
            try:
                resp = await self._client.get(f"https://{host}/robots.txt")
                if resp.status_code in (401, 403):
                    parser.parse(["User-agent: *", "Disallow: /"])
                elif resp.status_code >= 400:
                    parser.parse([])  # no robots.txt: everything allowed
                else:
                    parser.parse(resp.text.splitlines())
            except FetchBlocked:
                raise
            except httpx.HTTPError:
                parser.parse([])  # unreachable robots.txt: the page request itself will tell
            cached = (time.monotonic(), parser)
            self._robots[host] = cached
        return cached[1].can_fetch(self._settings.fetch_user_agent, url)
