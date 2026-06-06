# 世界ニュース母艦

世界ニュース、日本ニュース、投資ニュース、AIニュース、教育ニュースのRSSを集約し、GitHub Pagesで公開する静的ニュースサイトです。

Gemini APIキーをGitHub ActionsのSecretに登録している場合は、各カテゴリの記事に日本語タイトルと3〜5行の日本語要約を追加します。APIキーがない場合はRSS本文を表示します。APIキーがあるのにGemini要約が0件だった場合は、既存の公開ページを英語版で上書きしないよう更新を停止します。

## 公開ページ

https://tsubaki-pe.github.io/news-hub/

## 自動更新

GitHub Actionsの `.github/workflows/update-news.yml` で自動更新します。

- 実行タイミング: 毎日 21:00 UTC / 09:00 UTC
- 日本時間: 毎日 朝 6:00 / 夕方 18:00
- 取得件数: 各カテゴリ10件、合計50件
- 手動実行: GitHubの `Actions` タブから `Update RSS news` を選び、`Run workflow` で実行できます
- 公開反映: RSS取得、Gemini要約、テスト、静的サイト生成のあと、GitHub Pagesへ自動デプロイされます
- 非常用復元: 手動実行時に `use_existing_news` を有効にすると、RSS/Gemini取得をスキップしてリポジトリ内の `news.json` をそのまま再デプロイします

## Gemini APIキー

GitHubリポジトリのSecretに `GEMINI_API_KEY` を登録すると、日本語化が有効になります。

登録場所:

1. GitHubで `tsubaki-pe/news-hub` を開く
2. `Settings` を開く
3. `Secrets and variables` → `Actions` を開く
4. `Repository secrets` に `GEMINI_API_KEY` を登録する

現在のワークフローでは `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}` を使っています。

## ローカル実行

```bash
python scripts/fetch_feeds.py
python scripts/build_site.py
python -m http.server 8000 --directory _site
```

ブラウザで `http://localhost:8000` を開くと確認できます。

## テスト

```bash
python -m unittest discover -s tests
```

## 失敗した時のログ確認

自動更新や手動実行が失敗した場合は、GitHub Actionsのログを確認します。

1. GitHubで `tsubaki-pe/news-hub` を開く
2. 上部メニューの `Actions` を開く
3. 左側の `Update RSS news` を選ぶ
4. 一覧から失敗した実行をクリックする
5. `build` を開く
6. `Fetch RSS feeds` を開く
7. Gemini関連のエラー、RSS取得エラー、テスト失敗を確認する

よく見るポイント:

- `GEMINI_API_KEY is not set`: Secretが未登録です
- `Gemini returned HTTP 429`: Gemini APIの無料枠やレート制限に当たっています
- `Gemini did not return usable translations`: Geminiの返答形式が期待と違います
- `Gemini returned no usable translations`: Gemini要約が0件だったため、英語版で既存公開ページを上書きしないよう更新を停止しています
- `No items were fetched`: RSS取得に失敗し、記事が0件です

APIキーがある状態でGemini要約が0件だった場合は、既存の公開データを壊さないために更新を止め、GitHub Pagesへデプロイしません。RSS記事が0件の場合も同じく更新を止めます。

## 公開対象ファイル

GitHub Pagesには `_site` に生成された以下のファイルが公開されます。

- `index.html`
- `app.js`
- `styles.css`
- `news.json`
- `.nojekyll`
