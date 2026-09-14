#!/usr/bin/env python3
"""Create feature-first reference files from captured Awwwards tag evidence."""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITES = ROOT / "references" / "websites"
OUT = ROOT / "references" / "features"

FEATURES = {
    "cutin-and-page-transition": ("カットイン・画面遷移", {"Transitions", "Animation"}),
    "fixed-ui-and-navigation": ("固定UI・ナビゲーション候補", {"Header Design", "Footer Design", "Navigation Menu", "Menu - Horizontal", "Menu - Vertical", "Unusual Navigation"}),
    "background-motion": ("背景演出候補", {"WebGL", "GLSL", "3D", "Three.js", "Big Background Images"}),
    "scroll-driven": ("スクロール連動", {"Scrolling", "Locomotive Scroll", "Infinite Scroll", "Parallax"}),
    "microinteractions": ("マイクロインタラクション", {"Microinteractions", "Interaction Design", "Gestures / Interaction"}),
    "filters-and-effects": ("フィルター・視覚エフェクト", {"Filters and Effects", "After Effects"}),
    "media-and-sound": ("映像・音声", {"Video", "Photo & Video", "Sound-Audio", "Music & Sound"}),
    "gallery-and-browsing": ("ギャラリー・閲覧UI", {"Gallery"}),
    "responsive": ("レスポンシブ対応", {"Responsive", "Responsive Design"}),
    "forms-and-input": ("フォーム・入力UI", {"Forms and Input"}),
}
FIELDS = ["priority", "rank", "name", "url", "focus", "feature", "evidence", "source", "source_page"]


def main():
    with (WEBSITES / "all.csv").open(encoding="utf-8", newline="") as f:
        catalog = list(csv.DictReader(f))
    with (WEBSITES / "awwwards-additions.json").open(encoding="utf-8") as f:
        tagged = {item["url"]: item for item in json.load(f)}

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.csv"):
        old.unlink()

    grouped = defaultdict(list)
    unknown = []
    for row in catalog:
        item = tagged.get(row["url"])
        if not item:
            unknown.append({**row, "feature": "未判定", "evidence": "機能タグ未取得"})
            continue
        tags = set(item["tags"])
        for slug, (label, rule) in FEATURES.items():
            evidence = sorted(tags & rule)
            if evidence:
                grouped[slug].append({**row, "feature": label, "evidence": " / ".join(evidence)})

    for slug, (label, _) in FEATURES.items():
        with (OUT / f"{slug}.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader(); writer.writerows(grouped[slug])
    with (OUT / "unknown.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(unknown)

    summary = {
        "method": "Awwwardsの作品タグと明示的に一致した機能だけを抽出。タグ未取得の既存サイトは未判定として分離。",
        "features": {slug: {"label": label, "count": len(grouped[slug])} for slug, (label, _) in FEATURES.items()},
        "unknown_count": len(unknown),
    }
    (OUT / "metadata.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = "# Feature-first reference index\n\n順位（`priority` / `rank`）を残したまま、実装したいUI機能から参照サイトを探せる一覧です。\n\n"
    readme += "| ファイル | 機能 | 抽出根拠 |\n| --- | --- | --- |\n"
    for slug, (label, tags) in FEATURES.items():
        readme += f"| `{slug}.csv` | {label} | {' / '.join(sorted(tags))} |\n"
    readme += "| `unknown.csv` | 未判定 | 機能タグを取得していない既存サイト。機能がないという意味ではありません。 |\n\n"
    readme += "`evidence` 列は機能を断定する説明ではなく、公開カタログ上のタグ一致です。実装前にリンク先を確認してください。\n"
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
