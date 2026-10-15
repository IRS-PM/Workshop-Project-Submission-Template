#!/usr/bin/env python3
"""
FairPrice search crawler for the unmatched head terms.

The category crawl (fairprice_crawler.py) covers the five aisles in
CRAWL_INSTRUCT.md; whatever nutrient row it cannot price is summarised by
process_price.ipynb in data/output_raw/frequent_unmatched_food.csv as
(head_term, rows). This script goes after those terms one by one:

    https://www.fairprice.com.sg/search?query=<term>

and parses the results with the same DOM contract -- the search grid renders
the identical PRODUCT_IMPRESSION cards, so extraction is imported wholesale
from fairprice_crawler rather than restated here.

Unlike a category page, the search grid's first ~20 cards are server-rendered
and they are the ones that matter (results past the first screen have already
drifted off the query), so this runs on requests alone: no Chrome, no scroll.

A search card carries no aisle, so -- per the "For crawling unmatched" section
of CRAWL_INSTRUCT.md -- each result's own page is fetched and its breadcrumb
read for the category. That is one extra request per product; pages are cached
per URL for the run, and --no-category skips the pass entirely.

Usage:
    python3 fairprice_unmatched_crawler.py                  # every term in the CSV
    python3 fairprice_unmatched_crawler.py --min-rows 20    # only the frequent ones
    python3 fairprice_unmatched_crawler.py --term sandwich --term cereals
    python3 fairprice_unmatched_crawler.py --resume         # keep what is already out
    python3 fairprice_unmatched_crawler.py --no-category    # prices only, one request per term
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from fairprice_crawler import USER_AGENT, dedupe, parse_products

SEARCH_URL = "https://www.fairprice.com.sg/search?query={}"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-SG,en;q=0.9",
}

# CRAWL_INSTRUCT.md, "For crawling unmatched": every crumb of the product page
# breadcrumb is an <a> sharing this styled-components hash. The crumbs run
# Home > aisle > sub-aisle > product ("/", "/category/snacks--confectionery",
# "/category/snacks", "/category/dips"), so the FIRST /category/ link is the
# top-level aisle -- the same value fairprice_crawler.py writes for a category
# crawl, which is what makes the two CSVs comparable.
BREADCRUMB_CLASS_SUFFIX = "cuemoG"
CATEGORY_HREF_RE = re.compile(r"^/category/([^/?#]+)")

# term/occurrences carried through so a row still says which unmatched food it
# was fetched for, and how much of the gap that food accounts for. Column order
# matches the existing data/output_raw/raw_unmatched_food_prices.csv so
# --resume can append to a file an earlier run left behind.
FIELDS = ["term", "occurrences", "rank", "product_id", "category", "name",
          "price_value", "quantity", "dietary"]


def read_terms(path: str, min_rows: int) -> list[tuple[str, int]]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [
            (r["head_term"].strip(), int(r["rows"]))
            for r in csv.DictReader(fh)
        ]
    return [(name, n) for name, n in rows if name and n >= min_rows]


def fetch(url: str, session: requests.Session, timeout: int, retries: int) -> str:
    last = None
    for attempt in range(retries + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # transient 5xx / timeout: back off and retry
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last  # type: ignore[misc]


def search(term: str, session: requests.Session, timeout: int, retries: int) -> str:
    return fetch(SEARCH_URL.format(quote_plus(term)), session, timeout, retries)


def parse_category(html: str) -> tuple[str, bool]:
    """(top-level aisle, used_fallback) from a product page's breadcrumb.

    Returns "" for a page that has no breadcrumb at all -- delisted products
    and some marketplace listings render without one. The fallback flag says
    the class hash no longer matched and plain /category/ anchors were used
    instead, so a redeploy shows up in the run summary rather than silently
    emptying the column.
    """
    soup = BeautifulSoup(html, "lxml")
    anchors = [
        a for a in soup.find_all("a", href=True)
        if any(t.endswith(BREADCRUMB_CLASS_SUFFIX) for t in a.get("class") or ())
    ]
    used_fallback = False
    if not anchors:
        anchors = soup.find_all("a", href=True)
        used_fallback = True

    for a in anchors:
        m = CATEGORY_HREF_RE.match(a["href"].strip())
        if m:
            return m.group(1), used_fallback
    return "", False


class CategoryLookup:
    """Product URL -> top-level category, fetched at most once per URL per run.

    Roughly one result in five is a repeat across terms ("milk" and "cheese"
    both surface the same carton) and a product page is ~300KB, so the cache is
    what keeps this second pass affordable. Two workers can still race onto the
    same cold URL; that costs one duplicate fetch and is cheaper than holding a
    lock across the network.
    """

    def __init__(self, timeout: int, retries: int, delay: float) -> None:
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self.hits = 0        # rows answered from cache
        self.failed = 0      # product page never loaded
        self.missing = 0     # page loaded, no breadcrumb on it
        self.fallbacks = 0   # breadcrumb found only via the fallback path

    def __call__(self, url: str, session: requests.Session) -> str:
        if not url:
            return ""
        with self._lock:
            if url in self._cache:
                self.hits += 1
                return self._cache[url]

        try:
            html = fetch(url, session, self.timeout, self.retries)
        except Exception:
            with self._lock:
                self.failed += 1
            return ""

        category, used_fallback = parse_category(html)
        with self._lock:
            self._cache[url] = category
            if used_fallback and category:
                self.fallbacks += 1
            if not category:
                self.missing += 1

        time.sleep(self.delay)
        return category


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--terms-csv", default="data/output_raw/frequent_unmatched_food.csv",
                    help="input: the name/occurrences table (default: %(default)s)")
    ap.add_argument("--term", action="append", default=None,
                    help="search this term instead of reading the CSV (repeatable)")
    ap.add_argument("--min-rows", type=int, default=0,
                    help="skip terms accounting for fewer than N unmatched rows")
    ap.add_argument("--out", default="data/output_raw/raw_unmatched_food_prices.csv")
    ap.add_argument("--top", type=int, default=0,
                    help="keep only the first N results per term (0 = all)")
    ap.add_argument("--jobs", type=int, default=6, help="concurrent searches")
    ap.add_argument("--delay", type=float, default=0.35,
                    help="pause between requests within a worker")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--no-category", action="store_true",
                    help="leave the category column empty instead of fetching "
                         "each product page for its breadcrumb")
    ap.add_argument("--resume", action="store_true",
                    help="append, skipping terms already present in --out")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    verbose = not args.quiet

    if args.term:
        terms = [(t, 0) for t in args.term]
    else:
        terms = read_terms(args.terms_csv, args.min_rows)

    done: set[str] = set()
    if args.resume and os.path.exists(args.out):
        with open(args.out, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            # appending under a different header would silently misalign every
            # column, so refuse rather than corrupt an existing crawl
            if reader.fieldnames and reader.fieldnames != FIELDS:
                print(f"--resume: {args.out} has columns {reader.fieldnames}; "
                      f"this build writes {FIELDS}. Re-crawl to a new --out.",
                      file=sys.stderr)
                return 1
            done = {r["term"] for r in reader}
        terms = [(t, n) for t, n in terms if t not in done]
        if verbose:
            print(f"resuming: {len(done)} terms already crawled, {len(terms)} left",
                  file=sys.stderr)

    if not terms:
        print("nothing to crawl", file=sys.stderr)
        return 0

    append = args.resume and done
    fh = open(args.out, "a" if append else "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
    if not append:
        writer.writeheader()

    # one lock for the shared file: rows are written as each term lands, so an
    # interrupted run keeps everything crawled up to that point
    lock = threading.Lock()
    local = threading.local()
    counts = {"terms": 0, "rows": 0, "empty": 0, "failed": 0, "categorised": 0}
    lookup = CategoryLookup(args.timeout, args.retries, args.delay)

    def crawl(job: tuple[str, int]) -> None:
        term, occurrences = job
        session = getattr(local, "session", None)
        if session is None:
            session = local.session = requests.Session()

        try:
            html = search(term, session, args.timeout, args.retries)
        except Exception as exc:
            with lock:
                counts["failed"] += 1
            print(f"[{term}] FAILED: {exc}", file=sys.stderr)
            return

        # parse_products stores the search term in Product.category (it is what
        # keys dedupe here); the real aisle comes off each product's own page.
        products = dedupe(parse_products(html, term))
        if args.top:
            products = products[: args.top]

        # done before the writer lock: this is a page fetch per product and
        # must not hold every other worker out of the CSV while it waits
        categories = ["" if args.no_category else lookup(p.url, session)
                      for p in products]

        with lock:
            for rank, (p, category) in enumerate(zip(products, categories), start=1):
                writer.writerow({
                    "term": term,
                    "occurrences": occurrences,
                    "rank": rank,
                    "product_id": p.product_id,
                    "category": category,
                    "name": p.name,
                    "price_value": p.price_value,
                    "quantity": p.quantity,
                    "dietary": p.dietary,
                })
            fh.flush()
            counts["terms"] += 1
            counts["rows"] += len(products)
            counts["categorised"] += sum(bool(c) for c in categories)
            if not products:
                counts["empty"] += 1
            if verbose and counts["terms"] % 25 == 0:
                print(f"  {counts['terms']}/{len(terms)} terms, "
                      f"{counts['rows']} rows", file=sys.stderr)

        time.sleep(args.delay)

    if verbose:
        print(f"searching {len(terms)} terms across {args.jobs} workers -> {args.out}",
              file=sys.stderr)
        if not args.no_category:
            print("  (+1 product page per result for its category breadcrumb)",
                  file=sys.stderr)

    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(crawl, terms))
    except KeyboardInterrupt:
        print("interrupted; keeping what was written", file=sys.stderr)
    finally:
        fh.close()

    if verbose:
        print(f"\n{counts['rows']} listings for {counts['terms']} terms -> {args.out}")
        print(f"terms with no result: {counts['empty']}; failed: {counts['failed']}")
        if not args.no_category:
            print(f"category: {counts['categorised']}/{counts['rows']} rows "
                  f"({lookup.hits} from cache, {lookup.missing} pages with no "
                  f"breadcrumb, {lookup.failed} unreachable)")

    # Fail loudly if a redeploy moved the breadcrumb hash, the same way the
    # category crawler does for its name/price hashes.
    if not args.no_category and counts["rows"]:
        if not counts["categorised"]:
            print(f'WARNING: no row got a category; the "{BREADCRUMB_CLASS_SUFFIX}" '
                  "breadcrumb hash has probably changed -- re-check the "
                  '"For crawling unmatched" section of CRAWL_INSTRUCT.md '
                  "against the live DOM.", file=sys.stderr)
        elif lookup.fallbacks:
            print(f"WARNING: {lookup.fallbacks} product pages missed the "
                  f'"{BREADCRUMB_CLASS_SUFFIX}" class and used the fallback path; '
                  "FairPrice likely redeployed its CSS -- update "
                  "BREADCRUMB_CLASS_SUFFIX.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
