# 世界ニュース母艦

世界・日本・投資・AI・教育のRSSを毎朝収集し、カテゴリ切替と全文検索で確認できる静的ニュースハブです。APIキーやサーバーは不要で、GitHub ActionsとGitHub Pagesだけで運用できます。

## ローカル実行

```bash
python scripts/fetch_feeds.py
python scripts/build_site.py
python -m http.server 8000 --directory _site
```

`http://localhost:8000` を開くと確認できます。RSS取得を伴わず既存の `news.json` で表示確認する場合は、2行目以降だけ実行してください。

## テスト

```bash
python -m unittest discover -s tests
```

## 自動更新と公開

`.github/workflows/update-news.yml` が毎日 21:00 UTC（日本時間 6:00）にRSS取得、テスト、公開用ビルド、GitHub Pagesへのデプロイを行います。手動実行にも対応しています。

公開対象は `_site` に生成される `index.html`、`app.js`、`styles.css`、`news.json`、`.nojekyll` のみです。取得できない配信元があっても残りのニュースは公開され、全配信元が失敗した場合は既存データを空データで上書きせずワークフローを停止します。

## 日本語翻訳と要約

GitHub ActionsのSecretに `GEMINI_API_KEY` を登録すると、各カテゴリの上位記事に日本語タイトルと3〜5行のやさしい日本語要約を追加します。APIキーが未登録、またはAPI呼び出しに失敗した場合でも、従来どおりRSSのタイトルと要約を表示します。

無料枠を使いやすくするため、初期設定では各カテゴリ10件まで翻訳・要約します。件数はワークフローの `TRANSLATION_LIMIT_PER_CATEGORY` で変更できます。
