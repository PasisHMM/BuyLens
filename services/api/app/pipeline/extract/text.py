"""Page cleaning and number helpers shared by the extractors."""

import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, Tag

NOISE_TAGS = ("script", "style", "noscript", "svg", "iframe", "template", "nav", "footer", "form", "header")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean_text(html: str, max_chars: int = 200_000) -> str:
    """Visible page text with tables kept as `a | b | c` rows, for the LLM extractor."""
    soup = soup_of(html)
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(" | ".join(cells))
        table.replace_with("\n" + "\n".join(rows) + "\n")
    text = soup.get_text("\n")
    lines = [_WS.sub(" ", line).strip() for line in text.splitlines()]
    text = _BLANK_LINES.sub("\n\n", "\n".join(line for line in lines))
    return text[:max_chars]


def to_cents(value: object) -> int | None:
    """'98', '98.00', 98.0, '$1,098.50' → cents. None if not a price."""
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip().replace(",", "")
    raw = re.sub(r"^[^\d.]+", "", raw)
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None
    if amount < 0 or amount > 100_000:
        return None
    return int((amount * 100).quantize(Decimal(1)))


def to_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def number_in_text(value: float, text: str) -> bool:
    """True if `value` is written in `text` (26, 26.0, 26.5, 26½, 98.00, 98,00).

    Used to reject LLM-extracted numbers that don't literally appear on the page.
    """
    forms = {f"{value:g}", f"{value:.1f}", f"{value:.2f}", f"{value:.2f}".replace(".", ",")}
    if value == int(value):
        forms.add(str(int(value)))
    frac = value - int(value)
    if abs(frac - 0.5) < 1e-9:
        forms.update({f"{int(value)}½", f"{int(value)} 1/2", f"{int(value)}-1/2"})
    return any(re.search(rf"(?<![\d.,]){re.escape(form)}(?![\d]|[.,]\d)", text) for form in forms)


def attr_str(tag: Tag, name: str) -> str | None:
    value = tag.get(name)
    if isinstance(value, list):
        value = " ".join(value)
    return value.strip() if isinstance(value, str) and value.strip() else None
