# 🤖 AI Agent Daily Blog

AIエージェント開発のノウハウを自動収集し、毎朝ブログ記事を生成・投稿するシステムです。

## アーキテクチャ

```
GitHub Actions (毎朝 6:00 JST)
    │
    ├─ 📥 collect.py      情報収集
    │       ├─ arXiv API             最新論文
    │       ├─ RSS フィード           Anthropic/OpenAI/HF/LangChain/DeepMind 等
    │       ├─ Hacker News API       コミュニティ
    │       ├─ GitHub API            トレンドリポジトリ
    │       ├─ YouTube Data API v3   動画（トランスクリプト取得対応）
    │       ├─ YouTube Shorts        短尺解説動画（トランスクリプト取得対応）
    │       └─ X(Twitter) API v2     公式アカウント優先収集 ★NEW
    │               @AnthropicAI / @ClaudeAI / @code / @MicrosoftCopilot
    │
    ├─ ✍️ generate.py     記事生成（Claude API / マルチエージェント）
    │       ├─ Agent 1: ThemeSelectorAgent (Haiku)  テーマ選定
    │       ├─ Agent 2: ResearchAgent (Haiku)        情報収集・ランキング
    │       ├─ Agent 3: WriterAgent (Sonnet)         記事執筆
    │       ├─ Agent 4: JapaneseNativeCheckAgent (Haiku) 日本語校正
    │       ├─ Agent 5: SummarizerAgent (Haiku)      読了時間圧縮（5分以内）
    │       └─ Agent 6: EditorAgent (Haiku)          品質評価（70点以上で承認）
    │
    ├─ 🔍 polish.py       記事品質チェック・自動修正 ★NEW
    │       ├─ 「おわりに」セクション存在確認
    │       ├─ 見出し重複チェック
    │       ├─ フロントマター検証
    │       └─ --fix で自動修正（重複参考文献削除・おわりにプレースホルダー追加）
    │
    └─ 🚀 publish.py      投稿
            ├─ Zenn（GitHubリポジトリ連携）
            ├─ WordPress（REST API）
            └─ Slack通知
```

## 優先度システム

収集した情報は以下の優先度でスコアリングされ、テーマ選定に反映されます。

| 優先度 | ソース | 説明 |
|---|---|---|
| 🔴🔴🔴 **絶対最高** | X(Twitter) 公式 | @AnthropicAI / @ClaudeAI / @code / @MicrosoftCopilot |
| 🔴🔴 **最高** | 各ソース | GitHub Copilot・Claude Code・VSCode・最新AIモデルの情報 |
| 🔴 **高** | 各ソース | エージェント評価・トークン最適化・ローカルLLM等 |
| ● **中** | 各ソース | クラウドAI・RAG設計・AIアプリ等 |
| ○ **低** | arXiv | 純粋な学術論文・理論的内容 |

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
| `TWITTER_BEARER_TOKEN` | X(Twitter) API v2 Bearer Token | 推奨 ★NEW |
| `YOUTUBE_API_KEY` | YouTube Data API v3 キー | 推奨 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL | 任意 |
| `WP_URL` | WordPress サイトURL | WordPressのみ |
| `WP_USER` | WordPress ユーザー名 | WordPressのみ |
| `WP_APP_PASSWORD` | WordPress アプリケーションパスワード | WordPressのみ |

> **Twitter API について**: Basic プラン（$100/月）以上が必要です。Bearer Token は Twitter Developer Portal で取得します。

### 3. Variables を設定

**Settings → Secrets and variables → Actions → Variables** で設定：

| Variable 名 | 値 | 説明 |
|---|---|---|
| `PUBLISH_TARGET` | `zenn` または `wordpress` | 投稿先 |

### 4. Zenn 連携の場合

1. [Zenn](https://zenn.dev) アカウントを作成
2. このリポジトリを Zenn に連携（Zenn ダッシュボード → GitHub連携）
3. `articles/` ディレクトリに Markdown を置くと自動公開されます

### 5. ローカルテスト

```bash
pip install -r requirements.txt

# 収集のみテスト
GITHUB_TOKEN=xxx TWITTER_BEARER_TOKEN=xxx YOUTUBE_API_KEY=xxx python scripts/collect.py

# 記事生成テスト（収集後に実行）
ANTHROPIC_API_KEY=xxx python scripts/generate.py

# 記事品質チェック
python scripts/polish.py

# 問題を自動修正
python scripts/polish.py --fix

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
│   ├── collect.py          # 情報収集（arXiv/RSS/HN/GitHub/YouTube/X）
│   ├── generate.py         # 記事生成（Claude API マルチエージェント）
│   ├── polish.py           # 記事品質チェック・自動修正 ★NEW
│   └── publish.py          # 投稿（Zenn/WordPress/Slack）
├── data/                   # 収集データ（自動生成）
│   └── raw_YYYY-MM-DD.json
├── articles/               # Zenn投稿用（自動生成）
│   └── YYYY-MM-DD-slug.md
├── requirements.txt
└── README.md
```

## 記事フォーマット

生成される記事は以下のセクション構成で出力されます：

```
---
フロントマター (Zenn形式)
---

# タイトル

**日付 | 読了 X分 | #タグ**

リード文（フック）

---
## セクション1
## セクション2
## セクション3（驚き・核心）
## セクション4（展望・アクション）
---
## 🛠️ エンジニアのための実践Tips
---
## 📚 参考リソース
---
## おわりに  ← 筆者の所感（必須）★NEW
```

`## おわりに` は筆者の所感セクションとして必ず生成されます。
`polish.py --fix` を使うと、既存記事にプレースホルダーを追加できます。

## 月額コスト目安

| 項目 | 費用 |
|---|---|
| Claude API（Haiku/Sonnet使い分け） | 〜$0.15〜0.25/日 |
| GitHub Actions | 無料枠内 |
| X(Twitter) API Basic | $100/月（任意） |
| YouTube Data API | 無料枠内（1万クォータ/日） |
| 合計（Twitter除く） | **約$5〜8/月** |

## カスタマイズ

### 収集ソースの追加
`scripts/collect.py` の `RSS_FEEDS` 辞書にURLを追加するだけ。

### X公式アカウントの追加
`scripts/collect.py` の `TWITTER_OFFICIAL_ACCOUNTS` リストにアカウント名を追加。

### 記事フォーマットの変更
`scripts/generate.py` の `WRITER_SYSTEM` プロンプトを編集。

### 投稿時刻の変更
`.github/workflows/daily-blog.yml` の `cron` を変更。
例：毎朝7時JST → `"0 22 * * *"`（UTC換算）

## トラブルシューティング

- **記事が生成されない**: `ANTHROPIC_API_KEY` を確認
- **Twitterデータが取得できない**: `TWITTER_BEARER_TOKEN` を確認（Basic プラン以上が必要）
- **YouTubeトランスクリプトが取得できない**: 動画によっては字幕が無効の場合あり（自動的にスキップ）
- **Zennに反映されない**: GH_TOKENのrepo権限とZenn連携を確認
- **品質チェック落ち**: `articles/YYYY-MM-DD.md` のフロントマター `approved` を確認
- **「おわりに」が見つからない**: `python scripts/polish.py --fix` でプレースホルダーを追加後、内容を手動記入
