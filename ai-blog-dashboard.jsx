import { useState } from "react";

const steps = [
  {
    id: 1,
    icon: "⑁",
    label: "リポジトリ作成",
    status: "todo",
    detail: "GitHubで新規リポジトリを作成し、提供ファイル一式をコミット",
    code: `git clone https://github.com/your-name/ai-agent-blog
cd ai-agent-blog
pip install -r requirements.txt`,
  },
  {
    id: 2,
    icon: "⑂",
    label: "Secrets 設定",
    status: "todo",
    detail: "GitHub → Settings → Secrets and variables → Actions",
    secrets: [
      { name: "ANTHROPIC_API_KEY", required: true, desc: "Anthropic コンソールで発行" },
      { name: "GH_TOKEN", required: true, desc: "repo権限付きPAT" },
      { name: "SLACK_WEBHOOK_URL", required: false, desc: "通知用（任意）" },
    ],
  },
  {
    id: 3,
    icon: "⑃",
    label: "Zenn 連携",
    status: "todo",
    detail: "zenn.dev → GitHubリポジトリ連携 → このリポジトリを選択",
    code: `# zenn/articles/ 以下の .md が自動公開されます`,
  },
  {
    id: 4,
    icon: "⑄",
    label: "動作確認",
    status: "todo",
    detail: "Actions → Daily AI Agent Blog → Run workflow → dry_run ON",
    code: `# ローカルテストも可能
ANTHROPIC_API_KEY=sk-ant-xxx python scripts/collect.py
ANTHROPIC_API_KEY=sk-ant-xxx python scripts/generate.py`,
  },
  {
    id: 5,
    icon: "⑅",
    label: "本番運用開始",
    status: "todo",
    detail: "毎朝 6:00 JST に自動実行。Slack に投稿通知が届きます",
    code: `# cron: "0 21 * * *"  ← .github/workflows/daily-blog.yml`,
  },
];

const arch = [
  { id: "collect", label: "collect.py", color: "#4ADE80", desc: "arXiv / RSS / HN / GitHub", icon: "📥" },
  { id: "generate", label: "generate.py", color: "#60A5FA", desc: "スコアリング → 記事生成 → 品質チェック", icon: "✍️" },
  { id: "publish", label: "publish.py", color: "#F472B6", desc: "Zenn / WordPress / Slack通知", icon: "🚀" },
];

const files = [
  { path: ".github/workflows/daily-blog.yml", desc: "GitHub Actions ワークフロー（cron 毎朝6時）" },
  { path: "scripts/collect.py", desc: "情報収集（arXiv, RSS, Hacker News, GitHub）" },
  { path: "scripts/generate.py", desc: "Claude APIで整理・記事生成・品質チェック" },
  { path: "scripts/publish.py", desc: "Zenn/WordPress投稿 & Slack通知" },
  { path: "requirements.txt", desc: "Python依存ライブラリ" },
  { path: "README.md", desc: "セットアップガイド（詳細）" },
];

export default function Dashboard() {
  const [activeStep, setActiveStep] = useState(null);
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [tab, setTab] = useState("setup");

  const toggle = (id) => {
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const progress = Math.round((completedSteps.size / steps.length) * 100);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0A0A0F",
      color: "#E2E8F0",
      fontFamily: "'IBM Plex Mono', 'Courier New', monospace",
      padding: "0",
    }}>
      {/* Header */}
      <div style={{
        borderBottom: "1px solid #1E293B",
        padding: "24px 32px",
        display: "flex",
        alignItems: "center",
        gap: "16px",
        background: "linear-gradient(90deg, #0F172A 0%, #0A0A0F 100%)",
      }}>
        <div style={{
          width: 40, height: 40,
          background: "linear-gradient(135deg, #4ADE80, #60A5FA)",
          borderRadius: 8,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 20,
        }}>🤖</div>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: "0.05em", color: "#F1F5F9" }}>
            AI Agent Daily Blog
          </div>
          <div style={{ fontSize: 11, color: "#64748B", marginTop: 2 }}>
            自動収集 → 記事生成 → 毎朝投稿システム
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {["setup", "arch", "files"].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: "6px 14px",
                borderRadius: 6,
                border: "1px solid",
                borderColor: tab === t ? "#4ADE80" : "#1E293B",
                background: tab === t ? "rgba(74,222,128,0.1)" : "transparent",
                color: tab === t ? "#4ADE80" : "#64748B",
                cursor: "pointer",
                fontSize: 11,
                fontFamily: "inherit",
                letterSpacing: "0.05em",
              }}
            >
              {t === "setup" ? "セットアップ" : t === "arch" ? "構成図" : "ファイル一覧"}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: "32px", maxWidth: 900, margin: "0 auto" }}>

        {/* ── セットアップタブ ── */}
        {tab === "setup" && (
          <>
            {/* Progress */}
            <div style={{ marginBottom: 28 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 11, color: "#64748B", letterSpacing: "0.1em" }}>SETUP PROGRESS</span>
                <span style={{ fontSize: 11, color: "#4ADE80" }}>{completedSteps.size}/{steps.length} 完了</span>
              </div>
              <div style={{ height: 4, background: "#1E293B", borderRadius: 2 }}>
                <div style={{
                  height: "100%",
                  width: `${progress}%`,
                  background: "linear-gradient(90deg, #4ADE80, #60A5FA)",
                  borderRadius: 2,
                  transition: "width 0.4s ease",
                }} />
              </div>
            </div>

            {/* Steps */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {steps.map((step) => {
                const done = completedSteps.has(step.id);
                const open = activeStep === step.id;
                return (
                  <div key={step.id} style={{
                    border: "1px solid",
                    borderColor: done ? "#166534" : open ? "#1E3A5F" : "#1E293B",
                    borderRadius: 10,
                    background: done ? "rgba(74,222,128,0.04)" : open ? "rgba(96,165,250,0.04)" : "#0F172A",
                    overflow: "hidden",
                    transition: "all 0.2s",
                  }}>
                    <div
                      onClick={() => setActiveStep(open ? null : step.id)}
                      style={{
                        display: "flex", alignItems: "center", gap: 14,
                        padding: "14px 18px", cursor: "pointer",
                      }}
                    >
                      <button
                        onClick={(e) => { e.stopPropagation(); toggle(step.id); }}
                        style={{
                          width: 22, height: 22,
                          borderRadius: "50%",
                          border: "2px solid",
                          borderColor: done ? "#4ADE80" : "#334155",
                          background: done ? "#4ADE80" : "transparent",
                          cursor: "pointer",
                          flexShrink: 0,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          color: "#0A0A0F",
                          fontSize: 12,
                          fontWeight: 700,
                        }}
                      >{done ? "✓" : ""}</button>
                      <span style={{ fontSize: 13, color: done ? "#4ADE80" : "#94A3B8", minWidth: 24 }}>
                        STEP {step.id}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: done ? "#4ADE80" : "#E2E8F0" }}>
                        {step.label}
                      </span>
                      <span style={{ marginLeft: "auto", color: "#334155", fontSize: 12 }}>
                        {open ? "▲" : "▼"}
                      </span>
                    </div>
                    {open && (
                      <div style={{ padding: "0 18px 18px 54px" }}>
                        <p style={{ fontSize: 13, color: "#94A3B8", marginBottom: 12 }}>{step.detail}</p>
                        {step.secrets && (
                          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            {step.secrets.map((s) => (
                              <div key={s.name} style={{
                                display: "flex", alignItems: "center", gap: 10,
                                padding: "8px 12px",
                                background: "#0A0A0F",
                                borderRadius: 6,
                                border: "1px solid #1E293B",
                              }}>
                                <span style={{
                                  fontSize: 10, padding: "2px 6px", borderRadius: 4,
                                  background: s.required ? "rgba(239,68,68,0.15)" : "rgba(100,116,139,0.15)",
                                  color: s.required ? "#F87171" : "#64748B",
                                }}>{s.required ? "必須" : "任意"}</span>
                                <code style={{ fontSize: 12, color: "#60A5FA", flex: 1 }}>{s.name}</code>
                                <span style={{ fontSize: 11, color: "#475569" }}>{s.desc}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {step.code && (
                          <pre style={{
                            background: "#070B14",
                            border: "1px solid #1E293B",
                            borderRadius: 8,
                            padding: "14px 16px",
                            fontSize: 12,
                            color: "#94A3B8",
                            overflowX: "auto",
                            margin: 0,
                            lineHeight: 1.6,
                          }}>{step.code}</pre>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {progress === 100 && (
              <div style={{
                marginTop: 24,
                padding: "16px 20px",
                background: "rgba(74,222,128,0.08)",
                border: "1px solid #166534",
                borderRadius: 10,
                textAlign: "center",
                color: "#4ADE80",
                fontSize: 14,
              }}>
                🎉 セットアップ完了！毎朝 6:00 JST に自動投稿が始まります
              </div>
            )}
          </>
        )}

        {/* ── 構成図タブ ── */}
        {tab === "arch" && (
          <div>
            <div style={{ marginBottom: 24, color: "#64748B", fontSize: 12, letterSpacing: "0.1em" }}>
              SYSTEM ARCHITECTURE
            </div>

            {/* Timeline */}
            <div style={{
              background: "#0F172A",
              border: "1px solid #1E293B",
              borderRadius: 12,
              padding: "24px",
              marginBottom: 20,
            }}>
              <div style={{ fontSize: 11, color: "#64748B", marginBottom: 20, letterSpacing: "0.1em" }}>
                📅 DAILY EXECUTION FLOW  ─  毎朝 6:00 JST (GitHub Actions)
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
                {arch.map((node, i) => (
                  <div key={node.id} style={{ display: "flex", gap: 16 }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                      <div style={{
                        width: 36, height: 36,
                        borderRadius: "50%",
                        background: `${node.color}22`,
                        border: `2px solid ${node.color}`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 16, flexShrink: 0,
                      }}>{node.icon}</div>
                      {i < arch.length - 1 && (
                        <div style={{ width: 2, flex: 1, background: "#1E293B", margin: "4px 0", minHeight: 32 }} />
                      )}
                    </div>
                    <div style={{ paddingBottom: i < arch.length - 1 ? 28 : 0, paddingTop: 6 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: node.color }}>{node.label}</div>
                      <div style={{ fontSize: 12, color: "#64748B", marginTop: 4 }}>{node.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Sources */}
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr",
              gap: 12,
            }}>
              {[
                { label: "arXiv", desc: "cs.AI / cs.LG 最新論文", color: "#F472B6" },
                { label: "RSS Feeds", desc: "Anthropic / OpenAI / HF / LangChain", color: "#60A5FA" },
                { label: "Hacker News", desc: "コミュニティ注目トピック", color: "#FB923C" },
                { label: "GitHub Trending", desc: "AIエージェント系リポジトリ", color: "#A78BFA" },
              ].map((s) => (
                <div key={s.label} style={{
                  padding: "14px 16px",
                  background: "#0F172A",
                  border: "1px solid #1E293B",
                  borderRadius: 8,
                  borderLeft: `3px solid ${s.color}`,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: s.color }}>{s.label}</div>
                  <div style={{ fontSize: 11, color: "#475569", marginTop: 4 }}>{s.desc}</div>
                </div>
              ))}
            </div>

            {/* Cost */}
            <div style={{
              marginTop: 20,
              padding: "16px 20px",
              background: "#0F172A",
              border: "1px solid #1E293B",
              borderRadius: 10,
            }}>
              <div style={{ fontSize: 11, color: "#64748B", marginBottom: 12, letterSpacing: "0.1em" }}>💰 月額コスト目安</div>
              <div style={{ display: "flex", gap: 24 }}>
                <div>
                  <div style={{ fontSize: 20, color: "#4ADE80", fontWeight: 700 }}>$3〜10</div>
                  <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>/ 月</div>
                </div>
                <div style={{ fontSize: 12, color: "#64748B", lineHeight: 1.8 }}>
                  Claude API: ~$0.10〜0.30/日<br />
                  GitHub Actions: 無料枠内<br />
                  インフラ: $0
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── ファイル一覧タブ ── */}
        {tab === "files" && (
          <div>
            <div style={{ marginBottom: 24, color: "#64748B", fontSize: 12, letterSpacing: "0.1em" }}>
              GENERATED FILES
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {files.map((f) => (
                <div key={f.path} style={{
                  display: "flex", alignItems: "center", gap: 16,
                  padding: "14px 18px",
                  background: "#0F172A",
                  border: "1px solid #1E293B",
                  borderRadius: 8,
                }}>
                  <code style={{ fontSize: 12, color: "#60A5FA", minWidth: 280 }}>{f.path}</code>
                  <span style={{ fontSize: 12, color: "#475569" }}>{f.desc}</span>
                </div>
              ))}
            </div>
            <div style={{
              marginTop: 20,
              padding: "14px 18px",
              background: "rgba(96,165,250,0.06)",
              border: "1px solid #1E3A5F",
              borderRadius: 8,
              fontSize: 12,
              color: "#64748B",
              lineHeight: 1.8,
            }}>
              📦 ダウンロードした全ファイルを GitHub リポジトリのルートに配置してください。<br />
              <code style={{ color: "#60A5FA" }}>data/</code> と <code style={{ color: "#60A5FA" }}>articles/</code> は自動生成されます。
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
