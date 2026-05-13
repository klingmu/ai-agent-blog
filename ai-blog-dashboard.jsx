import { useState } from "react";

const agents = [
  {
    id: "theme",
    name: "ThemeSelectorAgent",
    icon: "🎯",
    color: "#F59E0B",
    role: "テーマ設計・起承転結の骨格を作る",
    detail: "収集データ全件を俯瞰し、今日最もインパクトのある「一つのテーマ」を選定。フック文・起承転結の骨格・必要な用語解説リストを出力する。",
    output: "theme.json（テーマ / 起承転結 / フック文 / 用語リスト）",
    tools: [],
    calls: "1回（単発）",
  },
  {
    id: "research",
    name: "ResearchAgent",
    icon: "🔍",
    color: "#60A5FA",
    role: "tool_use ループで情報を自律収集",
    detail: "テーマに関係するデータが揃うまで自律的にツールを呼び続ける。情報不足なら追加検索し、新規性でランキング。揃ったら finalize_research を呼んでループ終了。",
    output: "selected_items[] + research_notes",
    tools: ["search_collected_data", "get_item_detail", "rank_items_by_novelty", "finalize_research"],
    calls: "最大10ターン（tool_use ループ）",
  },
  {
    id: "writer",
    name: "WriterAgent",
    icon: "✍️",
    color: "#34D399",
    role: "雑誌スタイルの記事を執筆",
    detail: "起承転結の骨格・リサーチノート・選定アイテムをもとに記事を執筆。初心者向け用語解説・比喩・具体例を必ず含め、転で読者を驚かせるドラマを作る。EditorAgentに差し戻されたら改稿する。",
    output: "Markdown 記事本文（3000〜5000字）",
    tools: [],
    calls: "最大3回（差し戻し時に再稿）",
  },
  {
    id: "editor",
    name: "EditorAgent",
    icon: "🔎",
    color: "#F472B6",
    role: "品質評価 → 承認 or 差し戻し",
    detail: "5軸（おもしろさ・わかりやすさ・正確性・実用性・起承転結）で100点満点採点。75点以上で承認、未満はフィードバック付きで WriterAgent に差し戻す。",
    output: "scores / total / approved / feedback / highlight_sentence",
    tools: [],
    calls: "最大3回（WriterAgent と対で動く）",
  },
];

const newFeatures = [
  { icon: "🤖", label: "エージェント化", desc: "tool_use ループで自律的に情報収集。情報不足なら追加検索、揃ったら自動で完了判定。" },
  { icon: "📺", label: "YouTube収集", desc: "YouTube Data API v3で最新AI解説動画・Shortsを収集。動画情報も記事の参考ソースに。" },
  { icon: "📰", label: "雑誌スタイル", desc: "初心者からエキスパートまで全員が楽しめる。専門用語解説ボックス・比喩・具体例を必ず含む。" },
  { icon: "🎭", label: "起承転結", desc: "毎回「一つのテーマ」を決め、転で驚きを、結で希望を渡すストーリー記事を生成。" },
  { icon: "📊", label: "5軸品質評価", desc: "おもしろさ・わかりやすさ・正確性・実用性・起承転結の5軸で100点満点採点。75点以上のみ投稿。" },
  { icon: "🔄", label: "自動差し戻し", desc: "EditorAgentが不合格なら WriterAgent に具体的フィードバックを渡して最大3回再稿。" },
];

const setupItems = [
  { key: "ANTHROPIC_API_KEY", required: true, desc: "Anthropic コンソールで発行" },
  { key: "GH_TOKEN", required: true, desc: "repo権限付き GitHub PAT" },
  { key: "YOUTUBE_API_KEY", required: false, desc: "Google Cloud Console で YouTube Data API v3 を有効化して発行。なくても動作します" },
  { key: "SLACK_WEBHOOK_URL", required: false, desc: "Slack Incoming Webhook URL（投稿通知）" },
  { key: "WP_URL / WP_USER / WP_APP_PASSWORD", required: false, desc: "WordPress 投稿を使う場合のみ" },
];

export default function Dashboard() {
  const [activeAgent, setActiveAgent] = useState(null);
  const [tab, setTab] = useState("arch");

  return (
    <div style={{
      minHeight: "100vh",
      background: "#080C14",
      color: "#CBD5E1",
      fontFamily: "'IBM Plex Mono', monospace",
    }}>
      <div style={{
        padding: "20px 28px",
        borderBottom: "1px solid #0F1F35",
        display: "flex", alignItems: "center", gap: 14,
        background: "linear-gradient(90deg, #0D1B2E 0%, #080C14 100%)",
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: 8, fontSize: 20,
          background: "linear-gradient(135deg, #F59E0B, #F472B6)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>🤖</div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9" }}>
            AI Agent Daily Blog
            <span style={{ fontSize: 11, color: "#F59E0B", marginLeft: 8, fontWeight: 400 }}>v2 — Agentic</span>
          </div>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 1 }}>
            4エージェント × tool_use ループ × 雑誌スタイル起承転結
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {[["arch", "エージェント構成"], ["new", "変更点"], ["setup", "セットアップ"]].map(([t, label]) => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding: "5px 12px", borderRadius: 6, cursor: "pointer",
              border: "1px solid", fontFamily: "inherit", fontSize: 11,
              borderColor: tab === t ? "#F59E0B" : "#1E293B",
              background: tab === t ? "rgba(245,158,11,0.1)" : "transparent",
              color: tab === t ? "#F59E0B" : "#475569",
            }}>{label}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: "28px", maxWidth: 960, margin: "0 auto" }}>

        {tab === "arch" && (
          <>
            <div style={{ fontSize: 11, color: "#334155", letterSpacing: "0.12em", marginBottom: 20 }}>
              AGENTIC PIPELINE  ─  毎朝 6:00 JST 自動実行
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {agents.map((ag, i) => (
                <div key={ag.id}>
                  <div
                    onClick={() => setActiveAgent(activeAgent === ag.id ? null : ag.id)}
                    style={{
                      display: "flex", alignItems: "flex-start", gap: 16,
                      padding: "16px 20px", cursor: "pointer",
                      border: "1px solid",
                      borderColor: activeAgent === ag.id ? ag.color + "55" : "#0F1F35",
                      borderRadius: activeAgent === ag.id ? "10px 10px 0 0" : 10,
                      background: activeAgent === ag.id ? ag.color + "08" : "#0D1B2E",
                      marginBottom: activeAgent === ag.id ? 0 : 8,
                      transition: "all 0.2s",
                    }}
                  >
                    <div style={{
                      width: 40, height: 40, borderRadius: "50%", fontSize: 18,
                      border: `2px solid ${ag.color}`,
                      background: ag.color + "18",
                      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    }}>{ag.icon}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: ag.color }}>{ag.name}</span>
                        <span style={{
                          fontSize: 10, padding: "2px 8px", borderRadius: 4,
                          background: ag.color + "18", color: ag.color,
                        }}>{ag.calls}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "#64748B" }}>{ag.role}</div>
                    </div>
                    <span style={{ color: "#334155", fontSize: 12, marginTop: 10 }}>
                      {activeAgent === ag.id ? "▲" : "▼"}
                    </span>
                  </div>
                  {activeAgent === ag.id && (
                    <div style={{
                      padding: "16px 20px",
                      background: "#070B14",
                      border: `1px solid ${ag.color}55`,
                      borderTop: "none",
                      borderRadius: "0 0 10px 10px",
                      marginBottom: 8,
                    }}>
                      <p style={{ fontSize: 13, color: "#94A3B8", lineHeight: 1.7, marginBottom: 12 }}>{ag.detail}</p>
                      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
                        <div>
                          <div style={{ fontSize: 10, color: "#334155", marginBottom: 6, letterSpacing: "0.1em" }}>OUTPUT</div>
                          <code style={{ fontSize: 11, color: ag.color }}>{ag.output}</code>
                        </div>
                        {ag.tools.length > 0 && (
                          <div>
                            <div style={{ fontSize: 10, color: "#334155", marginBottom: 6, letterSpacing: "0.1em" }}>TOOLS</div>
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                              {ag.tools.map(t => (
                                <span key={t} style={{
                                  fontSize: 10, padding: "2px 8px", borderRadius: 4,
                                  background: "#0F1F35", color: "#60A5FA", border: "1px solid #1E3A5F",
                                }}>{t}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {i < agents.length - 1 && (
                    <div style={{ textAlign: "center", color: "#1E293B", fontSize: 16, margin: "0 0 8px" }}>↓</div>
                  )}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 20, padding: "16px 20px", background: "#0D1B2E", border: "1px solid #0F1F35", borderRadius: 10 }}>
              <div style={{ fontSize: 11, color: "#334155", letterSpacing: "0.1em", marginBottom: 12 }}>WRITER ↔ EDITOR LOOP（最大3回）</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                {[
                  { label: "✍️ 執筆", color: "#34D399" },
                  { label: "→", color: "#334155" },
                  { label: "🔎 採点（/100）", color: "#F472B6" },
                  { label: "→", color: "#334155" },
                  { label: "✅ 75点以上 投稿", color: "#4ADE80" },
                  { label: "↩️ 未満 差し戻し", color: "#F87128" },
                ].map((x, i) => (
                  x.label === "→" ? <span key={i} style={{ color: x.color }}>{x.label}</span> :
                  <div key={i} style={{
                    padding: "7px 12px", borderRadius: 7,
                    border: `1px solid ${x.color}44`, background: x.color + "08",
                    fontSize: 12, color: x.color,
                  }}>{x.label}</div>
                ))}
              </div>
              <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
                {["おもしろさ/20", "わかりやすさ/20", "正確性/20", "実用性/20", "起承転結/20"].map(s => (
                  <span key={s} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 4, background: "#0F1F35", color: "#475569" }}>{s}</span>
                ))}
              </div>
            </div>
          </>
        )}

        {tab === "new" && (
          <>
            <div style={{ fontSize: 11, color: "#334155", letterSpacing: "0.12em", marginBottom: 20 }}>WHAT'S NEW IN v2</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
              {newFeatures.map(f => (
                <div key={f.label} style={{
                  padding: "16px 18px", background: "#0D1B2E", border: "1px solid #0F1F35", borderRadius: 10,
                }}>
                  <div style={{ fontSize: 20, marginBottom: 8 }}>{f.icon}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#F1F5F9", marginBottom: 6 }}>{f.label}</div>
                  <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.6 }}>{f.desc}</div>
                </div>
              ))}
            </div>
            <div style={{ padding: "18px 20px", background: "#0D1B2E", border: "1px solid #0F1F35", borderRadius: 10 }}>
              <div style={{ fontSize: 11, color: "#334155", letterSpacing: "0.1em", marginBottom: 14 }}>NEW ARTICLE STRUCTURE</div>
              {[
                { icon: "🔮", label: "起", desc: "背景・問題提起（初心者にも伝わる言葉で）＋ 用語解説ボックス" },
                { icon: "🔍", label: "承", desc: "深掘り・証拠（論文・実装例・動画ソース）" },
                { icon: "⚡", label: "転", desc: "意外な視点・反転・ドラマ ← ここが記事の核心" },
                { icon: "🚀", label: "結", desc: "読者への示唆・実践Tips・次のアクション・希望" },
              ].map((s, i, arr) => (
                <div key={s.label} style={{
                  display: "flex", alignItems: "flex-start", gap: 14,
                  padding: "10px 0",
                  borderBottom: i < arr.length - 1 ? "1px solid #0F1F35" : "none",
                }}>
                  <span style={{ fontSize: 18 }}>{s.icon}</span>
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "#F59E0B", marginRight: 8 }}>{s.label}</span>
                    <span style={{ fontSize: 12, color: "#475569" }}>{s.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "setup" && (
          <>
            <div style={{ fontSize: 11, color: "#334155", letterSpacing: "0.12em", marginBottom: 20 }}>SETUP GUIDE</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
              {setupItems.map(s => (
                <div key={s.key} style={{
                  display: "flex", alignItems: "flex-start", gap: 14,
                  padding: "14px 18px", background: "#0D1B2E", border: "1px solid #0F1F35", borderRadius: 8,
                }}>
                  <span style={{
                    fontSize: 10, padding: "2px 8px", borderRadius: 4, flexShrink: 0, marginTop: 2,
                    background: s.required ? "rgba(239,68,68,0.15)" : "rgba(100,116,139,0.1)",
                    color: s.required ? "#F87171" : "#475569",
                  }}>{s.required ? "必須" : "任意"}</span>
                  <div>
                    <code style={{ fontSize: 12, color: "#60A5FA", display: "block", marginBottom: 4 }}>{s.key}</code>
                    <div style={{ fontSize: 12, color: "#475569" }}>{s.desc}</div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{
              padding: "14px 18px", background: "rgba(245,158,11,0.06)",
              border: "1px solid rgba(245,158,11,0.2)", borderRadius: 10,
              fontSize: 12, color: "#64748B", lineHeight: 1.8, marginBottom: 12,
            }}>
              💡 <strong style={{ color: "#F59E0B" }}>YouTube API なしでも動作します。</strong><br />
              未設定の場合、YouTube収集はスキップされ arXiv・RSS・HN・GitHub のみで記事を生成。
            </div>
            <div style={{ padding: "16px 18px", background: "#0D1B2E", border: "1px solid #0F1F35", borderRadius: 10 }}>
              <div style={{ fontSize: 11, color: "#334155", marginBottom: 10, letterSpacing: "0.1em" }}>💰 月額コスト目安（v2）</div>
              <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 24, color: "#4ADE80", fontWeight: 700 }}>$15〜40</div>
                  <div style={{ fontSize: 11, color: "#334155" }}>/ 月</div>
                </div>
                <div style={{ fontSize: 12, color: "#475569", lineHeight: 1.8 }}>
                  Claude API: ~$0.50〜1.30/日（エージェントループ増加分）<br />
                  YouTube Data API: 無料枠（1万クォータ/日）内<br />
                  GitHub Actions: 無料枠内
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
