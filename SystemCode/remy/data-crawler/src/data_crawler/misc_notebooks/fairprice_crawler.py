#!/usr/bin/env python3
"""
FairPrice category crawler.

Follows the DOM contract in CRAWL_INSTRUCT.md:

  * a product   is a <div data-impressiontype="PRODUCT_IMPRESSION">
  * its price   is a descendant whose class ends with "iNLBGt"
  * its name    is a descendant whose class ends with "gpnjpI"
  * quantity +  dietary note live in the container whose class ends with
    "iIDbJm": its first child <span> is the selling quantity ("5kg"), and an
    optional second child <span> -- the one holding
    data-testid="dietary-attributes-separator" -- is the dietary note.

Category pages server-render only the first ~25 products and load the rest via
infinite scroll (there is no ?page= parameter; it is ignored), so the full crawl
drives headless Chrome and scrolls until the grid stops growing.

Usage:
    python3 fairprice_crawler.py                    # all 5 categories -> data/output_raw/
    python3 fairprice_crawler.py --engine requests  # first page of each, no browser
    python3 fairprice_crawler.py --url https://www.fairprice.com.sg/category/frozen
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

SITE_ROOT = "https://www.fairprice.com.sg"

CATEGORIES = [
    "https://www.fairprice.com.sg/category/fruits-vegetables",
    "https://www.fairprice.com.sg/category/meat-seafood",
    "https://www.fairprice.com.sg/category/dairy-chilled-eggs",
    "https://www.fairprice.com.sg/category/rice-noodles-cooking-ingredients",
    "https://www.fairprice.com.sg/category/frozen",
]

# --- The DOM contract from CRAWL_INSTRUCT.md -------------------------------
# These are styled-components hashes: stable per deploy, but they WILL change
# when FairPrice ships new CSS. They live here as named constants, and every
# lookup has a fallback plus a startup assertion so a rebuild fails loudly
# instead of silently producing empty columns.
PRODUCT_SELECTOR = 'div[data-impressiontype="PRODUCT_IMPRESSION"]'
PRICE_CLASS_SUFFIX = "iNLBGt"
NAME_CLASS_SUFFIX = "gpnjpI"
META_CLASS_SUFFIX = "iIDbJm"      # container div: quantity + dietary spans
META_SPAN_SUFFIX = "jkDBep"       # the spans inside that container
DIETARY_SEPARATOR = "dietary-attributes-separator"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

PRICE_RE = re.compile(r"\$\s*([0-9]+(?:\.[0-9]+)?)")
PRODUCT_ID_RE = re.compile(r"-(\d+)/?$")


@dataclass
class Product:
    category: str
    product_id: str
    name: str
    price: str            # raw text as rendered, e.g. "$16.25"
    price_value: float | None
    quantity: str         # "5kg", "400g"; empty when the card omits it
    dietary: str          # "Halal", "Organic", ...; empty when absent
    url: str
    used_fallback: bool = field(default=False, repr=False)


# --------------------------------------------------------------------------
# selector helpers
# --------------------------------------------------------------------------
def find_by_class_suffix(node: Tag, suffix: str, name: str | None = None) -> Tag | None:
    """First descendant with a class *token* ending in `suffix`.

    Token-wise rather than whole-attribute, so a reordered class list still
    matches. `name` optionally restricts the tag ("span"); left open by default
    because the quantity container is a <div> even though CRAWL_INSTRUCT.md
    describes it as a span.
    """
    for el in node.find_all(name or True):
        for token in el.get("class") or ():
            if token.endswith(suffix):
                return el
    return None


def _is_non_price_context(node: Tag) -> bool:
    """Card regions holding a $-amount that is not the current price.

    Two exist: the "Save $0.70" promo badge, which renders *before* the price
    block, and the struck-through original price.
    """
    if "promo-label" in (node.get("data-testid") or ""):
        return True
    return (node.get("aria-label") or "") == "Original price"


def fallback_price(card: Tag) -> str:
    """Recover the current price without the styled-components hash.

    Walks $-amounts in document order, skipping promo badges and the original
    price. The discounted price renders first, so the first survivor is right.
    """
    for text_node in card.find_all(string=PRICE_RE):
        if any(_is_non_price_context(p) for p in text_node.parents if isinstance(p, Tag)):
            continue
        m = PRICE_RE.search(text_node)
        if m:
            return f"${m.group(1)}"
    return ""


def extract_meta(card: Tag) -> tuple[str, str]:
    """(selling quantity, dietary note) from the iIDbJm container.

    The container holds one or two sibling spans with identical classes. The
    dietary one is identified by its separator child -- not by position, since
    quantity is absent on some products. Its text renders as "• Halal", so the
    bullet is stripped. The note is not always "Halal" (Organic, Vegetarian and
    others use the same slot), so the literal text is kept.
    """
    container = find_by_class_suffix(card, META_CLASS_SUFFIX)
    if container is not None:
        spans = container.find_all("span", recursive=False) or container.find_all("span")
    else:
        # Hash changed -- fall back to the inner spans by their own class.
        spans = [
            el for el in card.find_all("span")
            if any(t.endswith(META_SPAN_SUFFIX) for t in el.get("class") or ())
        ]

    quantity = dietary = ""
    for span in spans:
        text = span.get_text(" ", strip=True)
        if span.find(attrs={"data-testid": DIETARY_SEPARATOR}):
            dietary = text.lstrip("•").strip()
        elif not quantity:
            quantity = text
    return quantity, dietary


def extract_product(card: Tag, category: str) -> Product | None:
    link = card.find("a", href=True)
    href = link["href"] if link else ""
    url = urljoin(SITE_ROOT, href) if href else ""

    # data-refid is "<impressionIndex>-<productId>"; the index churns on every
    # page load, so the id after the dash -- which also ends the href -- is the
    # only stable identity.
    m = PRODUCT_ID_RE.search(href)
    if m:
        product_id = m.group(1)
    else:
        refid = card.get("data-refid") or ""
        product_id = refid.rsplit("-", 1)[1] if "-" in refid else ""

    used_fallback = False

    name_el = find_by_class_suffix(card, NAME_CLASS_SUFFIX, "span")
    if name_el is not None:
        name = name_el.get_text(" ", strip=True)
    else:
        img = card.find("img")
        name = (img.get("alt") or img.get("title") or "").strip() if img else ""
        used_fallback = True

    price_el = find_by_class_suffix(card, PRICE_CLASS_SUFFIX, "span")
    if price_el is not None:
        price = price_el.get_text(" ", strip=True)
    else:
        price = fallback_price(card)
        used_fallback = True

    quantity, dietary = extract_meta(card)

    if not name and not price:
        return None

    pm = PRICE_RE.search(price or "")
    return Product(
        category=category,
        product_id=product_id,
        name=name,
        price=price,
        price_value=float(pm.group(1)) if pm else None,
        quantity=quantity,
        dietary=dietary,
        url=url,
        used_fallback=used_fallback,
    )


def category_of(url: str) -> str:
    return urlparse(url).path.rstrip("/").split("/")[-1]


def parse_products(html: str, category: str) -> list[Product]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select(PRODUCT_SELECTOR):
        p = extract_product(card, category)
        if p is not None:
            out.append(p)
    return out


def dedupe(products: list[Product]) -> list[Product]:
    """Keep the first card per (category, product id).

    Each page shows some products twice -- once in a promo carousel, once in the
    grid -- so document-wide selection double-counts without this.
    """
    seen: set[tuple[str, str]] = set()
    out: list[Product] = []
    for p in products:
        key = (p.category, p.product_id or f"{p.name}|{p.price}")
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------
def fetch_static(url: str, timeout: int = 30) -> str:
    """Server-rendered first page. Fast, no browser, ~25 cards."""
    r = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-SG,en;q=0.9",
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.text


def fetch_scrolled(
    url: str,
    *,
    headless: bool = True,
    max_scrolls: int = 400,
    scroll_pause: float = 2.5,
    patience: int = 8,
    verbose: bool = True,
) -> str:
    """Scroll to the bottom until the grid stops growing; return page_source.

    Parsing the finished DOM once is far cheaper than thousands of per-element
    WebDriver round trips. On a plateau it nudges the lazy-load observer (scroll
    up, pause, scroll back down) before giving up.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1440,1000")
    opts.add_argument("--blink-settings=imagesEnabled=false")  # big speedup
    opts.add_argument(f"--user-agent={USER_AGENT}")
    opts.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(url)
        time.sleep(6)  # first client-side render

        previous, stalled = 0, 0
        for i in range(max_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause)
            count = len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_SELECTOR))

            if count > previous:
                previous, stalled = count, 0
                if verbose and (i + 1) % 10 == 0:
                    print(f"    scroll {i + 1}: {count} cards", file=sys.stderr)
                continue

            stalled += 1
            # Re-arm the IntersectionObserver: up, pause, back down, pause.
            driver.execute_script("window.scrollBy(0, -800);")
            time.sleep(2.5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2.5)
            if len(driver.find_elements(By.CSS_SELECTOR, PRODUCT_SELECTOR)) > previous:
                stalled = 0
                continue
            if stalled >= patience:
                if verbose:
                    print(f"    end of list at {count} cards", file=sys.stderr)
                break
        else:
            if verbose:
                print(f"    hit --max-scrolls ({max_scrolls}); may be more",
                      file=sys.stderr)

        return driver.page_source
    except KeyboardInterrupt:
        print("    interrupted; keeping what loaded", file=sys.stderr)
        return driver.page_source
    finally:
        driver.quit()


# --------------------------------------------------------------------------
# per-category worker
# --------------------------------------------------------------------------
def crawl_category(job: dict) -> tuple[str, list[Product], str]:
    """Fetch + parse one category. Runs in its own process.

    Every category gets a fresh interpreter (spawn), so each selenium run drives
    its own Chrome with no shared WebDriver state. Returns the error text rather
    than raising, so one dead category cannot take the pool down with it.
    """
    url = job["url"]
    cat = category_of(url)
    verbose = job["verbose"]
    if verbose:
        print(f"[{cat}] crawling (pid {os.getpid()}) ...", file=sys.stderr)
    try:
        html = (fetch_static(url) if job["engine"] == "requests"
                else fetch_scrolled(url, headless=job["headless"],
                                    max_scrolls=job["max_scrolls"],
                                    scroll_pause=job["scroll_pause"],
                                    patience=job["patience"], verbose=verbose))
    except Exception as exc:
        return cat, [], str(exc)

    return cat, dedupe(parse_products(html, cat)), ""


# --------------------------------------------------------------------------
FIELDS = ["category", "name", "price_value",
          "quantity", "dietary"]


def write_csv(products: list[Product], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for p in products:
            w.writerow(asdict(p))


def write_json(products: list[Product], path: str) -> None:
    rows = [{k: v for k, v in asdict(p).items() if k in FIELDS} for p in products]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", action="append", default=None,
                    help="category page (repeatable); defaults to all 5 in CRAWL_INSTRUCT.md")
    ap.add_argument("--engine", choices=["selenium", "requests"], default="selenium",
                    help="selenium scrolls for every product (default); requests "
                         "grabs only the server-rendered first page")
    ap.add_argument("--out", default="data/output_raw/raw_matched_food_prices.csv")
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--max-scrolls", type=int, default=400)
    ap.add_argument("--scroll-pause", type=float, default=2.5)
    ap.add_argument("--patience", type=int, default=8,
                    help="plateau rounds (each with a nudge) before giving up")
    ap.add_argument("--jobs", type=int, default=0,
                    help="worker processes; 0 (default) runs every category at once")
    ap.add_argument("--no-headless", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    urls = args.url or CATEGORIES
    verbose = not args.quiet
    all_products: list[Product] = []

    jobs = [
        {
            "url": url,
            "engine": args.engine,
            "headless": not args.no_headless,
            "max_scrolls": args.max_scrolls,
            "scroll_pause": args.scroll_pause,
            "patience": args.patience,
            "verbose": verbose,
        }
        for url in urls
    ]
    workers = args.jobs if args.jobs > 0 else len(jobs)
    workers = max(1, min(workers, len(jobs)))

    if verbose:
        print(f"crawling {len(jobs)} categories across {workers} process(es)",
              file=sys.stderr)

    # spawn, not fork: a forked Chrome/WebDriver child is not safe, and spawn is
    # already the macOS default -- pinning it keeps Linux behaving the same.
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        # imap keeps results in category order, so the CSV does not reshuffle
        # itself depending on which crawl happened to finish first.
        for cat, found, error in pool.imap(crawl_category, jobs):
            if error:
                print(f"[{cat}] FAILED: {error}", file=sys.stderr)
                continue
            all_products.extend(found)
            if verbose:
                q = sum(bool(p.quantity) for p in found)
                d = sum(bool(p.dietary) for p in found)
                print(f"[{cat}] {len(found)} products  ({q} with quantity, {d} with dietary note)",
                      file=sys.stderr)

    if not all_products:
        print(f"No products matched {PRODUCT_SELECTOR!r}. The markup probably "
              "changed -- re-check CRAWL_INSTRUCT.md against the live DOM.",
              file=sys.stderr)
        return 1

    # Fail loudly if a redeploy silently broke the hashes.
    fallbacks = sum(p.used_fallback for p in all_products)
    if fallbacks:
        print(f"WARNING: {fallbacks}/{len(all_products)} cards missed the "
              f'"{NAME_CLASS_SUFFIX}"/"{PRICE_CLASS_SUFFIX}" class hashes and used '
              "the fallback path. FairPrice likely redeployed its CSS -- update "
              "the suffix constants at the top of this file.", file=sys.stderr)
    if not any(p.quantity for p in all_products):
        print(f'WARNING: no card yielded a selling quantity; the "{META_CLASS_SUFFIX}" '
              "container hash has probably changed.", file=sys.stderr)

    write_csv(all_products, args.out)
    if args.json_out:
        write_json(all_products, args.json_out)

    if verbose:
        print(f"\n{len(all_products)} products -> {args.out}"
              + (f" (+{args.json_out})" if args.json_out else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
