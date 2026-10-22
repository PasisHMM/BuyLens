import httpx
import pytest

from app.config import Settings
from app.pipeline.fetch import FetchBlocked, FetchError, HttpFetcher
from app.pipeline.urls import InvalidProductUrl, domain_matches, normalize_url, seller_domain_for


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("levi.com/p/501?utm_source=ig&color=blue&gclid=x#reviews", "https://levi.com/p/501?color=blue"),
        ("http://WWW.Levi.com/p/501", "https://www.levi.com/p/501"),
        ("https://levi.com/p/501?b=2&a=1&fbclid=z", "https://levi.com/p/501?a=1&b=2"),
        ("  https://levi.com  ", "https://levi.com/"),
    ],
)
def test_normalize_url(raw, normalized):
    assert normalize_url(raw) == normalized


@pytest.mark.parametrize(
    "raw",
    ["javascript:alert(1)", "ftp://levi.com/x", "https://user:pw@levi.com/", "https://127.0.0.1/p",
     "https://[::1]/p", "https://levi.com:8443/p", "localhost/p", "file:///etc/passwd"],
)  # fmt: skip
def test_rejects_unsafe_urls(raw):
    with pytest.raises(InvalidProductUrl):
        normalize_url(raw)


def test_domain_matching():
    assert domain_matches("www.levi.com", "levi.com")
    assert domain_matches("levi.com", "levi.com")
    assert not domain_matches("evil-levi.com", "levi.com")
    assert not domain_matches("levi.com.evil.test", "levi.com")
    assert seller_domain_for("https://shop.levi.com/x", ["levi.com", "shop.levi.com"]) == "shop.levi.com"
    assert seller_domain_for("https://evil.test/x", ["levi.com"]) is None


def fetcher(handler, allowed=("shop.test",), **overrides) -> HttpFetcher:
    settings = Settings(fetch_min_interval_s=0, **overrides)
    return HttpFetcher(
        settings,
        host_allowed=lambda h: any(domain_matches(h, d) for d in allowed),
        transport=httpx.MockTransport(handler),
    )


def site(routes: dict[str, httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(request.url.path, httpx.Response(404))

    return handler


async def test_fetches_page_and_respects_robots():
    f = fetcher(site({
        "/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /checkout\n"),
        "/p/jeans": httpx.Response(200, html="<h1>Jeans</h1>"),
    }))  # fmt: skip
    page = await f.get_page("https://shop.test/p/jeans")
    assert "Jeans" in page.text
    with pytest.raises(FetchBlocked, match="doesn't allow"):
        await f.get_page("https://shop.test/checkout")


async def test_robots_403_blocks_everything():
    f = fetcher(site({"/robots.txt": httpx.Response(403), "/p": httpx.Response(200, html="ok")}))
    with pytest.raises(FetchBlocked):
        await f.get_page("https://shop.test/p")


async def test_redirect_off_the_allow_list_is_blocked():
    f = fetcher(site({"/p": httpx.Response(302, headers={"Location": "https://evil.test/steal"})}))
    with pytest.raises(FetchBlocked, match="outside the stores"):
        await f.get_page("https://shop.test/p")


async def test_bot_wall_and_missing_page():
    f = fetcher(site({"/blocked": httpx.Response(403), "/rate": httpx.Response(429)}))
    with pytest.raises(FetchBlocked):
        await f.get_page("https://shop.test/blocked")
    with pytest.raises(FetchBlocked):
        await f.get_page("https://shop.test/rate")
    with pytest.raises(FetchError, match="doesn't exist"):
        await f.get_page("https://shop.test/gone")


async def test_body_size_is_capped():
    f = fetcher(site({"/big": httpx.Response(200, content=b"x" * 5000)}), fetch_max_bytes=1000)
    with pytest.raises(FetchError, match="too large"):
        await f.get_page("https://shop.test/big")


async def test_plain_http_is_refused():
    f = fetcher(site({"/p": httpx.Response(200, html="ok")}))
    with pytest.raises(FetchBlocked):
        await f.get_page("http://shop.test/p")
