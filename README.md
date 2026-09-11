# VEXUM Design Library

VEXUMでWebサイトやLP、教材、業務画面を設計するときに参照するためのデザインリファレンス集です。

## Web reference ranking

`references/websites/` に、実在するデザイン参考サイトを **1,000件** 保存します。

- **priority**: 1（最優先）〜1000
- **rank**: A（最優先）〜Z（相対的に低優先）の26段階
- 1ランクあたり約38〜39件
- 同一サイトは原則1件に正規化
- テンプレート販売ページ、スポンサー枠、閉鎖サイト、明らかな低品質サイトは除外

### ランクの判断軸

VEXUMでの再利用価値を基準に、以下を総合評価します。

1. レイアウト構成の完成度・独自性
2. スクロール／トランジション／マイクロインタラクション
3. タイポグラフィと情報階層
4. 色・余白・背景表現
5. 実装に落とし込みやすい再利用性
6. 現代性と視覚的な完成度

Aは「最初に見るべき」、Zは「用途が合えば参照する」という相対順位です。Zも収録基準を満たした参考サイトであり、品質が低いという意味ではありません。

## Sources

主な発見元は、A1 Gallery、Siteinspire、Awwwards等の公開デザインキュレーションです。リポジトリにはスクリーンショットや第三者の説明文を転載せず、公開サイトの名称・URLとVEXUM独自の優先順位のみを保存します。

## Structure

```text
references/
└── websites/
    ├── A.csv
    ├── B.csv
    ├── ...
    └── Z.csv
```

CSV schema:

```text
priority,rank,name,url,focus
```

`focus` はVEXUM側で参照するときの大分類（motion / typography / layout / brand / product / editorial / ecommerce など）です。
