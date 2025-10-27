"""Tools for scraping chart and product data from HTML pages."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

import requests
from bs4 import BeautifulSoup

CURRENCY_REGEX = re.compile(r"(?P<currency>[₺€$£]|TRY|USD|EUR|GBP)\s?(?P<value>[\d.,]+)")


@dataclass
class ChartDataset:
    label: str
    values: List[float]
    labels: List[str]
    color: Optional[str] = None


@dataclass
class ProductCard:
    name: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    description: Optional[str]
    image_url: Optional[str]


@dataclass
class ScrapeResult:
    url: str
    title: Optional[str]
    chart_title: Optional[str]
    datasets: List[ChartDataset] = field(default_factory=list)
    products: List[ProductCard] = field(default_factory=list)
    images: List[tuple[str, Optional[str], Optional[str]]] = field(default_factory=list)
    raw_payload: Optional[str] = None


class ScraperError(RuntimeError):
    """Raised when the scraper fails to collect meaningful data."""


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    )
}


def fetch_html(url: str) -> str:
    """Fetch raw HTML from the given URL."""
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def load_sample_html() -> str:
    """Load the bundled sample HTML file."""
    with open("examples/sample_chart_page.html", "r", encoding="utf-8") as sample_file:
        return sample_file.read()


def parse_price(text: str) -> tuple[Optional[float], Optional[str]]:
    """Parse price text into numeric value and currency symbol."""
    match = CURRENCY_REGEX.search(text)
    if not match:
        return None, None
    currency = match.group("currency")
    value = match.group("value").replace(".", "").replace(",", ".")
    try:
        return float(value), currency
    except ValueError:
        return None, currency


def try_parse_json(text: str) -> Optional[dict]:
    """Attempt to parse a JSON object from a script body."""
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def normalise_chart(payload: dict) -> tuple[Optional[str], List[ChartDataset]]:
    """Convert assorted chart payloads into ChartDataset instances."""
    chart_title: Optional[str] = payload.get("title") or payload.get("name")
    labels: List[str] = payload.get("labels", [])
    datasets: List[ChartDataset] = []
    raw_datasets = payload.get("datasets") or payload.get("series") or []
    for dataset in raw_datasets:
        dataset_label = dataset.get("label") or dataset.get("name") or "Veri Seti"
        data_points: Iterable = dataset.get("data") or dataset.get("values") or []
        color = dataset.get("backgroundColor") or dataset.get("color")
        try:
            numeric_points = [float(point) for point in data_points]
        except (TypeError, ValueError):
            continue
        datasets.append(
            ChartDataset(label=dataset_label, values=numeric_points, labels=labels, color=color)
        )
    return chart_title, datasets


def extract_chart_data(soup: BeautifulSoup) -> tuple[Optional[str], List[ChartDataset], Optional[str]]:
    """Look for JSON chart definitions within the page."""
    for script in soup.find_all("script"):
        script_type = (script.get("type") or "").lower()
        if script_type and script_type not in {"application/json", "application/ld+json"}:
            continue
        script_payload = script.string or script.get_text()
        if not script_payload:
            continue
        parsed = try_parse_json(script_payload)
        if not parsed:
            continue
        chart_payload = None
        if isinstance(parsed, dict):
            if "chart" in parsed:
                chart_payload = parsed["chart"]
            elif "data" in parsed and isinstance(parsed["data"], dict):
                data_section = parsed["data"]
                if {"labels", "datasets"} <= data_section.keys():
                    chart_payload = data_section
            elif {"labels", "datasets"} <= parsed.keys():
                chart_payload = parsed
        if chart_payload:
            raw_json = json.dumps(chart_payload, ensure_ascii=False)
            title, datasets = normalise_chart(chart_payload)
            if datasets:
                source_name = script.get("data-chart") or script.get("id") or script.get("class")
                return title, datasets, raw_json
    return None, [], None


def extract_products(soup: BeautifulSoup) -> List[ProductCard]:
    """Attempt to extract product cards from the document."""
    product_selectors = "[data-product], .product-card, article.product, li.product"
    products: List[ProductCard] = []
    seen_names: set[str] = set()
    for node in soup.select(product_selectors):
        name_candidate = (
            node.get("data-name")
            or (node.select_one("[itemprop='name']") or node.find(["h1", "h2", "h3", "h4"]))
        )
        if hasattr(name_candidate, "get_text"):
            product_name = name_candidate.get_text(strip=True)
        else:
            product_name = name_candidate
        if product_name:
            if product_name in seen_names:
                continue
            seen_names.add(product_name)
        price_candidate = node.get("data-price") or node.get("data-amount")
        if not price_candidate:
            price_element = node.select_one("[itemprop='price'], .price, .amount")
            if price_element:
                price_candidate = price_element.get_text(" ", strip=True)
        description_element = node.select_one("[itemprop='description'], .description, p")
        description = description_element.get_text(strip=True) if description_element else None
        image_element = node.find("img")
        image_url = image_element.get("src") if image_element else None
        price_value, currency = (None, None)
        if price_candidate:
            price_value, currency = parse_price(str(price_candidate))
        products.append(
            ProductCard(
                name=product_name,
                price=price_value,
                currency=currency,
                description=description,
                image_url=image_url,
            )
        )
    return products


def extract_images(soup: BeautifulSoup) -> List[tuple[str, Optional[str], Optional[str]]]:
    """Collect distinct imagery associated with charts or products."""
    images: List[tuple[str, Optional[str], Optional[str]]] = []
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        alt_text = img.get("alt")
        context = None
        parent = img.find_parent()
        if parent and parent.has_attr("data-product"):
            context = "product"
        images.append((src, alt_text, context))
    return images


def scrape(url: str, html_override: str | None = None) -> ScrapeResult:
    """High level helper that orchestrates the scraping workflow."""
    html = html_override if html_override is not None else fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(strip=True) if soup.title else None
    chart_title, datasets, raw_chart = extract_chart_data(soup)
    products = extract_products(soup)
    images = extract_images(soup)

    if not datasets and not products:
        raise ScraperError("Sayfada analiz edilecek grafik veya ürün bulunamadı.")

    result = ScrapeResult(
        url=url,
        title=page_title,
        chart_title=chart_title,
        datasets=datasets,
        products=products,
        images=images,
        raw_payload=raw_chart,
    )
    return result


__all__ = [
    "ChartDataset",
    "ProductCard",
    "ScrapeResult",
    "ScraperError",
    "scrape",
    "fetch_html",
    "load_sample_html",
]
