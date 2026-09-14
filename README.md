# VEXUM Design Library

VEXUMでWebサイトやLP、教材、業務画面を設計するときに参照するためのデザインリファレンス集です。

## Web reference ranking

`references/websites/` に、実在するデザイン参考サイトを **3,000件** 保存します。

- **priority**: 1（最優先）〜3000
- **rank**: A（最優先）〜Z（相対的に低優先）の26段階
- 1ランクあたり約115〜116件
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

発見元は、A1 Gallery と Awwwards の公開デザインキュレーションです。リポジトリにはスクリーンショットや第三者の説明文を転載せず、公開サイトの名称・URL・参照元ページとVEXUM独自の優先順位のみを保存します。

## Structure

```text
references/
├── websites/
│   ├── all.csv
│   ├── A.csv ... Z.csv
│   └── metadata.json
└── categories/
    ├── motion.csv
    ├── typography.csv
    └── ...
└── features/
    ├── cutin-and-page-transition.csv
    ├── fixed-ui-and-navigation.csv
    ├── background-motion.csv
    └── ...
```

CSV schema:

```text
priority,rank,name,url,focus,source,source_page
```

`focus` はVEXUM側で参照するときの大分類（motion / typography / layout / brand / product / editorial / ecommerce など）です。

`references/categories/` には、同じレコードを `focus` 別に保存します。案件の目的から先に探したいときは、こちらを入口にします。

`references/features/` は、カットイン、固定UI・ナビゲーション、背景演出、スクロール連動、マイクロインタラクションなど、実装したい機能を起点にした一覧です。各行の `evidence` に、抽出に用いた公開カタログ上のタグを残します。
