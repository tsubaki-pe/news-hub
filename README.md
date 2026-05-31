# Morning RSS News

RSSフィードを毎朝取得して、カテゴリ別のニュース一覧として公開する静的サイトです。APIキーは使いません。

## カテゴリ

- 世界ニュース
- 日本ニュース
- 投資ニュース
- AIニュース
- 教育ニュース

## 表示項目

- タイトル
- 媒体名
- 公開日時
- 短い抜粋
- リンク

## ローカル更新

```bash
python scripts/fetch_feeds.py
```

生成結果は `data/news.json` に保存されます。

## GitHub Pages

`.github/workflows/update-news.yml` が毎日 21:00 UTC に実行されます。これは日本時間の毎朝 6:00 です。

GitHub リポジトリの Settings → Pages で Source を GitHub Actions に設定してください。
