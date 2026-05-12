# 🤖 AI Agent Daily Blog

AIエージェント開発のノウハウを自動収集し、毎朝ブログ記事を生成・投稿するシステムです。

## アーキテクチャ

```
GitHub Actions (毎朝 6:00 JST)
    │
    ├─ 📥 collect.py      情報収集
    │       ├─ arXiv API        最新論文
    │       ├─ RSS フィード      Anthropic/OpenAI/HF/LangChain
    │       ├─ Hacker News API  コミュニティ
    │       └─ GitHub API       トレンドリポジトリ
    │
    ├─ ✍️ generate.py     記事生成（Claude API）
    │       ├─ Step 1: スコアリング & キュレーション
    │       ├─ Step 2: 記事本文生成
    │       └─ Step 3: 品質チェック（60点未満は下書き保存）
    │
    └─ 🚀 publish.py      投稿
            ├─ Zenn（GitHubリポジトリ連携）
            ├─ WordPress（REST API）
            └─ Slack通知
```

## セットアップ

### 1. リポジトリをフォーク・クローン

```bash
git clone https://github.com/your-username/ai-agent-blog
cd ai-agent-blog
```

### 2. GitHub Secrets を設定

GitHub リポジトリの **Settings → Secrets and variables → Actions** で以下を設定：

| Secret 名 | 説明 | 必須 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API キー | ✅ |
| `GH_TOKEN` | GitHub Personal Access Token (repo権限) | ✅ |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | 任意 |
| `WP_URL` | WordPress サイトURL | WordPressのみ |
| `WP_USER` | WordPress ユーザー名 | WordPressのみ |
| `WP_APP_PASSWORD` | WordPress アプリケーションパスワード | WordPressのみ |

### 3. Variables を設定

**Settings → Secrets and variables → Actions → Variables** で設定：

| Variable 名 | 値 | 説明 |
|---|---|---|
| `PUBLISH_TARGET` | `zenn` または `wordpress` | 投稿先 |

### 4. Zenn 連携の場合

1. [Zenn](https://zenn.dev) アカウントを作成
2. このリポジトリを Zenn に連携（Zenn ダッシュボード → GitHub連携）
3. `zenn/articles/` ディレクトリに Markdown を置くと自動公開されます

### 5. ローカルテスト

```bash
pip install -r requirements.txt

# 収集のみテスト
GITHUB_TOKEN=xxx python scripts/collect.py

# 記事生成テスト（収集後に実行）
ANTHROPIC_API_KEY=xxx python scripts/generate.py

# 投稿テスト（dry_run的に実行）
PUBLISH_TARGET=zenn python scripts/publish.py
```

### 6. 手動実行

GitHub Actions の **Actions → Daily AI Agent Blog → Run workflow** からいつでも手動実行可能。
`dry_run` を有効にすると投稿せず記事生成のみ確認できます。

## ディレクトリ構成

```
.
├── .github/workflows/
│   └── daily-blog.yml      # GitHub Actions ワークフロー
├── scripts/
│   ├── collect.py          # 情報収集
│   ├── generate.py         # 記事生成（Claude API）
│   └── publish.py          # 投稿
├── data/                   # 収集データ（自動生成）
│   ├── raw_YYYY-MM-DD.json
│   └── curated_YYYY-MM-DD.json
├── articles/               # 生成記事（自動生成）
│   └── YYYY-MM-DD.md
├── zenn/articles/          # Zenn投稿用（自動生成）
├── requirements.txt
└── README.md
```

## 月額コスト目安

| 項目 | 費用 |
|---|---|
| Claude API（記事1本 ≈ 8,000トークン × 3回） | 〜$0.10〜0.30/日 |
| GitHub Actions | 無料枠内 |
| 合計 | **約$3〜10/月** |

## カスタマイズ

### 収集ソースの追加
`scripts/collect.py` の `RSS_FEEDS` 辞書にURLを追加するだけ。

### 記事フォーマットの変更
`scripts/generate.py` の `ARTICLE_PROMPT` を編集。

### 投稿時刻の変更
`.github/workflows/daily-blog.yml` の `cron` を変更。
例：毎朝7時JST → `"0 22 * * *"`（UTC換算）

## トラブルシューティング

- **記事が生成されない**: `ANTHROPIC_API_KEY` を確認
- **Zennに反映されない**: GH_TOKENのrepo権限とZenn連携を確認
- **品質チェック落ち**: `articles/YYYY-MM-DD.md` のフロントマター `approved` を確認
