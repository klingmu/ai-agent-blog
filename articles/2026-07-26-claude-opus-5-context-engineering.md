---
title: "プロンプト設計の常識が変わった"
emoji: "🤖"
type: "tech"
topics: ["AIエージェント", "LLM", "Claude", "機械学習", "生成AI"]
published: true
quality_score: 78
approved: true
date: "2026-07-26"
highlight_sentence: "モデルの性能が上がるほど、人間側がやるべき仕事は「細かい言葉の調整」から「情報アーキテクチャの設計」へと移っていきます。"
scores: {"fun_novelty": 14, "clarity": 13, "accuracy": 12, "practicality": 14, "narrative": 13, "japanese_quality": 12}
---

# プロンプト設計の常識が変わった

**2026-07-26 | 読了 4分 | #Claude #AI #ContextEngineering**

「いいプロンプトを書けばいい」——その時代が終わりつつある。Claude Opus 5の登場で、AIとの対話を設計する考え方そのものが刷新された。今すぐ知らないと、既存のパイプラインが丸ごと時代遅れになるかもしれない。

---

## Opus 5で何が変わったのか

Anthropicが2026年7月に発表したClaude Opus 5は、単なる性能向上にとどまらない。**コンテキストの扱い方が根本から変わった**のです。

前世代までは「文字数」や「位置」の工夫が必要でした。ところがOpus 5は長いコンテキストでも重要情報を取りこぼしにくくなり、「何をどう渡すか」という設計の質が問われるようになりました。

詳細は → [Introducing Claude Opus 5](https://www.anthropic.com/news/claude-opus-5)

> 💡 **Context Engineering** — モデルに渡す「文脈全体」を、情報の種類・量・構造・順序を総合的に最適化して設計する手法。

---

## 古いプロンプト技法が通用しない理由

新時代のポイントは一つ：

- **旧時代**：「どう言えば伝わるか（言葉の工夫）」
- **新時代**：「何を・どんな形で・いつ渡すか（情報設計）」

主な変更ルール：

**① システムプロンプトは構造化する** — 箇条書きや見出しでセクション分けし、役割・制約・出力形式を明確に分離する。

**② 段階的に指示を渡す** — 一度に大量の指示を詰め込まず、タスクの流れに沿ってコンテキストを順番に積み上げる。

**③ 出力フォーマットを具体的に指定する** — JSONのキー名・ネスト構造・文字数制限まで明示すると精度が上がる。

詳細は → [The new rules of context engineering](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)

---

## 開発者が今すぐやるべき3つの調整

**転機①：プロンプトの再設計**
「繰り返しで強調」「重要事項を冒頭に詰め込む」といった古いテクニックは逆効果になりえます。冗長な繰り返しがノイズになり、精度を下げるケースも報告されています。不要な情報を削ぎ落とす作業が必須です。

**転機②：トークン配分の見直し**
「長く書けばいい」ではなく「高品質な情報を必要最小限に」が正解。RAG（検索拡張生成）で関連文書だけを絞り込むなどの工夫がより重要になります。

**転機③：検証フローの再構築**
従来の評価セットがOpus 5では意図した通りに動かないケースがあります。本番移行前に小規模で評価し直すことを推奨します。

---

## Opus 5前提の新しいワークフローへ

モデルの性能が上がるほど、人間側がやるべき仕事は「細かい言葉の調整」から「情報アーキテクチャの設計」へと移っていきます。

実践の出発点として、Anthropicが公開している **Claude Cookbook** が役立ちます。Context Engineeringの実例が多数収録されています。

詳細は → [Claude Cookbook](https://platform.claude.com/cookbook/)

---

## 🛠️ エンジニアのための実践Tips

- **既存のシステムプロンプトを見直す** — 繰り返しや過剰な制約を削ぎ落とし、構造化された記述に書き直す
- **Claude Cookbookを1つ試す** — Context Engineering実例をそのまま動かしてみる
- **評価セットを小さく作り直す** — Opus 5専用の10〜20件のテストケースで移行前後の挙動を確認する

---

## 📚 参考文献

1. [Introducing Claude Opus 5](https://www.anthropic.com/news/claude-opus-5) — Anthropic公式発表
2. [The new rules of context engineering](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models) — AnthropicのContext Engineering新ガイドライン
3. [Claude Cookbook](https://platform.claude.com/cookbook/) — 実装レシピ集

---

## おわりに

「プロンプトが上手い人」が強い時代から、「情報をどう設計するかを考えられる人」が強い時代へ——Opus 5の登場でその流れが一気に加速したように感じる。言葉の工夫より、構造の工夫。これはAIとの付き合い方だけでなく、エンジニアリング全般の本質に近いのではないだろうか。Context Engineeringという考え方が、開発者にとって当たり前の教養になる日が楽しみでもあり、少し背筋が伸びる思いもする。あなたのプロンプト設計は、もう時代に合っていますか？