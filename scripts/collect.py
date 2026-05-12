"""
collect.py — AI Agent ノウハウ収集スクリプト
収集ソース: arXiv, RSS (Anthropic/OpenAI/HF), Hacker News, GitHub Trending
"""

import os
import json
import datetime
import feedparser
import requests
import arxiv
from pathlib import Path

TODAY = datetime.date.today().isoformat()
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

# ────────────────────────────────────────────────────────────
# 1. arXiv 論文収集
# ────────────────────────────────────────────────────────────
def fetch_arxiv(max_results: int = 10) -> list[dict]:
    """cs.AI / cs.LG の最新論文をエージェント関連キーワードで取得"""
    query = (
        '(cat:cs.AI OR cat:cs.LG) AND '
        '(ti:"agent" OR ti:"agentic" OR ti:"multi-agent" OR '
        ' ti:"tool use" OR ti:"LLM" OR ti:"RAG" OR ti:"autonomous")'
    )
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    results = []
    for paper in client.results(search):
        results.append({
            "source": "arxiv",
            "title": paper.title,
            "summary": paper.summary[:500],
            "url": paper.entry_id,
            "authors": [a.name for a in paper.authors[:3]],
            "published": paper.published.isoformat(),
            "categories": paper.categories,
        })
    print(f"[arXiv] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 2. RSS フィード収集
# ────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "Anthropic Blog":       "https://www.anthropic.com/rss.xml",
    "OpenAI Blog":          "https://openai.com/blog/rss.xml",
    "Google DeepMind":      "https://deepmind.google/blog/rss.xml",
    "Hugging Face Blog":    "https://huggingface.co/blog/feed.xml",
    "LangChain Blog":       "https://blog.langchain.dev/rss/",
    "Simon Willison":       "https://simonwillison.net/atom/everything/",
}

def fetch_rss(max_per_feed: int = 5) -> list[dict]:
    results = []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                results.append({
                    "source": f"rss:{name}",
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:500],
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[RSS] {name} 取得失敗: {e}")
    print(f"[RSS] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 3. Hacker News — AIエージェント関連スレッド
# ────────────────────────────────────────────────────────────
HN_KEYWORDS = ["agent", "llm", "gpt", "claude", "gemini", "rag", "mcp", "openai", "anthropic"]

def fetch_hackernews(max_results: int = 10) -> list[dict]:
    try:
        r = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        )
        story_ids = r.json()[:100]
    except Exception as e:
        print(f"[HN] 取得失敗: {e}")
        return []

    results = []
    for sid in story_ids:
        if len(results) >= max_results:
            break
        try:
            s = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5
            ).json()
            title = s.get("title", "").lower()
            if any(kw in title for kw in HN_KEYWORDS):
                results.append({
                    "source": "hackernews",
                    "title": s.get("title", ""),
                    "summary": f"Score: {s.get('score', 0)}, Comments: {s.get('descendants', 0)}",
                    "url": s.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "published": datetime.datetime.fromtimestamp(
                        s.get("time", 0)
                    ).isoformat(),
                })
        except Exception:
            pass

    print(f"[HN] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 4. GitHub Trending（スクレイピング）
# ────────────────────────────────────────────────────────────
def fetch_github_trending(max_results: int = 5) -> list[dict]:
    """GitHub Trending APIを使ってAI/LLMリポジトリを収集"""
    try:
        # GitHub Search APIでAIエージェント関連の人気リポジトリを検索
        headers = {}
        if token := os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"token {token}"

        r = requests.get(
            "https://api.github.com/search/repositories",
            params={
                "q": "agent llm OR agent AI topic:llm pushed:>2024-01-01",
                "sort": "stars",
                "order": "desc",
                "per_page": max_results,
            },
            headers=headers,
            timeout=10,
        )
        items = r.json().get("items", [])
        results = []
        for repo in items:
            results.append({
                "source": "github",
                "title": repo["full_name"],
                "summary": repo.get("description", "")[:300],
                "url": repo["html_url"],
                "published": repo.get("updated_at", ""),
                "stars": repo.get("stargazers_count", 0),
            })
        print(f"[GitHub] {len(results)} 件取得")
        return results
    except Exception as e:
        print(f"[GitHub] 取得失敗: {e}")
        return []


# ────────────────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────────────────
def main():
    all_items = []
    all_items += fetch_arxiv()
    all_items += fetch_rss()
    all_items += fetch_hackernews()
    all_items += fetch_github_trending()

    out_path = OUTPUT_DIR / f"raw_{TODAY}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"date": TODAY, "items": all_items}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 収集完了: {len(all_items)} 件 → {out_path}")


if __name__ == "__main__":
    main()
