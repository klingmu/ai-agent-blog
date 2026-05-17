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
import re
import json
import datetime
import anthropic
from pathlib import Path

_JST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(_JST).date().isoformat()
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

# ── 読了時間制限 ──────────────────────────────────────────────
READING_TIME_LIMIT_MIN = 5   # 最大5分
CHARS_PER_MIN          = 500  # 日本語平均読書速度（字/分）


# ══════════════════════════════════════════════════════════════
# 🎯 ユーザーの関心領域設定
# ══════════════════════════════════════════════════════════════
USER_INTERESTS = {
    # 優先度: 超最高（公式X/Twitterアカウントからの発信 — source == "twitter_official" で判定）
    # @AnthropicAI / @ClaudeAI / @code (VS Code) / @MicrosoftCopilot
    # → _score_by_user_interest() でソース判定し score=3.0 を直接返す

    # 優先度: 2.0 （最高！！）
    "highest_priority": [
        # GitHub Copilot 関連
        "github copilot", "copilot update", "copilot feature", "copilot release",
        "copilot enterprise", "copilot workspace",
        # Claude Code / Anthropic 関連
        "claude code", "claude codebase", "claude model", "claude update", "claude release",
        "claude 3", "claude 4", "claude 5",
        # VSCode 関連
        "vscode", "vscode update", "vscode release", "visual studio code",
        "vscode extension", "vscode ai", "vscode copilot",
        # 最新AIモデルのアップデート
        "gpt-4", "gpt-5", "gemini", "gemini update", "o1", "o1-preview",
        "model release", "ai model", "model update",
        "anthropic", "openai", "google deepmind",
    ],
    # 優先度: 1.5 （高）
    "high_priority": [
        # エージェント・スキル評価・最適化
        "agent evaluation", "skill evaluation", "token optimization", "token efficiency",
        "context management", "context control", "orchestration", "agent orchestration",
        "execution time", "inference control", "parallel processing", "concurrency",
        "debugging", "debug tool", "trace", "observability",
        # ローカルLLM
        "local llm", "edge llm", "quantization", "model compression",
    ],
    # 優先度: 1.2 （中）
    "medium_priority": [
        # クラウドAI・アーキテクチャ
        "azure", "aws", "google cloud", "cloud architecture",
        "cloud ai", "vertex ai", "bedrock", "sagemaker",
        # RAG設計
        "rag", "retrieval", "vector database", "embedding",
        # AIアプリ
        "notion ai", "obsidian", "notebooklm", "ai notebook",
        "knowledge management", "ai app",
    ],
    # 優先度: 0.5 （低、学術的な論文）
    "low_priority": [
        "arxiv", "research", "paper", "academic",
        "theoretical", "formalization",
    ]
}

def _score_by_user_interest(item: dict) -> float:
    """アイテムをユーザーの関心度でスコア化（1.0 ~ 3.0）"""

    # 🔴🔴🔴 超最高優先度: 公式X(Twitter)アカウントの発信は常に最大スコア
    if item.get("source") == "twitter_official" or item.get("is_official_account"):
        return 3.0

    title_lower = item.get("title", "").lower()
    summary_lower = item.get("summary", "").lower()
    text = f"{title_lower} {summary_lower}"

    score = 1.0  # ベーススコア

    # 最高優先度キーワード（GitHub Copilot, Claude Code, VSCode, 最新モデル）
    for keyword in USER_INTERESTS.get("highest_priority", []):
        if keyword in text:
            score += 1.0  # +1.0
    
    # 高優先度キーワード
    for keyword in USER_INTERESTS.get("high_priority", []):
        if keyword in text:
            score += 0.5
    
    # 中優先度キーワード
    for keyword in USER_INTERESTS.get("medium_priority", []):
        if keyword in text:
            score += 0.2
    
    # 低優先度キーワード（スコア低下）
    for keyword in USER_INTERESTS.get("low_priority", []):
        if keyword in text:
            score *= 0.7
    
    # HackerNews スコアも加味
    hn_score = item.get("hn_score", 0)
    score += min(hn_score / 1000, 0.5)
    
    return min(score, 3.0)  # 最大3.0


# ══════════════════════════════════════════════════════════════
# ④ データ圧縮ヘルパー
# ══════════════════════════════════════════════════════════════
def _slim(items: list[dict], summary_len: int = 100) -> list[dict]:
    """ThemeSelector / ResearchAgent に渡す圧縮版（タイトル + 100字要約 + 関心度）"""
    return [
        {
            "idx": i,
            "src": item["source"],
            "title": item["title"],
            "summary": item.get("summary", "")[:summary_len],
            "user_interest_score": round(_score_by_user_interest(item), 2),
            # 公式X投稿は明示的にフラグを立てる
            "is_official": item.get("is_official_account", False),
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
                              "enum": ["arxiv","rss","hackernews","github","youtube","youtube_shorts","twitter_official"]},
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
                    "description": "記事に使うアイテムのインデックス（spotlight構成なら1〜3件、それ以外は5〜8件）",
                },
                "research_notes": {
                    "type": "string",
                    "description": "ライターへの調査メモ（背景・文脈・補足）",
                },
            },
            "required": ["selected_indices"],
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

                # 🔴🔴🔴 超最高優先度: 公式X(Twitter)アカウントの発信
                if item.get("source") == "twitter_official" or item.get("is_official_account"):
                    score += 30  # 他のいかなるソースも超える圧倒的スコア
                else:
                    # ★ ユーザー関心度スコアを大きく加味
                    user_interest_score = _score_by_user_interest(item)
                    if user_interest_score >= 2.0:
                        # 最高優先度（GitHub Copilot, Claude Code, VSCode, 最新モデル）
                        score += user_interest_score * 4  # 4倍に重み付け
                    elif user_interest_score >= 1.5:
                        # 高優先度
                        score += user_interest_score * 2.5  # 2.5倍
                    else:
                        # 中・低優先度
                        score += user_interest_score * 2  # 2倍

                # 既存スコアリング（Twitterアカウント以外に適用）
                if "arxiv"   in item["source"]: score += 3
                if "youtube" in item["source"]: score += 2
                score += min(item.get("hn_score", 0) // 100, 3)
                score += min(item.get("stars",    0) // 1000, 2)

                ranked.append({"index": idx, "title": item["title"], "score": round(score, 2)})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return json.dumps(ranked, ensure_ascii=False)

    elif tool_name == "finalize_research":
        return json.dumps({"status": "finalized"})

    return json.dumps({"error": f"未知のツール: {tool_name}"})


# ══════════════════════════════════════════════════════════════
# Agent 1: ThemeSelectorAgent — Haiku
# ══════════════════════════════════════════════════════════════
THEME_SELECTOR_SYSTEM = """あなたは雑誌編集長です。
収集データを見て今日号のテーマと記事構成を設計します。
JSONのみ返してください（前後の説明・```json 不要）。

## 🎯🎯🎯 テーマ選択の優先順位（ユーザー最優先）

**【絶対最高】公式X(Twitter)アカウントの発信（src: "twitter_official" かつ is_official: true）**:
- 🔴🔴🔴 @AnthropicAI — Anthropic公式
- 🔴🔴🔴 @ClaudeAI — Claude公式
- 🔴🔴🔴 @code — Visual Studio Code公式
- 🔴🔴🔴 @MicrosoftCopilot — Microsoft Copilot公式
→ **これらの投稿が存在する場合は、他のどんな情報よりも最優先でテーマに選ぶこと**
→ user_interest_score が 3.0 のアイテムが対象

**最高優先度（user_interest_score 2.0以上）**:
- 🔴 GitHub Copilot のアップデート・新機能・ベストプラクティス
- 🔴 Claude Code / Anthropic の最新モデル・アップデート情報
- 🔴 VSCode のアップデート・AI統合・新機能
- 🔴 GPT-5, Gemini, O1などの最新AIモデルのリリース・性能情報

その次の優先度（user_interest_score 1.5以上）:
- エージェント・スキル評価、トークン最適化、コンテキスト制御
- オーケストレーション、並列処理制御、デバッグツール
- ローカルLLM、エッジデバイス向けモデル

その次（user_interest_score 1.2以上）:
- Azure/AWS/Google Cloud のクラウドAI、RAG設計
- Notion, Obsidian, NotebookLM などのAIアプリ

低優先度：純粋な学術論文の理論的内容

## 構成パターン（最も適切なものを選ぶ）
- spotlight: 【単一ソース深掘り】公式発表・重要リリース1件を徹底解説。背景 → 何が変わるか → 使い方・影響 → 読者へのアクション。複数ソースを無理に集めず、1件の情報を深く掘り下げる。user_interest_score 2.5以上の公式発表があればこれを優先。
- problem_solution: 課題提起 → 解決策の登場 → 実装・効果 → 今後の展望
- discovery: 意外な発見・事実 → 背景の深掘り → 業界への影響 → 読者への示唆
- journey: 現状の限界 → 新技術の登場 → 採用事例・実証 → 次のステージ
- debate: 対立する2つの視点 → それぞれの根拠 → 統合・新解釈 → 読者が取るべき立場
- narrative: ストーリー導入 → 技術的背景 → 転機・驚き → 教訓・展望

出力フォーマット:
{
  "theme": "テーマ（30字以内）",
  "hook": "冒頭フック（読者を引き込む40字以内の一文）",
  "why_now": "なぜ今このテーマか（80字）",
  "structure_type": "problem_solution",
  "structure": {
    "section1": "第1セクションの骨格（何を語るか）",
    "section2": "第2セクションの骨格",
    "section3": "第3セクションの骨格（ここに驚き・核心を置く）",
    "section4": "第4セクションの骨格（読者へのアクション・展望）"
  },
  "key_items": [0, 3, 7],
  "glossary_needed": ["RAG", "MCP"],
  "slug": "keyword-topic-name"
}

slugは記事テーマを表す英小文字3〜5単語のハイフン区切り（例: "needle-agent-distillation", "shepherd-runtime-debug"）。"""

def run_theme_selector(all_items: list[dict]) -> dict:
    # ④ 100字要約＋関心度スコア付き圧縮版を作成
    slim = _slim(all_items, summary_len=100)
    # ★ 関心度の高い順にソート（ThemeSelectorが最初に見るデータを優先度順に）
    slim_sorted = sorted(slim, key=lambda x: x.get("user_interest_score", 0), reverse=True)
    
    resp = client.messages.create(
        model=MODEL_HAIKU, max_tokens=800,   # ① Haiku
        system=THEME_SELECTOR_SYSTEM,
        messages=[{"role": "user",
                   "content": f"収集データ（ユーザー関心度でソート済み）:\n{json.dumps(slim_sorted, ensure_ascii=False)}"}],
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
- 🔴🔴🔴 src="twitter_official" かつ is_official=true のアイテムを「絶対最高」で優先
  （@AnthropicAI / @ClaudeAI / @code / @MicrosoftCopilot の公式投稿）
- 🔴🔴 user_interest_score 2.0以上（GitHub Copilot, Claude Code, VSCode, 最新モデル）のアイテムを最優先
- 各アイテムの user_interest_score を参考に、スコアの高いアイテムを優先的に選ぶ
- search_collected_data でテーマ関連データを検索（1〜2回）
- rank_items_by_novelty で候補を精査（1回）
- 情報が揃ったらすぐ finalize_research を呼ぶ（ループを最小化）
- 選定件数のルール:
  - structure_type が "spotlight" の場合: 主役アイテム1件 + 補足1〜2件（合計1〜3件）で十分。無理に件数を増やさない。
  - それ以外の場合: 5件以上選定してメモを添える"""

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

    indices = finalized.get("selected_indices") or theme.get("key_items", list(range(min(6, len(all_items)))))
    notes   = finalized.get("research_notes") or "（調査メモなし）"
    selected = [all_items[i] for i in indices if 0 <= i < len(all_items)]
    print(f"   [Research] 選定: {len(selected)}件")
    return {"selected_items": selected, "research_notes": notes}


# ══════════════════════════════════════════════════════════════
# Agent 3: WriterAgent — Sonnet（記事品質が核心）
# ══════════════════════════════════════════════════════════════
WRITER_SYSTEM = """あなたはトップクラスのテックライターです。
AIビギナーから最前線エンジニアまで全員が楽しめる雑誌スタイルの記事を書きます。

## 📌 タイトル生成の鉄則（絶対守ること）
1. **シンプルで短い** — 15〜20文字以内。複雑な用語は避ける。
2. **人々の関心を引く** — 「なぜこれを読む必要があるのか」を一目で感じさせる。
   - 例：「○○が変わった」「意外な○○の真実」「今こそ知るべき○○」
   - 避けるべき：技術用語の直訳、抽象的すぎる表現、英語的な複雑な言い回し
3. **日本語として自然** — 英語の直訳は厳禁。日本人が日常で使う言葉を優先。
   - 「〇〇の最適化」より「〇〇を速くする」
   - 「フレームワークの進化」より「新しい〇〇が登場」
4. **検索性を考慮** — ユーザーが検索しそうなキーワードを1つは含める。
5. **新規性を示唆** — 「新」「今」「ついに」など、読者の好奇心をくすぐる言葉を活用。

## ✍️ 日本語表現の鉄則（執筆全体で必須）
- 難しい専門用語を使う場合は、「〜とは」で簡単に解説する
- 文長は最長30文字程度に（長い文は読者を疲れさせる）
- 「〜である」の堅い表現より「〜です」の親しみやすい表現を優先
- 「多くの研究によれば」より「実は」「意外にも」など話し言葉を使う
- 英語の直訳（例：「実装」「活用」「サポート」の誤用）を避け、自然な日本語に
- 見出しは短く（目安：15字以内）、読者が一目で内容を理解できる言葉に

## 執筆の鉄則
1. 論理的な流れで書く — 編集長から渡された構成タイプ（structure_type）に従い、
   読者が自然に次を読みたくなる展開を作る。「起承転結」などのラベルは記事本文に
   一切書かない。セクション見出しは内容を表す言葉にする。
   **structure_type が "spotlight" の場合**: 公式発表・重要リリース1件を主役に据え、
   深く丁寧に解説する。無理に複数ソースをつなげず、「この1件が何をもたらすか」を
   背景・変化・使い方・展望の順で掘り下げる。参考情報は補足程度に留める。
2. フックで心を掴む — 冒頭リード文（2〜3文）で「続きが気になる」と思わせる。
   統計・逆説・問いかけ・具体的なシーンなど引き込み方は自由。
3. 専門用語は必ず解説 — 初出の用語には 💡 用語解説ボックスを付ける。
4. 具体例・比喩で説明 — 抽象的な概念は日常の例えに落とす。
5. 核心セクションに驚きを — 記事の中盤〜後半で読者の予想を裏切る事実・視点を入れる。
   「実は…」「意外にも…」「ところが…」など自然な接続で展開する。
6. 実用的なTips — エンジニアが明日から使えるアクションを含める。
7. 読後感を大切に — 締めで読者に希望・次の一歩・問いを渡す。

## ⏱️ 文字数・読了時間の厳守ルール（最重要）
- **記事全体（本文）は2,000字以内** — 日本語平均読書速度500字/分で計算すると5分以内に読了できる量
- 詳しく書きたい内容は本文には書かず「詳細はこちら → [記事タイトル](URL)」の形で参考リソースへ誘導する
- セクションごとの上限を必ず守ること（下記フォーマット参照）
- 読了時間の表示は実際の文字数から計算した値を使う（必ず5以下）

## 🖼️ 図・画像の使い方（著作権に配慮した引用）

### インライン引用番号
- 本文中でソースを参照するときは `[[n]](URL)` 形式で番号を埋め込む。クリックするとすぐ参照先に飛べる。
  - 例: `Anthropic が発表した新機能 [[1]](https://...) によれば…`
- 参考文献セクションは番号付きリストにして、インライン番号と対応させる。

### YouTube動画の埋め込み
- YouTubeが参照元の場合は **必ず** Zenn の埋め込み記法を使う（再生できる状態で表示される）:
  ```
  @[youtube](VIDEO_ID)
  ```
  VIDEO_ID は URL の `?v=` 以降の11文字。埋め込み直後に出典を記載:
  ```
  *出典: [動画タイトル](https://youtube.com/watch?v=VIDEO_ID)*
  ```

### ブログ・公式発表の画像
- 公式ブログや論文に掲載されている図は、画像URLが分かれば直接引用する:
  ```
  ![図の説明（出典: サービス名）](画像のURL)
  *出典: [記事タイトル](記事URL)*
  ```
- 画像URLが不明な場合は埋め込まず、リンクのみにする。**画像を勝手に再現・模写しない**。

### 自作図（Mermaid）
- 複数の概念の関係性・フローを示すときのみ Mermaid を使う。
- 参照元の図を説明できるなら Mermaid を作らず原典を引用する。

## フォーマット（Markdown）

# {キャッチーなタイトル}

**{日付} | 読了 {分}分 | #{タグ}**

{リード文 — 2〜3文。統計・逆説・問いかけ・具体的なシーンで引き込む（150字以内）}

---

## {セクション1の見出し（内容を表す言葉。「起」などのラベルは使わない）}

（300〜400字。要点のみ。詳細はリンクへ誘導。ソース参照は [[n]](URL) 形式で本文中に入れる）

> 💡 **用語解説**
> **[用語]** — わかりやすい説明（1〜2文）

---

## {セクション2の見出し}

（400〜500字。YouTubeソースがあれば @[youtube](VIDEO_ID) で埋め込む。データ・実装例の要点のみ）

---

## {セクション3の見出し（驚き・核心・課題解決の転機がここに来ることが多い）}

（400〜500字。）

---

## {セクション4の見出し（展望・読者へのアクション）}

（200〜300字。）

---

## 🛠️ エンジニアのための実践Tips

（箇条書き 3個。各項目は1行で完結させる）

---

## 📚 参考文献

1. [タイトル](URL) — 一言説明
2. [タイトル](URL) — 一言説明
（本文中の [[n]] と番号を対応させる）

---
*収集ソース: arXiv, OpenAI/Anthropic Blog, Hacker News, GitHub, YouTube, X(Twitter)*
*{date}*

---

## おわりに

（150〜200字。**【必須セクション・必ず書くこと】筆者の所感として記述する**。
ルール:
• 語尾は「〜のように感じる」「〜のように思う」「〜ではないだろうか」「〜を願っている」など一人称・主観的な言葉を使う
• 記事全体の要約ではなく、この記事を書いて感じたこと・気づき・驚きを伝える
• 読者への問いかけや希望・展望で締める
• 「〜と感じる」「〜と思う」で終わる文を最低1文含めること）"""

def run_writer_agent(theme: dict, research: dict,
                     feedback: str | None = None, attempt: int = 1) -> str:
    glossary = ", ".join(theme.get("glossary_needed", []))
    fb_section = f"\n\n## ⚠️ 編集からの改善指示（第{attempt}稿）\n{feedback}\n" if feedback else ""

    # アイテムは要約 200 字に絞ってトークンを節約
    items_slim = [
        {
            "title": it["title"],
            "url": it.get("url", ""),
            "summary": it.get("summary", "")[:200],
            "source": it["source"],
            "video_id": it.get("video_id", ""),  # YouTube埋め込み用
        }
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
EDITOR_SYSTEM = f"""あなたは雑誌編集長です。記事を6軸で採点し承認 or 差し戻しを判定します。

評価基準（各16〜17点満点・合計 {APPROVE_THRESHOLD}点以上で承認）:
1. fun_novelty      — おもしろさ・新規性
2. clarity          — わかりやすさ（用語解説あるか、日本語が読みやすいか）
3. accuracy         — 正確性・信頼性
4. practicality     — 実用性（明日使えるか）
5. narrative        — 構成の完成度（論理的な流れ・核心セクションに驚きがあるか）
6. japanese_quality — 日本語表現の質（タイトル・見出し・本文は自然で読みやすいか）

## 日本語品質チェック（評価項目6）:
- タイトルが簡潔で読者の興味を引くか（15〜20字目安、複雑な表現がないか）
- 難しい用語は「〜とは」で解説されているか
- 文が長すぎないか（30字以上は避けるべき）
- 「〜です」など親しみやすい表現を使っているか
- 英語の直訳表現が混在していないか（例：「実装する」「活用する」の誤用）
- 全体的に読みやすい、自然な日本語か

JSONのみ返すこと（前後の説明不要）:
{{
  "scores": {{"fun_novelty":0,"clarity":0,"accuracy":0,"practicality":0,"narrative":0,"japanese_quality":0}},
  "total": 0,
  "approved": false,
  "feedback": "差し戻し時の具体的改善指示（承認時は空文字）",
  "highlight_sentence": "SNSシェア用の最良の一文"
}}"""

# ══════════════════════════════════════════════════════════════
# Agent 4.5: JapaneseNativeCheckAgent — Haiku
# ══════════════════════════════════════════════════════════════
JAPANESE_CHECKER_SYSTEM = """あなたは日本語ネイティブの校正者です。
テックライターが書いた記事のタイトル・見出し・本文を精査し、
より読みやすく、わかりやすい自然な日本語に修正します。

## チェック項目
1. タイトルが簡潔で興味を引くか（15〜20字、複雑な表現がないか）
2. 見出しが短く、内容を一目で理解できるか（目安：15字以内）
3. 文が長すぎないか（30字以上は短く分割を提案）
4. 難しい直訳表現があれば、自然な日本語に修正
   - 「実装する」「活用する」など英語的な表現を日本語に
5. 専門用語が十分に解説されているか
6. 全体の読みやすさ（話し言葉を活用しているか）

## 出力フォーマット（JSON のみ）
{
  "title_suggestion": "修正されたタイトル（修正不要なら元のまま）",
  "corrections": [
    {"original": "修正前の表現", "corrected": "修正後の表現", "reason": "理由"},
    ...
  ],
  "corrected_article": "日本語が修正された記事全体（Markdown形式）",
  "notes": "その他の提案・コメント"
}"""

def run_japanese_native_checker(article: str, theme: dict) -> str:
    """日本語表現のネイティブチェック"""
    article_head = article[:3000]  # 先頭部分で充分判定可能
    resp = client.messages.create(
        model=MODEL_HAIKU, max_tokens=2500,
        system=JAPANESE_CHECKER_SYSTEM,
        messages=[{"role": "user", "content":
                   f"テーマ: {theme['theme']}\n\n記事:\n{article_head}"}],
    )
    _log_cost("JapaneseNativeChecker(Haiku)", resp)
    try:
        checked = json.loads(_strip_json(resp.content[0].text))
        # タイトル修正提案があれば適用
        if checked.get("title_suggestion"):
            title_new = checked["title_suggestion"]
            article = re.sub(r"^# .+$", f"# {title_new}", article, count=1, flags=re.MULTILINE)
        # 本文の修正を適用
        if checked.get("corrected_article"):
            article = checked["corrected_article"]
        print(f"   [JapaneseChecker] 修正完了（{len(checked.get('corrections', []))}件の改善）")
    except Exception as e:
        print(f"   [JapaneseChecker] スキップ（パース失敗: {str(e)[:50]}）")
    return article


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
def orchestrate(all_items: list[dict]) -> tuple[str, dict, dict]:
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

        print(f"\n🔤 [Orchestrator] JapaneseNativeCheckAgent (Haiku) 第{attempt}稿「日本語」チェック")
        article = run_japanese_native_checker(article, theme)

        reading_min = _estimate_reading_time(article)
        print(f"   [ReadingTime] 推定読了時間: {reading_min:.1f}分")
        if reading_min > READING_TIME_LIMIT_MIN:
            print(f"\n✂️  [Orchestrator] SummarizerAgent (Haiku) — {reading_min:.1f}分 → 5分以内に圧縮")
            article = run_summarizer_agent(article, theme, reading_min)
            reading_min_after = _estimate_reading_time(article)
            print(f"   [ReadingTime] 圧縮後: {reading_min_after:.1f}分")

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

    return article, quality, theme


# ══════════════════════════════════════════════════════════════
# Agent 5: SummarizerAgent — Haiku（読了時間超過時に圧縮）
# ══════════════════════════════════════════════════════════════
SUMMARIZER_SYSTEM = f"""あなたは優秀な編集者です。
記事の読了時間が{READING_TIME_LIMIT_MIN}分を超えているため、{READING_TIME_LIMIT_MIN}分以内（本文2,000字以内）に圧縮してください。

## 圧縮ルール
1. **各セクションを半分程度に削る** — 要点だけ残し、説明的な文章を削除する
2. **詳細はリンクへ誘導** — 削った内容は「詳細は → [タイトル](URL)」の形で参考リソースへ誘導する
3. **リード文・タイトル・見出しは変えない** — 読者の興味を引く部分はそのまま残す
4. **Tips は3個まで** — 各項目は1行で完結させる
5. **フロントマター（---で囲まれた部分）は一切変更しない**
6. **「読了 X分」の表示を実際の圧縮後の文字数に合わせて更新する**（必ず5以下）
7. **「## おわりに」セクションは削除しない** — 筆者の所感として必須のセクション

圧縮後の記事全体（Markdownそのまま）を返してください。前後の説明は不要。"""

def run_summarizer_agent(article: str, theme: dict, current_min: float) -> str:
    """読了時間が5分を超える場合に記事を圧縮する"""
    resp = client.messages.create(
        model=MODEL_HAIKU, max_tokens=3000,
        system=SUMMARIZER_SYSTEM,
        messages=[{"role": "user", "content":
                   f"現在の推定読了時間: {current_min:.1f}分\n\n"
                   f"テーマ: {theme['theme']}\n\n"
                   f"記事:\n{article}"}],
    )
    _log_cost("Summarizer(Haiku)", resp)
    return resp.content[0].text


def _estimate_reading_time(article: str) -> float:
    """記事の推定読了時間（分）を返す"""
    # フロントマターを除去
    text = re.sub(r"^---\n.*?\n---\n", "", article, flags=re.DOTALL)
    # Markdownシンタックスを除去
    text = re.sub(r"[#*`>\-\[\]()!]", "", text)
    # URLを除去
    text = re.sub(r"https?://\S+", "", text)
    # 空白を除去してピュアテキスト文字数を数える
    text = re.sub(r"\s+", "", text)
    return len(text) / CHARS_PER_MIN


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

    article, quality, theme = orchestrate(all_items)

    # slug: ThemeSelectorの出力を優先、なければタイトルから英数字を抽出
    slug_part = theme.get("slug", "")
    slug_part = re.sub(r"[^a-z0-9-]+", "", slug_part.lower())[:50].strip("-")
    if not slug_part:
        title_match_slug = re.search(r"^# (.+)$", article, re.MULTILINE)
        raw_title = title_match_slug.group(1) if title_match_slug else "ai-agent-news"
        slug_part = re.sub(r"[^a-zA-Z0-9]+", "-", raw_title)[:40].strip("-").lower()
    if not slug_part:
        slug_part = "ai-agent"

    article_path = ARTICLES_DIR / f"{TODAY}-{slug_part}.md"

    # タイトル抽出
    title_match = re.search(r"^# (.+)$", article, re.MULTILINE)
    title = title_match.group(1) if title_match else f"AIエージェント最前線 {TODAY}"

    approved      = quality.get("approved", False)
    quality_score = quality.get("total", 0)
    highlight     = quality.get("highlight_sentence", "").replace('"', '\\"')
    scores_json   = json.dumps(quality.get("scores", {}), ensure_ascii=False)

    # Zennフロントマター（追加フィールドはZennが無視する）
    frontmatter = (
        f'---\n'
        f'title: "{title}"\n'
        f'emoji: "🤖"\n'
        f'type: "tech"\n'
        f'topics: ["AIエージェント", "LLM", "Claude", "機械学習", "生成AI"]\n'
        f'published: {str(approved).lower()}\n'
        f'quality_score: {quality_score}\n'
        f'approved: {str(approved).lower()}\n'
        f'date: "{TODAY}"\n'
        f'highlight_sentence: "{highlight}"\n'
        f'scores: {scores_json}\n'
        f'---\n\n'
    )

    with open(article_path, "w", encoding="utf-8") as f:
        f.write(frontmatter + article)

    print(f"\n✅ 記事生成完了 → {article_path}")
    print(f"   品質スコア: {quality_score}/100")
    print(f"   ハイライト: {highlight[:60]}...")

    if not approved:
        print("⚠️  品質未承認 → 投稿スキップ（published: false で保存）")
        exit(1)

    print("🚀 投稿準備完了")


if __name__ == "__main__":
    main()
