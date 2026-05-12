"""
generate.py — Claude API を使って収集データから記事を生成
"""

import os
import json
import datetime
import anthropic
from pathlib import Path

TODAY = datetime.date.today().isoformat()
DATA_DIR = Path("data")
ARTICLES_DIR = Path("articles")
ARTICLES_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


# ────────────────────────────────────────────────────────────
# Step 1: スコアリング & 整理
# ────────────────────────────────────────────────────────────
SCORING_PROMPT = """あなたはAIエージェント開発の専門キュレーターです。
以下の収集データを分析し、日本のAIエンジニア向けに価値の高い情報を選定・整理してください。

## タスク
1. 各アイテムに重要度スコア（1〜10）を付ける
2. カテゴリ分類する（framework / paper / tool / community / news）
3. 重複・類似コンテンツを統合する
4. 「今日のハイライト」として最も注目すべき1トピックを選ぶ

## 出力形式（必ずこのJSONのみ返すこと。前後の説明・```json不要）
{
  "highlight": {
    "title": "今日最注目のトピック",
    "reason": "なぜ重要か（100字以内）",
    "source_index": 0
  },
  "curated": [
    {
      "index": 0,
      "score": 9,
      "category": "paper",
      "japanese_title": "日本語タイトル",
      "key_insight": "エンジニアが知るべきポイント（150字以内）",
      "original_title": "...",
      "url": "..."
    }
  ]
}

## 収集データ
{raw_data}
"""

def score_and_curate(raw_items: list[dict]) -> dict:
    """Claude に重要度スコアリングと整理を依頼"""
    # トークン削減のため要約版を渡す
    simplified = [
        {
            "idx": i,
            "source": item["source"],
            "title": item["title"],
            "summary": item.get("summary", "")[:300],
            "url": item.get("url", ""),
        }
        for i, item in enumerate(raw_items)
    ]

    prompt = SCORING_PROMPT.replace("{raw_data}", json.dumps(simplified, ensure_ascii=False))

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # ```json ... ``` が含まれる場合に除去
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ────────────────────────────────────────────────────────────
# Step 2: 記事生成
# ────────────────────────────────────────────────────────────
ARTICLE_PROMPT = """あなたはAIエージェント開発に詳しい日本語テックライターです。
以下のキュレーション済みデータから、日本のエンジニア向けに読み応えのあるブログ記事を生成してください。

## 記事フォーマット（Markdown）

# 【AIエージェント最前線】{date} ─ {highlight_title}

> {highlight_reason}

---

## 🔥 今日のハイライト

（highlight トピックを400〜600字で深掘り解説。背景・技術的意義・エンジニアへの影響を含める）

---

## 📚 論文ピックアップ

（category=paper のアイテムを2〜3件。各200字程度で解説）

---

## 🛠️ ツール・フレームワーク

（category=framework または tool のアイテムを2〜3件。実用的な観点で解説）

---

## 💡 コミュニティの声・News

（category=community または news のアイテムを2〜3件。簡潔に）

---

## ✍️ 編集後記

（今日のトレンドを俯瞰した一言コメント。100字程度）

---
*収集元: arXiv, Anthropic/OpenAI/HuggingFace Blog, Hacker News, GitHub Trending*
*自動生成: {date}*

## キュレーション済みデータ
{curated_json}
"""

def generate_article(curated: dict, date: str) -> str:
    """整理済みデータから記事本文を生成"""
    prompt = (
        ARTICLE_PROMPT
        .replace("{date}", date)
        .replace("{highlight_title}", curated["highlight"]["title"])
        .replace("{highlight_reason}", curated["highlight"]["reason"])
        .replace("{curated_json}", json.dumps(curated["curated"], ensure_ascii=False, indent=2))
    )

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ────────────────────────────────────────────────────────────
# Step 3: 品質チェック
# ────────────────────────────────────────────────────────────
QUALITY_PROMPT = """以下のブログ記事を品質チェックしてください。

評価項目（各10点満点）:
1. 技術的正確性
2. 読みやすさ・構成
3. 日本語エンジニアへの実用性
4. 情報の鮮度・独自性

JSONのみ返すこと:
{{"score": 75, "issues": ["...", "..."], "approved": true}}

approved は合計スコアが60以上なら true

記事:
{article}
"""

def quality_check(article: str) -> dict:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": QUALITY_PROMPT.replace("{article}", article[:3000])}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ────────────────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────────────────
def main():
    # 収集データ読み込み
    raw_path = DATA_DIR / f"raw_{TODAY}.json"
    if not raw_path.exists():
        raise FileNotFoundError(f"収集データが見つかりません: {raw_path}\nまず collect.py を実行してください")

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    raw_items = raw["items"]
    print(f"📥 収集データ: {len(raw_items)} 件")

    # Step 1: スコアリング
    print("🔍 スコアリング中...")
    curated = score_and_curate(raw_items)
    curated_path = DATA_DIR / f"curated_{TODAY}.json"
    with open(curated_path, "w", encoding="utf-8") as f:
        json.dump(curated, f, ensure_ascii=False, indent=2)
    print(f"✅ キュレーション完了: {len(curated['curated'])} 件選定")

    # Step 2: 記事生成
    print("✍️  記事生成中...")
    article = generate_article(curated, TODAY)

    # Step 3: 品質チェック
    print("🔎 品質チェック中...")
    quality = quality_check(article)
    print(f"   スコア: {quality['score']}/40, 承認: {quality['approved']}")

    # 保存
    article_path = ARTICLES_DIR / f"{TODAY}.md"
    metadata = {
        "date": TODAY,
        "highlight": curated["highlight"]["title"],
        "quality_score": quality["score"],
        "approved": quality["approved"],
        "issues": quality.get("issues", []),
        "item_count": len(raw_items),
        "curated_count": len(curated["curated"]),
    }

    # メタデータをフロントマターとして付与
    frontmatter = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in metadata.items()) + "\n---\n\n"
    with open(article_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + article)

    print(f"\n✅ 記事生成完了 → {article_path}")

    if not quality["approved"]:
        print("⚠️  品質スコアが低いため、下書き状態で保存しました")
        print(f"   問題点: {quality.get('issues', [])}")
        # GitHub Actions では exit 1 で投稿をスキップ
        exit(1)

    print("🚀 投稿準備完了")


if __name__ == "__main__":
    main()
