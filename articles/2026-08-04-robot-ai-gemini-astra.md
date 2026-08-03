---
title: "ロボットが「考えて動く」時代が来た"
emoji: "🤖"
type: "tech"
topics: ["AIエージェント", "LLM", "Claude", "機械学習", "生成AI"]
published: true
quality_score: 80
approved: true
date: "2026-08-04"
highlight_sentence: "ロボットが動画を見て状況を判断し、複数台で役割を分担しながら作業する光景が、もう実験室の外に出ようとしている。"
scores: {"fun_novelty": 14, "clarity": 13, "accuracy": 15, "practicality": 12, "narrative": 14, "japanese_quality": 12}
---

# ロボットが「考えて動く」時代が来た

**2026-08-04 | 読了 4分 | #ロボットAI #Gemini #OpenAI**

ロボットが動画を見て状況を判断し、複数台で役割を分担しながら作業する。そんな光景が、もう実験室の外に出ようとしている。Google DeepMindとOpenAIが相次いで公開した成果は、AIが「考える」から「動く」へ本格シフトしたことを示している。

---

## Googleが見せた「全身で考えるロボット」

Google DeepMindが公開した **Gemini Robotics ER 2** [[1]](https://deepmind.google/blog/gemini-robotics-er-2-powering-robotics-with-video-understanding-task-orchestration-and-multi-robot-collaboration/) は、従来のロボットAIを大きく超えた。

**① 動画を理解して動く**
カメラ映像をリアルタイムで解析し、環境の変化に即応する。

**② 複数台が自律的に協力する**
ロボット同士が役割を自動調整しながら作業を完了。

**③ 全身を使った動作計画**
腕だけでなく全身を連携させて、人間にとって当たり前の複雑な動きが可能に。

詳細は → [Gemini Robotics 2: whole body intelligence](https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/)

---

## OpenAIの「数学が解けるロボット脳」

OpenAIの未公開モデル **Astra** は、未解決の数学問題10件を解いた [[2]](https://thezvi.substack.com/p/openais-unreleased-model-astra-solves)。ロボットの実用化には「見る力」と同時に「論理的に考える力」が必要。工場ラインの予期せぬトラブル対応など、複雑な推論が求められる現場でこの能力が活躍する。

OpenAIのアプローチは、「どこでも持ち込める推論エンジン」としてロボットの頭脳を担う戦略だと読める。

---

## 「見る力」vs「考える力」、実は「つなぐ力」が勝負

Googleは知覚優位：現実世界のセンサー情報を重視。工場・物流に強い。

OpenAIは推論優位：高度な論理推論をベース。ハードウェアメーカーとの協業前提。

**現場の課題は、映像を行動計画に変換する橋渡し部分。** Gemini ER 2は「動画理解」で、Astraは「強力な推論」で解こうとしている。2026年後半、どちらが現場で機能するかが正念場になる。

---

## 🛠️ エンジニアのための実践Tips

- **現場の映像データを整理する** — Gemini系モデルの学習素材になる可能性がある
- **Omnigent などのマルチエージェントフレームワークを試す** [[3]](https://github.com/omnigent-ai/omnigent) — 複数ロボット管理の実装経験を積む
- **推論モデルと知覚モデルを分けた設計に慣れる** — モジュール構成が業界標準になりつつある

---

## 📚 参考文献

1. [Gemini Robotics ER 2](https://deepmind.google/blog/gemini-robotics-er-2-powering-robotics-with-video-understanding-task-orchestration-and-multi-robot-collaboration/) — Google DeepMind
2. [OpenAI's Astra Solves Open Mathematics Problems](https://thezvi.substack.com/p/openais-unreleased-model-astra-solves) — Zvi Mowshowitz分析
3. [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent) — マルチエージェント管理フレームワーク

---

## おわりに

「ロボットが考えながら動く」という言葉は、つい最近まで漠然とした未来の話だと思っていた。ところが今回、その未来がすでに「どちらの実装が正しいか議論する段階」に来ていることに驚いた。知覚か推論か、GoogleかOpenAIか——この問いが現場エンジニアにとってリアルな選択になっている。ロボットと人間が同じ空間で協力する日常が思ったより早く来るのではないか、と感じている。あなたの現場では、どちらのアプローチが刺さるだろうか。