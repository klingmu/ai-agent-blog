"""
generate.py — 記事生成エージェント（コスト最適化版）

コスト削減策（5つ）:
  ① モデル使い分け  Haiku / Sonnet を役割別に選択（Opus は使わない）
  ② ResearchAgent ループ上限を 10→5 ターンに削減
  ③ WriterAgent 差し戻し上限を 3→2 回、合格ラインを 75→70 点に緩和
  ④ ThemeSelectorAgent/ResearchAgent へ渡すデータはタイトル+100字に削減
  ⑤ EditorAgent は記事の先頭 2,000 字のみ評価

コスト試算（1日あたり）:
  変更前: 最悪 ~$1.30（Opus×17回）
  変更後: 通常 ~$0.15、最悪 ~$0.25（Haiku/Sonnet 使い分け）
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

# ── ① モデル使い分け ──────────────────────────────────────────
# JSON出力のみ → Haiku（最安）
# 文章執筆 → Sonnet（品質と価格のバランス）
MODEL_HAIKU  = "claude-haiku-4-5-20251001"   # ThemeSelector / Research / Editor
MODEL_SONNET = "claude-sonnet-4-6"            # Writer（記事品質が核心）

# ── ② ResearchAgent ループ上限 ────────────────────────────────
MAX_AGENT_TURNS     = 5   # 10 → 5
# ── ③ 差し戻し上限・合格ライン ───────────────────────────────
MAX_REWRITE_ATTEMPTS = 2  # 3 → 2
APPROVE_THRESHOLD    = 70  # 75 → 70


# ══════════════════════════════════════════════════════════════
# ④ データ圧縮ヘルパー
# ══════════════════════════════════════════════════════════════
def _slim(items: list[dict], summary_len: int = 100) -> list[dict]:
    """ThemeSelector / ResearchAgent に渡す圧縮版（タイトル + 100字要約）"""
    return [
        {
            "idx": i,
            "src": item["source"].split(":")[0],
            "title": item["title"],
            "summary": item.get("summary", "")[:summary_len],
        }
        for i, item in enumerate(items)
    ]


# ══════════════════════════════════════════════════════════════
# ツール定義（ResearchAgent が使う）
# ══════════════════════════════════════════════════════════════
RESEARCH_TOOLS = [
    {
        "name": "search_collected_data",
        "description": "収集済みデータからキーワードに関連するアイテムを検索する。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array", "items": {"type": "string"},
                    "description": "検索キーワード（例: ['multi-agent', 'tool use']）",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string",
                              "enum": ["arxiv","rss","hackernews","github","youtube","youtube_shorts"]},
                    "description": "絞り込むソース（省略で全ソース）",
                },
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["keywords"],
        },
    },
    {
        "name": "rank_items_by_novelty",
        "description": "アイテムリストを新規性・話題性でランキングする。",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_indices": {
                    "type": "array", "items": {"type": "integer"},
                    "description": "ランキング対象インデックス",
                },
            },
            "required": ["item_indices"],
        },
    },
    {
        "name": "finalize_research",
        "description": "リサーチ完了を宣言する。情報が揃ったら必ずこれを呼ぶ。",
        "input_schema": {
            "type": "object",
            "properties": {
                "selected_indices": {
                    "type": "array", "items": {"type": "integer"},
                    "description": "記事に使うアイテムのインデックス（5〜8件）",
                },
                "research_notes": {
                    "type": "string",
                    "description": "ライターへの調査メモ（背景・文脈・補足）",
                },
            },
            "required": ["selected_indices", "research_notes"],
        },
    },
]


def _handle_tool(tool_name: str, tool_input: dict, all_items: list[dict]) -> str:
    if tool_name == "search_collected_data":
        keywords = [k.lower() for k in tool_input["keywords"]]
        sources  = tool_input.get("sources", [])
        max_r    = tool_input.get("max_results", 5)
        results  = []
        for i, item in enumerate(all_items):
            src = item["source"].split(":")[0]
            if sources and src not in sources:
                continue
            text = (item.get("title","") + " " + item.get("summary","")).lower()
            if any(kw in text for kw in keywords):
                # ④ ツール結果も 100 字に絞る
                results.append({
                    "index": i, "src": src,
                    "title": item["title"],
                    "summary": item.get("summary","")[:100],
                })
        return json.dumps(results[:max_r], ensure_ascii=False)

    elif tool_name == "rank_items_by_novelty":
        indices = tool_input["item_indices"]
        ranked  = []
        for idx in indices:
            if 0 <= idx < len(all_items):
                item  = all_items[idx]
                score = 0
                if "arxiv"   in item["source"]: score += 3
                if "youtube" in item["source"]: score += 2
                score += min(item.get("hn_score", 0) // 100, 3)
                score += min(item.get("stars",    0) // 1000, 2)
                ranked.append({"index": idx, "title": item["title"], "score": score})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return json.dumps(ranked, ensure_ascii=False)

    elif tool_name == "finalize_research":
        return json.dumps({"status": "finalized"})

    return json.dumps({"error": f"未知のツール: {tool_name}"})


# ══════════════════════════════════════════════════════════════
# Agent 1: ThemeSelectorAgent — Haiku
# ══════════════════════════════════════════════════════════════
THEME_SELECTOR_SYSTEM = """あなたは雑誌編集長です。
収集データを見て今日号のテーマ・起承転結を設計します。
JSONのみ返してください（前後の説明・```json 不要）。

出力フォーマット:
{
  "theme": "テーマ（30字以内）",
  "hook": "冒頭フック（40字以内）",
  "why_now": "なぜ今か（80字）",
  "narrative_arc": {
    "ki": "起の骨格",
    "sho": "承の骨格",
    "ten": "転の骨格（驚き・反転）",
    "ketsu": "結の骨格"
  },
  "key_items": [0, 3, 7],
  "glossary_needed": ["RAG", "MCP"]
}"""

def run_theme_selector(all_items: list[dict]) -> dict:
    # ④ 100字要約のみ渡す
    slim = _slim(all_items, summary_len=100)
    resp = client.messages.create(
        model=MODEL_HAIKU, max_tokens=800,   # ① Haiku
        system=THEME_SELECTOR_SYSTEM,
        messages=[{"role": "user",
                   "content": f"収集データ:\n{json.dumps(slim, ensure_ascii=False)}"}],
    )
    theme = json.loads(_strip_json(resp.content[0].text))
    print(f"📋 テーマ: 「{theme['theme']}」  フック: {theme['hook']}")
    _log_cost("ThemeSelector(Haiku)", resp)
    return theme


# ══════════════════════════════════════════════════════════════
# Agent 2: ResearchAgent — Haiku × tool_use（最大5ターン）
# ══════════════════════════════════════════════════════════════
RESEARCH_SYSTEM = """あなたはデータリサーチャーです。
テーマに沿って収集データから情報を集め、最後に finalize_research を呼んでください。

ルール:
- search_collected_data でテーマ関連データを検索（1〜2回）
- rank_items_by_novelty で候補を精査（1回）
- 情報が揃ったらすぐ finalize_research を呼ぶ（ループを最小化）
- 5件以上選定してメモを添える"""

def run_research_agent(theme: dict, all_items: list[dict]) -> dict:
    # ④ 圧縮版データをプロンプトに含める
    slim    = _slim(all_items, summary_len=100)
    messages = [{
        "role": "user",
        "content": (
            f"テーマ: {json.dumps(theme, ensure_ascii=False)}\n"
            f"アイテム数: {len(slim)}件\n"
            f"データ: {json.dumps(slim, ensure_ascii=False)}\n\n"
            "情報収集してください。"
        ),
    }]

    finalized    = None
    total_input  = 0
    total_output = 0

    for turn in range(MAX_AGENT_TURNS):   # ② 最大5ターン
        resp = client.messages.create(
            model=MODEL_HAIKU, max_tokens=1000,   # ① Haiku
            system=RESEARCH_SYSTEM,
            tools=RESEARCH_TOOLS,
            messages=messages,
        )
        total_input  += resp.usage.input_tokens
        total_output += resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            print(f"   [Research] turn {turn+1}: end_turn")
            break

        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            print(f"   [Research] turn {turn+1}: {block.name}")
            if block.name == "finalize_research":
                finalized = block.input
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": json.dumps({"status": "finalized"}),
                })
                break
            result = _handle_tool(block.name, block.input, all_items)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id, "content": result,
            })

        if finalized:
            break
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    print(f"   [Research] 合計 {total_input}入力/{total_output}出力トークン")

    if not finalized:
        finalized = {
            "selected_indices": theme.get("key_items", list(range(min(6, len(all_items))))),
            "research_notes": "フォールバック: key_items を使用",
        }

    selected = [all_items[i] for i in finalized["selected_indices"] if 0 <= i < len(all_items)]
    print(f"   [Research] 選定: {len(selected)}件")
    return {"selected_items": selected, "research_notes": finalized["research_notes"]}


# ══════════════════════════════════════════════════════════════
# Agent 3: WriterAgent — Sonnet（記事品質が核心）
# ══════════════════════════════════════════════════════════════
WRITER_SYSTEM = """あなたはトップクラスのテックライターです。
AIビギナーから最前線エンジニアまで全員が楽しめる雑誌スタイルの記事を書きます。

## 執筆の鉄則
1. 起承転結を厳守 — 一貫したストーリーを紡ぐ
2. フックで心を掴む — 冒頭2〜3文で「読まなきゃ損」と思わせる
3. 専門用語は必ず解説 — 初出の用語には 💡用語解説 ボックスを付ける
4. 具体例・比喩で説明 — 抽象概念は日常の例えに落とす
5. 転で驚かせる — 「実は…」「意外にも…」で予想を裏切る
6. 実用的なTips — 明日から使えるアクションを含める
7. 読後感を大切に — 結びで希望と次の一歩を渡す

## フォーマット（Markdown）

# {キャッチーなタイトル}

**{日付} | 読了 {分}分 | #{タグ}**

> {フック — 2〜3文}

---

## 🔮 起：{サブタイトル}
（600〜800字。初心者にも伝わる言葉で背景・問題提起）

> 💡 **用語解説**  **[用語]** — 説明（1〜2文）

---

## 🔍 承：{サブタイトル}
（800〜1000字。論文・実装例・動画を交えて深掘り）

---

## ⚡ 転：{サブタイトル}
（800〜1000字。意外な視点・反転・ドラマ — ここが核心）

---

## 🚀 結：{サブタイトル}
（400〜600字。読者への示唆・希望）

---

## 🛠️ 実践Tips
（箇条書き 3〜5個。明日から使えるアクション）

---

## 📚 参考リソース
（URL リスト）

---
*収集ソース: arXiv, OpenAI/Anthropic Blog, Hacker News, GitHub, YouTube*
*{date}*"""

def run_writer_agent(theme: dict, research: dict,
                     feedback: str | None = None, attempt: int = 1) -> str:
    glossary = ", ".join(theme.get("glossary_needed", []))
    fb_section = f"\n\n## ⚠️ 編集からの改善指示（第{attempt}稿）\n{feedback}\n" if feedback else ""

    # アイテムは要約 200 字に絞ってトークンを節約
    items_slim = [
        {"title": it["title"], "url": it.get("url",""),
         "summary": it.get("summary","")[:200], "source": it["source"]}
        for it in research["selected_items"]
    ]

    prompt = (
        f"## テーマ設計\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"## リサーチノート\n{research['research_notes']}\n\n"
        f"## 使用アイテム\n{json.dumps(items_slim, ensure_ascii=False)}\n\n"
        f"## 必須用語解説\n{glossary}\n\n"
        f"## 日付\n{TODAY}"
        f"{fb_section}\n\n"
        "上記をもとに記事を執筆してください。"
    )
    resp = client.messages.create(
        model=MODEL_SONNET, max_tokens=6000,   # ① Sonnet
        system=WRITER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    _log_cost(f"Writer(Sonnet) 第{attempt}稿", resp)
    return resp.content[0].text


# ══════════════════════════════════════════════════════════════
# Agent 4: EditorAgent — Haiku（先頭 2,000 字のみ評価）
# ══════════════════════════════════════════════════════════════
EDITOR_SYSTEM = f"""あなたは雑誌編集長です。記事を5軸で採点し承認 or 差し戻しを判定します。

評価基準（各20点満点・合計 {APPROVE_THRESHOLD}点以上で承認）:
1. fun_novelty   — おもしろさ・新規性
2. clarity       — わかりやすさ（用語解説あるか）
3. accuracy      — 正確性・信頼性
4. practicality  — 実用性（明日使えるか）
5. narrative     — 起承転結の完成度（転に驚きがあるか）

JSONのみ返すこと（前後の説明不要）:
{{
  "scores": {{"fun_novelty":0,"clarity":0,"accuracy":0,"practicality":0,"narrative":0}},
  "total": 0,
  "approved": false,
  "feedback": "差し戻し時の具体的改善指示（承認時は空文字）",
  "highlight_sentence": "SNSシェア用の最良の一文"
}}"""

def run_editor_agent(article: str, theme: dict) -> dict:
    # ⑤ 先頭 2,000 字のみ渡す（構成・品質は冒頭でわかる）
    article_head = article[:2000]
    resp = client.messages.create(
        model=MODEL_HAIKU, max_tokens=600,   # ① Haiku
        system=EDITOR_SYSTEM,
        messages=[{"role": "user", "content":
                   f"テーマ: {theme['theme']}\n\n記事（先頭2000字）:\n{article_head}"}],
    )
    _log_cost("Editor(Haiku)", resp)
    result = json.loads(_strip_json(resp.content[0].text))
    # approved の基準を閾値で上書き保証
    result["approved"] = result.get("total", 0) >= APPROVE_THRESHOLD
    return result


# ══════════════════════════════════════════════════════════════
# OrchestratorAgent
# ══════════════════════════════════════════════════════════════
def orchestrate(all_items: list[dict]) -> tuple[str, dict]:
    print("\n🎯 [Orchestrator] ThemeSelectorAgent (Haiku)")
    theme = run_theme_selector(all_items)

    print("\n🔍 [Orchestrator] ResearchAgent (Haiku × tool_use, max 5 turns)")
    research = run_research_agent(theme, all_items)

    article  = ""
    quality  = {}
    feedback = None

    for attempt in range(1, MAX_REWRITE_ATTEMPTS + 1):
        print(f"\n✍️  [Orchestrator] WriterAgent (Sonnet) 第{attempt}稿")
        article = run_writer_agent(theme, research, feedback, attempt)

        print(f"\n🔎 [Orchestrator] EditorAgent (Haiku) 第{attempt}稿評価")
        quality = run_editor_agent(article, theme)

        total    = quality.get("total", 0)
        approved = quality.get("approved", False)
        scores   = quality.get("scores", {})
        print(f"   スコア: {total}/100 (閾値:{APPROVE_THRESHOLD})  承認: {approved}")
        print("   " + " / ".join(f"{k}:{v}" for k, v in scores.items()))

        if approved:
            print(f"✅ 第{attempt}稿 承認！")
            break

        feedback = quality.get("feedback", "")
        print(f"   差し戻し: {feedback[:80]}...")

        if attempt == MAX_REWRITE_ATTEMPTS:
            print("⚠️  最大リトライ到達。最後の稿を使用")

    return article, quality


# ══════════════════════════════════════════════════════════════
# ユーティリティ
# ══════════════════════════════════════════════════════════════
def _strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()

def _log_cost(label: str, resp) -> None:
    """トークン使用量をログ出力（デバッグ用）"""
    i = resp.usage.input_tokens
    o = resp.usage.output_tokens
    # 概算料金（Haiku: $0.25/$1.25 per 1M, Sonnet: $3/$15 per 1M）
    model = resp.model
    if "haiku" in model:
        cost = i * 0.00000025 + o * 0.00000125
    else:
        cost = i * 0.000003 + o * 0.000015
    print(f"   [{label}] {i}入力/{o}出力トークン ≈ ${cost:.4f}")


# ══════════════════════════════════════════════════════════════
# メイン
# ══════════════════════════════════════════════════════════════
def main():
    raw_path = DATA_DIR / f"raw_{TODAY}.json"
    if not raw_path.exists():
        raise FileNotFoundError(
            f"収集データが見つかりません: {raw_path}\n"
            "先に collect.py を実行してください"
        )
    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    all_items = raw["items"]
    print(f"📥 収集データ: {len(all_items)} 件")

    article, quality = orchestrate(all_items)

    article_path = ARTICLES_DIR / f"{TODAY}.md"
    meta = {
        "date":               TODAY,
        "quality_score":      quality.get("total", 0),
        "approved":           quality.get("approved", False),
        "scores":             quality.get("scores", {}),
        "highlight_sentence": quality.get("highlight_sentence", ""),
        "item_count":         len(all_items),
        "models_used":        {"theme": MODEL_HAIKU, "research": MODEL_HAIKU,
                               "writer": MODEL_SONNET, "editor": MODEL_HAIKU},
    }
    frontmatter = (
        "---\n"
        + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items())
        + "\n---\n\n"
    )
    with open(article_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + article)

    print(f"\n✅ 記事生成完了 → {article_path}")
    print(f"   品質スコア: {meta['quality_score']}/100")
    print(f"   ハイライト: {meta['highlight_sentence'][:60]}...")

    if not quality.get("approved"):
        print("⚠️  品質未承認 → 投稿スキップ（下書き保存済み）")
        exit(1)

    print("🚀 投稿準備完了")


if __name__ == "__main__":
    main()
