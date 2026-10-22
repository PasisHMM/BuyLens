import pytest

from app.pipeline.cache import MemoryCache
from app.pipeline.extract import ExtractionFailed, extract_product
from app.pipeline.extract.attributes import infer_category, infer_stretch, parse_size_label, size_display
from app.pipeline.extract.jsonld import apply_meta_fallbacks, extract_jsonld
from app.pipeline.extract.llm import LLMProductPage, LLMSizeRow
from app.pipeline.extract.shopify import parse_product_js
from app.pipeline.extract.text import number_in_text, soup_of, to_cents
from tests.fakes import FakeFetcher, FakeLLM, fixture, seller

URL = "https://www.brand.test/us/501-original-cropped-jeans/p/A1234"


def test_jsonld_product_group():
    e = extract_jsonld(URL, URL, "brand.test", soup_of(fixture("brand_product.html")))
    assert e is not None
    assert (e.name, e.brand, e.mpn) == ("501® Original Cropped Jeans", "Levi's", "A1234")
    assert (e.price_cents, e.currency, e.shipping_cents) == (9800, "USD", 0)
    assert e.gtin is None  # variant GTINs identify sizes, not the product
    assert "0000000000260" in e.variant_gtins
    assert e.sizes == ["25x30", "26x30", "26x32", "27x30"]
    assert (e.review_rating, e.review_count, len(e.review_texts)) == (4.6, 1284, 4)
    assert e.in_stock is True
    assert e.attributes["fabric"] == "100% Cotton"


def test_meta_fallback_when_no_jsonld():
    soup = soup_of(fixture("meta_only.html"))
    e = apply_meta_fallbacks(extract_jsonld(URL, URL, "x.test", soup), URL, URL, "x.test", soup)
    assert e is not None
    assert (e.name, e.price_cents, e.currency, e.brand) == ("Relaxed Chino Pant", 6450, "USD", "Everlane")


def test_shopify_product_js():
    data = {
        "id": 42, "title": "Ribcage Straight Ankle", "vendor": "Levi's", "type": "Jeans",
        "options": [{"name": "Size"}, {"name": "Length"}],
        "variants": [
            {"price": 9800, "available": True, "option1": "26", "barcode": "000123", "sku": "A1"},
            {"price": 9800, "available": False, "option1": "27", "barcode": "000124", "sku": "A2"},
        ],
        "featured_image": "//cdn.test/img.jpg",
    }  # fmt: skip
    e = parse_product_js(data, "https://shop.test/products/ribcage", "shop.test")
    assert e is not None
    assert (e.price_cents, e.sizes, e.in_stock, e.external_id) == (9800, ["26", "27"], True, "42")
    assert e.variant_gtins == ["000123", "000124"]
    assert e.image_url == "https://cdn.test/img.jpg"


@pytest.mark.parametrize(
    ("raw", "cents"),
    [
        ("98", 9800),
        ("98.00", 9800),
        (98.5, 9850),
        ("$1,098.50", 109850),
        ("free", None),
        (None, None),
        (True, None),
    ],
)
def test_to_cents(raw, cents):
    assert to_cents(raw) == cents


def test_number_in_text_is_literal():
    text = "Waist 26½ in · Inseam 30 · Price $98.00 · 1,284 reviews"
    assert number_in_text(26.5, text)
    assert number_in_text(30, text)
    assert number_in_text(98, text)
    assert not number_in_text(36, text)
    assert not number_in_text(2, text)  # "26" must not count as "2"


@pytest.mark.parametrize(
    ("label", "parsed", "display"),
    [
        ("26x30", ("26", 30), "W26 / L30"),
        ("W26 L30", ("26", 30), "W26 / L30"),
        ("26W x 30L", ("26", 30), "W26 / L30"),
        ("26/30", ("26", 30), "W26 / L30"),
        ("26\u00d730", ("26", 30), "W26 / L30"),
        ("26", ("26", None), "W26"),
        ("M", None, "M"),
    ],
)
def test_size_labels(label, parsed, display):
    assert parse_size_label(label) == parsed
    assert size_display(label) == display


@pytest.mark.parametrize(
    ("texts", "category"),
    [
        (("501 Original Cropped Jeans",), "jeans"),
        (("Relaxed Chino Pant",), "pants"),
        (("Short Sleeve Shirt",), "tops"),
        (("Denim Shorts",), "jeans"),  # denim first: fit check still applies
        (("Silk Scarf",), None),
    ],
)
def test_infer_category(texts, category):
    assert infer_category(*texts) == category


@pytest.mark.parametrize(
    ("fabric", "texts", "stretch"),
    [
        ("100% Cotton", (), False),
        ("98% cotton, 2% elastane", (), True),
        (None, ("Non-stretch denim",), False),
        (None, ("Super stretch skinny",), True),
        (None, ("Straight leg",), None),  # unknown stays unknown
    ],
)
def test_infer_stretch(fabric, texts, stretch):
    assert infer_stretch(fabric, *texts) is stretch


async def test_extract_product_end_to_end_without_llm():
    fetcher = FakeFetcher({URL: fixture("brand_product.html")})
    llm = FakeLLM()  # no responses: any call would fail, and the size chart is in a table
    e = await extract_product(
        URL, seller("brand.test"), fetcher=fetcher, llm=llm, cache=MemoryCache(), cache_ttl_s=60
    )
    assert e.category == "jeans"
    assert e.attributes["stretch"] is False
    assert e.attributes["wash"] == "medium wash"
    assert e.attributes["fit"] == "straight"
    # Canonical link is normalized (tracking stripped) and stays on the seller's domain.
    assert e.canonical_url == URL
    assert e.size_chart is not None and e.size_chart.source == "table"
    assert llm.calls == []


async def test_extract_product_is_cached():
    fetcher = FakeFetcher({URL: fixture("brand_product.html")})
    cache = MemoryCache()
    kwargs = {"fetcher": fetcher, "llm": None, "cache": cache, "cache_ttl_s": 60}
    await extract_product(URL, seller("brand.test"), **kwargs)
    await extract_product(URL, seller("brand.test"), **kwargs)
    assert fetcher.requested == [URL]


async def test_llm_fallback_drops_numbers_not_on_the_page():
    url = "https://shop.test/p/wide-leg"
    page = LLMProductPage(
        is_product_page=True, name="High Rise Wide Leg Jean", brand=None, category="Jeans",
        price=120.0, currency="USD", shipping_price=5.0,  # $5 shipping is NOT on the page
        color=None, fabric=None, sizes=["26", "27"], size_chart_unit="in", size_chart_basis="body",
        size_chart=[
            LLMSizeRow(label="26", waist=26, hips=36, inseam=31),  # inseam 31 is invented
            LLMSizeRow(label="27", waist=27, hips=37, inseam=None),
        ],
        review_rating=4.9, review_count=None,  # invented rating
    )  # fmt: skip
    llm = FakeLLM({LLMProductPage: page})
    fetcher = FakeFetcher({url: fixture("text_only.html")})
    e = await extract_product(
        url, seller("shop.test"), fetcher=fetcher, llm=llm, cache=MemoryCache(), cache_ttl_s=60
    )

    assert e.price_cents == 12000
    assert e.shipping_cents is None
    assert e.review_rating is None
    assert e.size_chart is not None
    row26 = next(r for r in e.size_chart.rows if r.label == "26")
    assert set(row26.measures) == {"waist", "hips"}
    assert row26.measures["waist"].cm == 66.0
    assert row26.measures["waist"].basis == "body"
    # The page text sent to the model has scripts stripped.
    assert "tracking" not in llm.calls[0][2]


async def test_unreadable_page_fails_with_user_message():
    url = "https://shop.test/p/empty"
    fetcher = FakeFetcher({url: "<html><body>Hello</body></html>"})
    with pytest.raises(ExtractionFailed, match="couldn't read"):
        await extract_product(url, seller("shop.test"), fetcher=fetcher, llm=FakeLLM(), cache=MemoryCache(),
                              cache_ttl_s=60)  # fmt: skip
