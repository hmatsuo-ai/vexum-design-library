#!/usr/bin/env python3
"""Build a 1,000-site web design reference index.

A rank is an editorially pinned seed list. B-Z are refreshed from public A1 Gallery
listing pages, but only factual site names/URLs plus VEXUM's own ranking are stored.
No screenshots or source descriptions are copied into this repository.
"""

from __future__ import annotations

import csv
import json
import re
import string
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "references" / "websites"
A_FILE = OUT_DIR / "A.csv"
BASE = "https://www.a1.gallery"
TARGET = 1000
USER_AGENT = "VEXUM-Design-Library/1.0 (+https://github.com/hmatsuo-ai/vexum-design-library)"

# Type pages are preferred because they partition the gallery by site purpose better
# than broad style/category filters. Category pages are a fallback/top-up source.
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

CATEGORY_SOURCES = [
    ("design", "design", 5.0),
    ("ai", "ai", 4.0),
    ("software", "software", 4.0),
    ("development", "development", 3.0),
    ("technology", "technology", 3.0),
    ("marketing", "marketing", 2.0),
    ("productivity", "productivity", 3.0),
    ("finance", "finance", 2.0),
    ("business", "business", 2.0),
    ("health", "health", 2.0),
    ("data", "data", 3.0),
    ("web3-crypto", "web3", 1.0),
    ("education", "education", 2.0),
    ("entertainment", "entertainment", 2.0),
    ("fashion", "fashion", 2.0),
    ("food-drink", "food", 2.0),
    ("hardware", "hardware", 2.0),
    ("homeware", "homeware", 2.0),
    ("music", "music", 2.0),
    ("photography", "photography", 2.0),
    ("professional-services", "services", 2.0),
    ("real-estate", "real-estate", 2.0),
    ("retail", "retail", 2.0),
    ("science", "science", 2.0),
    ("security", "security", 2.0),
    ("social", "social", 2.0),
    ("sports", "sports", 2.0),
    ("transport", "transport", 2.0),
    ("travel", "travel", 2.0),
    ("typography", "typography", 4.0),
    ("venture-capital", "venture-capital", 2.0),
    ("video", "video", 3.0),
    ("writing", "writing", 2.0),
]

# We explicitly exclude gallery infrastructure, template stores, sponsors and social links.
EXCLUDED_HOSTS = {
    "a1.gallery",
    "www.a1.gallery",
    "framer.com",
    "www.framer.com",
    "framer.link",
    "bryntaylor.co.uk",
    "www.bryntaylor.co.uk",
    "freelancethings.co",
    "www.freelancethings.co",
    "goodgarms.com",
    "www.goodgarms.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "www.linkedin.com",
    "instagram.com",
    "www.instagram.com",
    "youtube.com",
    "www.youtube.com",
    "lemonsqueezy.com",
    "www.lemonsqueezy.com",
    "buy.polar.sh",
}

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
    "light": 0.5,
}


@dataclass
class Candidate:
    name: str
    url: str
    focus: str
    score: float
    source_order: int
    source: str


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
    host = p.netloc.lower().split("@")[-1]
    host = host.split(":")[0]
    if host in EXCLUDED_HOSTS or host.endswith(".a1.gallery"):
        return None
    # Strip tracking/query/fragment. Preserve meaningful path because some references are microsites.
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


def fetch(session: requests.Session, url: str) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return r
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def extract_page(
    session: requests.Session,
    url: str,
    focus: str,
    base_score: float,
    order_start: int,
    source_label: str,
) -> tuple[list[Candidate], bool, int]:
    r = fetch(session, url)
    soup = BeautifulSoup(r.text, "html.parser")
    anchors = soup.find_all("a", href=True)
    found: list[Candidate] = []
    order = order_start

    for i, a in enumerate(anchors):
        href = a.get("href", "")
        if not is_detail_link(href):
            continue

        name = " ".join(a.get_text(" ", strip=True).split())
        if not name:
            slug = urlparse(urljoin(BASE, href)).path.rsplit("/", 1)[-1]
            name = slug.replace("-", " ").title()

        external: str | None = None
        # On A1 cards, the direct-site arrow link immediately follows the detail link.
        # Limit the scan so navigation/footer links can never be paired with a card.
        for b in anchors[i + 1 : i + 5]:
            bhref = b.get("href", "")
            if is_detail_link(bhref):
                break
            candidate_url = normalize_url(urljoin(url, bhref))
            if candidate_url:
                external = candidate_url
                break
        if not external:
            continue

        # Use nearby image alt text only as a ranking signal; it is never written to the repo.
        img = a.find_previous("img")
        alt = img.get("alt", "") if img else ""
        score = base_score + signal_score(f"{name} {alt}")
        # Earlier gallery pages are fresher. This is a tie-break signal, not a quality claim.
        page_match = re.search(r"[?&]page=(\d+)", url)
        page_no = int(page_match.group(1)) if page_match else 1
        score += max(0.0, 2.0 - (page_no - 1) * 0.08)

        found.append(
            Candidate(
                name=name,
                url=external,
                focus=focus,
                score=round(score, 3),
                source_order=order,
                source=source_label,
            )
        )
        order += 1

    # Stop at the last page by checking for a visible Next pagination link.
    has_next = False
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split()).lower()
        if text.startswith("next"):
            has_next = True
            break

    return found, has_next, order


def crawl_source(
    session: requests.Session,
    kind: str,
    slug: str,
    focus: str,
    base_score: float,
    order_start: int,
) -> tuple[list[Candidate], int]:
    all_rows: list[Candidate] = []
    order = order_start
    for page in range(1, 60):
        url = f"{BASE}/{kind}/{slug}"
        if page > 1:
            url += f"?page={page}"
        try:
            rows, has_next, order = extract_page(
                session, url, focus, base_score, order, f"{kind}/{slug}"
            )
        except RuntimeError as exc:
            print(f"warning: {exc}", file=sys.stderr)
            break
        all_rows.extend(rows)
        if not has_next:
            break
        time.sleep(0.12)
    return all_rows, order


def load_pinned_a() -> list[dict[str, str]]:
    if not A_FILE.exists():
        raise RuntimeError("references/websites/A.csv is required as the pinned A-rank seed")
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
            existing = candidates.get(key)
            if existing is None or (row.score, -row.source_order) > (
                existing.score,
                -existing.source_order,
            ):
                candidates[key] = row

    for slug, focus, base_score in TYPE_SOURCES:
        rows, source_order = crawl_source(
            session, "type", slug, focus, base_score, source_order
        )
        merge(rows)
        print(f"type/{slug}: +{len(rows)} raw, {len(candidates)} unique candidates")

    # Category pages top up the set and improve scores for sites appearing in strong
    # design-centric categories. Stop once we have a healthy buffer over the target.
    for slug, focus, base_score in CATEGORY_SOURCES:
        rows, source_order = crawl_source(
            session, "category", slug, focus, base_score, source_order
        )
        merge(rows)
        print(f"category/{slug}: +{len(rows)} raw, {len(candidates)} unique candidates")
        if len(candidates) >= 1100:
            break

    needed = TARGET - len(pinned)
    ordered = sorted(
        candidates.values(), key=lambda c: (-c.score, c.source_order, c.name.lower())
    )
    if len(ordered) < needed:
        raise RuntimeError(f"only {len(ordered)} unique candidates; need {needed}")
    selected = ordered[:needed]

    final_rows: list[dict[str, str | int]] = []
    for row in pinned:
        priority = int(row["priority"])
        final_rows.append(
            {
                "priority": priority,
                "rank": "A",
                "name": row["name"],
                "url": row["url"],
                "focus": row.get("focus", "design"),
            }
        )

    for offset, candidate in enumerate(selected, start=40):
        final_rows.append(
            {
                "priority": offset,
                "rank": rank_for_priority(offset),
                "name": candidate.name,
                "url": candidate.url,
                "focus": candidate.focus,
            }
        )

    # Hard validation before writing anything.
    if len(final_rows) != TARGET:
        raise RuntimeError(f"expected {TARGET} rows, got {len(final_rows)}")
    domains = [domain_key(str(row["url"])) for row in final_rows]
    if len(domains) != len(set(domains)):
        raise RuntimeError("duplicate domains detected in final ranking")
    if [int(r["priority"]) for r in final_rows] != list(range(1, TARGET + 1)):
        raise RuntimeError("priority sequence is not contiguous 1..1000")

    fieldnames = ["priority", "rank", "name", "url", "focus"]
    by_rank: dict[str, list[dict[str, str | int]]] = {r: [] for r in string.ascii_uppercase}
    for row in final_rows:
        by_rank[str(row["rank"])].append(row)

    for rank, rows in by_rank.items():
        expected = 39 if rank <= "L" else 38
        if len(rows) != expected:
            raise RuntimeError(f"rank {rank}: expected {expected}, got {len(rows)}")
        path = OUT_DIR / f"{rank}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    with (OUT_DIR / "all.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(final_rows)

    metadata = {
        "count": TARGET,
        "rank_counts": {rank: len(rows) for rank, rows in by_rank.items()},
        "ranking": "A is editorially pinned; B-Z use VEXUM scoring over public live-site listings",
        "signals": SIGNAL_WEIGHTS,
        "source_policy": "Only factual public site names/URLs are stored; no screenshots or source descriptions are copied.",
    }
    with (OUT_DIR / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"wrote {TARGET} unique website references to {OUT_DIR}")


if __name__ == "__main__":
    main()
