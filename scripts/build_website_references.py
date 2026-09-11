#!/usr/bin/env python3
"""Build VEXUM's 1,000-site web-design reference index.

A rank is an editorially pinned seed list. B-Z are ranked with VEXUM's own
scoring over factual public site names/URLs discovered from live gallery listing
pages. Screenshots and third-party descriptions are never copied into this repo.
"""

from __future__ import annotations

import csv
import json
import re
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "references" / "websites"
A_FILE = OUT_DIR / "A.csv"
BASE = "https://www.a1.gallery"
TARGET = 1000
USER_AGENT = "Mozilla/5.0 VEXUM-Design-Library/1.0"

# Purpose-first sources. Templates are deliberately not included.
TYPE_SOURCES = [
    ("landing", "product", 4.0),
    ("agency", "brand", 5.0),
    ("portfolio", "portfolio", 5.0),
    ("shop", "ecommerce", 3.0),
    ("one-page", "landing", 3.0),
    ("directory", "editorial", 2.0),
    ("blog", "editorial", 2.0),
    ("waitlist", "product", 2.0),
]

# Used only if the purpose pages do not yield enough unique domains.
FALLBACK_CATEGORIES = [
    ("design", "design", 5.0),
    ("ai", "ai", 4.0),
    ("software", "software", 4.0),
    ("development", "development", 3.0),
    ("technology", "technology", 3.0),
    ("productivity", "productivity", 3.0),
    ("finance", "finance", 2.0),
    ("business", "business", 2.0),
    ("data", "data", 3.0),
    ("health", "health", 2.0),
    ("typography", "typography", 4.0),
    ("video", "video", 3.0),
]

EXCLUDED_HOSTS = {
    "a1.gallery", "www.a1.gallery",
    "framer.com", "www.framer.com", "framer.link",
    "bryntaylor.co.uk", "www.bryntaylor.co.uk",
    "freelancethings.co", "www.freelancethings.co",
    "goodgarms.com", "www.goodgarms.com",
    "twitter.com", "x.com", "linkedin.com", "www.linkedin.com",
    "instagram.com", "www.instagram.com", "youtube.com", "www.youtube.com",
    "lemonsqueezy.com", "www.lemonsqueezy.com", "buy.polar.sh",
}

# Higher weights mean greater reuse value for VEXUM's desired modern web direction.
SIGNAL_WEIGHTS = {
    "interactive": 7.0,
    "scroll animation": 6.0,
    "animated": 5.0,
    "3d": 5.0,
    "experimental": 5.0,
    "typographic": 4.5,
    "editorial": 4.0,
    "big type": 3.0,
    "brutalist": 3.0,
    "video": 2.5,
    "minimal": 2.5,
    "gradients": 2.0,
    "colourful": 2.0,
    "colorful": 2.0,
    "grid": 2.0,
    "photography": 1.5,
    "dark": 1.0,
}


@dataclass
class Candidate:
    name: str
    url: str
    focus: str
    score: float
    source_order: int


def normalize_url(raw: str) -> str | None:
    raw = raw.strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        p = urlparse(raw)
    except ValueError:
        return None
    if p.scheme not in {"http", "https"} or not p.netloc:
        return None
    host = p.netloc.lower().split("@")[-1].split(":")[0]
    if host in EXCLUDED_HOSTS or host.endswith(".a1.gallery"):
        return None
    path = re.sub(r"/{2,}", "/", p.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunparse(("https", p.netloc.lower(), path, "", "", ""))


def domain_key(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def is_detail_link(href: str) -> bool:
    try:
        p = urlparse(urljoin(BASE, href))
    except ValueError:
        return False
    return p.netloc.endswith("a1.gallery") and p.path.startswith("/website/")


def signal_score(text: str) -> float:
    t = " ".join(text.lower().replace("–", "-").split())
    return sum(weight for keyword, weight in SIGNAL_WEIGHTS.items() if keyword in t)


def get(session: requests.Session, url: str) -> requests.Response:
    last: Exception | None = None
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


def max_page(soup: BeautifulSoup) -> int:
    """Read explicit ?page=N pagination; avoids confusing 'Next.js' with Next."""
    pages = [1]
    for a in soup.find_all("a", href=True):
        try:
            q = parse_qs(urlparse(urljoin(BASE, a["href"])).query)
            if "page" in q:
                pages.append(int(q["page"][0]))
        except (ValueError, TypeError, IndexError):
            pass
    return max(pages)


def parse_cards(
    soup: BeautifulSoup,
    page_url: str,
    focus: str,
    base_score: float,
    order_start: int,
    page_no: int,
) -> tuple[list[Candidate], int]:
    anchors = soup.find_all("a", href=True)
    rows: list[Candidate] = []
    order = order_start

    for i, a in enumerate(anchors):
        href = a.get("href", "")
        if not is_detail_link(href):
            continue

        name = " ".join(a.get_text(" ", strip=True).split())
        if not name:
            continue  # image-link duplicate; the following text-link carries the name

        external: str | None = None
        for b in anchors[i + 1 : i + 5]:
            if is_detail_link(b.get("href", "")):
                break
            candidate_url = normalize_url(urljoin(page_url, b.get("href", "")))
            if candidate_url:
                external = candidate_url
                break
        if not external:
            continue

        img = a.find_previous("img")
        alt = img.get("alt", "") if img else ""
        freshness = max(0.0, 2.0 - (page_no - 1) * 0.08)
        score = base_score + signal_score(f"{name} {alt}") + freshness
        rows.append(Candidate(name, external, focus, round(score, 3), order))
        order += 1

    return rows, order


def crawl_listing(
    session: requests.Session,
    kind: str,
    slug: str,
    focus: str,
    base_score: float,
    order_start: int,
) -> tuple[list[Candidate], int]:
    base_url = f"{BASE}/{kind}/{slug}"
    first = get(session, base_url)
    first_soup = BeautifulSoup(first.text, "html.parser")
    last_page = min(max_page(first_soup), 50)

    rows, order = parse_cards(first_soup, base_url, focus, base_score, order_start, 1)
    all_rows = list(rows)

    for page in range(2, last_page + 1):
        page_url = f"{base_url}?page={page}"
        try:
            response = get(session, page_url)
        except RuntimeError as exc:
            print(f"warning: {exc}", file=sys.stderr)
            break
        soup = BeautifulSoup(response.text, "html.parser")
        page_rows, order = parse_cards(soup, page_url, focus, base_score, order, page)
        all_rows.extend(page_rows)
        time.sleep(0.18)

    return all_rows, order


def load_pinned_a() -> list[dict[str, str]]:
    with A_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 39:
        raise RuntimeError(f"A.csv must contain exactly 39 sites; found {len(rows)}")
    rows.sort(key=lambda row: int(row["priority"]))
    return rows


def rank_for_priority(priority: int) -> str:
    cursor = 1
    for i, rank in enumerate(string.ascii_uppercase):
        count = 39 if i < 12 else 38
        if cursor <= priority < cursor + count:
            return rank
        cursor += count
    raise ValueError(priority)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pinned = load_pinned_a()
    pinned_domains = {domain_key(row["url"]) for row in pinned}

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"})

    candidates: dict[str, Candidate] = {}
    source_order = 1

    def merge(rows: list[Candidate]) -> None:
        for row in rows:
            key = domain_key(row.url)
            if key in pinned_domains:
                continue
            old = candidates.get(key)
            if old is None or (row.score, -row.source_order) > (old.score, -old.source_order):
                candidates[key] = row

    for slug, focus, base_score in TYPE_SOURCES:
        try:
            rows, source_order = crawl_listing(
                session, "type", slug, focus, base_score, source_order
            )
        except RuntimeError as exc:
            print(f"warning: {exc}", file=sys.stderr)
            continue
        merge(rows)
        print(f"type/{slug}: {len(rows)} raw; {len(candidates)} unique")

    needed = TARGET - len(pinned)
    if len(candidates) < needed:
        for slug, focus, base_score in FALLBACK_CATEGORIES:
            try:
                rows, source_order = crawl_listing(
                    session, "category", slug, focus, base_score, source_order
                )
            except RuntimeError as exc:
                print(f"warning: {exc}", file=sys.stderr)
                continue
            merge(rows)
            print(f"category/{slug}: {len(rows)} raw; {len(candidates)} unique")
            if len(candidates) >= needed + 50:
                break

    ordered = sorted(candidates.values(), key=lambda c: (-c.score, c.source_order, c.name.lower()))
    if len(ordered) < needed:
        raise RuntimeError(f"only {len(ordered)} unique candidates; need {needed}")

    final_rows: list[dict[str, str | int]] = []
    for row in pinned:
        final_rows.append({
            "priority": int(row["priority"]),
            "rank": "A",
            "name": row["name"],
            "url": row["url"],
            "focus": row.get("focus", "design"),
        })

    for priority, candidate in enumerate(ordered[:needed], start=40):
        final_rows.append({
            "priority": priority,
            "rank": rank_for_priority(priority),
            "name": candidate.name,
            "url": candidate.url,
            "focus": candidate.focus,
        })

    if len(final_rows) != TARGET:
        raise RuntimeError(f"expected {TARGET} rows, got {len(final_rows)}")
    domains = [domain_key(str(row["url"])) for row in final_rows]
    if len(domains) != len(set(domains)):
        raise RuntimeError("duplicate domains detected")
    if [int(r["priority"]) for r in final_rows] != list(range(1, TARGET + 1)):
        raise RuntimeError("priority sequence must be 1..1000")

    fields = ["priority", "rank", "name", "url", "focus"]
    grouped = {r: [] for r in string.ascii_uppercase}
    for row in final_rows:
        grouped[str(row["rank"])].append(row)

    for rank, rows in grouped.items():
        expected = 39 if rank <= "L" else 38
        if len(rows) != expected:
            raise RuntimeError(f"rank {rank}: expected {expected}, got {len(rows)}")
        with (OUT_DIR / f"{rank}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    with (OUT_DIR / "all.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(final_rows)

    metadata = {
        "count": TARGET,
        "rank_counts": {rank: len(rows) for rank, rows in grouped.items()},
        "ranking": "A is editorially pinned; B-Z use VEXUM scoring over public live-site listings",
        "signals": SIGNAL_WEIGHTS,
        "source_policy": "Only factual public site names/URLs are stored; no screenshots or source descriptions are copied.",
    }
    with (OUT_DIR / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"wrote {TARGET} unique website references")


if __name__ == "__main__":
    main()
