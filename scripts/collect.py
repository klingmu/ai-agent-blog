"""
collect.py — 情報収集スクリプト（エージェント版）
収集ソース: arXiv, RSS, Hacker News, GitHub, YouTube, YouTube Shorts
"""

import os
import json
import datetime
import feedparser
import requests
import arxiv
from collections import Counter
from pathlib import Path

_JST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(_JST).date().isoformat()
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)

# ────────────────────────────────────────────────────────────
# 1. arXiv 論文
# ────────────────────────────────────────────────────────────
def fetch_arxiv(max_results: int = 10) -> list[dict]:
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
            "summary": paper.summary[:600],
            "url": paper.entry_id,
            "authors": [a.name for a in paper.authors[:3]],
            "published": paper.published.isoformat(),
            "categories": paper.categories,
        })
    print(f"[arXiv] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 2. RSS フィード
# ────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "Anthropic Blog":    "https://www.anthropic.com/rss.xml",
    "OpenAI Blog":       "https://openai.com/blog/rss.xml",
    "Google DeepMind":   "https://deepmind.google/blog/rss.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "LangChain Blog":    "https://blog.langchain.dev/rss/",
    "Simon Willison":    "https://simonwillison.net/atom/everything/",
    "The Batch":         "https://www.deeplearning.ai/the-batch/feed/",
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
                    "summary": entry.get("summary", "")[:600],
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[RSS] {name} 取得失敗: {e}")
    print(f"[RSS] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 3. Hacker News
# ────────────────────────────────────────────────────────────
HN_KEYWORDS = ["agent", "llm", "gpt", "claude", "gemini", "rag", "mcp",
               "openai", "anthropic", "agentic", "copilot", "cursor"]

def fetch_hackernews(max_results: int = 10) -> list[dict]:
    try:
        r = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        )
        story_ids = r.json()[:150]
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
                    "summary": f"HNスコア: {s.get('score', 0)}, コメント数: {s.get('descendants', 0)}",
                    "url": s.get("url") or f"https://news.ycombinator.com/item?id={sid}",
                    "published": datetime.datetime.fromtimestamp(s.get("time", 0)).isoformat(),
                    "hn_score": s.get("score", 0),
                })
        except Exception:
            pass
    print(f"[HN] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 4. GitHub
# ────────────────────────────────────────────────────────────
def fetch_github_trending(max_results: int = 8) -> list[dict]:
    headers = {}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {token}"

    queries = [
        "agent llm topic:llm-agent pushed:>2024-06-01",
        "agentic AI framework topic:ai-agent pushed:>2024-06-01",
    ]
    results = []
    seen: set[str] = set()
    for q in queries:
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc",
                        "per_page": max_results // len(queries)},
                headers=headers, timeout=10,
            )
            for repo in r.json().get("items", []):
                if repo["full_name"] not in seen:
                    seen.add(repo["full_name"])
                    results.append({
                        "source": "github",
                        "title": repo["full_name"],
                        "summary": repo.get("description", "")[:400],
                        "url": repo["html_url"],
                        "published": repo.get("updated_at", ""),
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language", ""),
                    })
        except Exception as e:
            print(f"[GitHub] クエリ失敗: {e}")
    print(f"[GitHub] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# 5. YouTube Data API v3
# ────────────────────────────────────────────────────────────
YOUTUBE_SEARCH_KEYWORDS = [
    "AI agent tutorial 2025",
    "LLM agent agentic AI",
    "Claude OpenAI agent demo",
    "AIエージェント 解説",
]

YOUTUBE_SHORTS_CHANNELS = {
    # チャンネルIDは実際の値に置き換えてください
    "Two Minute Papers": "UCbfYPyITQ-7l4upoX8nvctg",
    "AI Explained":      "UCZMT9TGE3gA7dXbJZBY5sqA",
}

def _yt_get(endpoint: str, params: dict) -> dict:
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    params["key"] = api_key
    r = requests.get(
        f"https://www.googleapis.com/youtube/v3/{endpoint}",
        params=params, timeout=10,
    )
    r.raise_for_status()
    return r.json()

def fetch_youtube(max_results: int = 8) -> list[dict]:
    if not os.environ.get("YOUTUBE_API_KEY"):
        print("[YouTube] YOUTUBE_API_KEY 未設定 → スキップ")
        return []

    results = []
    seen: set[str] = set()
    published_after = (
        datetime.date.today() - datetime.timedelta(days=7)
    ).isoformat() + "T00:00:00Z"

    for keyword in YOUTUBE_SEARCH_KEYWORDS[:3]:
        try:
            data = _yt_get("search", {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "order": "relevance",
                "publishedAfter": published_after,
                "maxResults": 3,
            })
            for item in data.get("items", []):
                vid = item["id"]["videoId"]
                if vid in seen:
                    continue
                seen.add(vid)
                sn = item["snippet"]
                results.append({
                    "source": "youtube",
                    "title": sn.get("title", ""),
                    "summary": sn.get("description", "")[:400],
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "published": sn.get("publishedAt", ""),
                    "channel": sn.get("channelTitle", ""),
                })
        except Exception as e:
            print(f"[YouTube] '{keyword}' 失敗: {e}")

    print(f"[YouTube] {len(results)} 件取得")
    return results

def fetch_youtube_shorts(max_results: int = 4) -> list[dict]:
    """著名AIチャンネルのShorts（短尺解説動画）を取得"""
    if not os.environ.get("YOUTUBE_API_KEY"):
        return []

    results = []
    for channel_name, channel_id in YOUTUBE_SHORTS_CHANNELS.items():
        try:
            data = _yt_get("search", {
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "videoDuration": "short",
                "order": "date",
                "maxResults": 2,
            })
            for item in data.get("items", []):
                vid = item["id"]["videoId"]
                sn = item["snippet"]
                results.append({
                    "source": "youtube_shorts",
                    "title": sn.get("title", ""),
                    "summary": sn.get("description", "")[:300],
                    "url": f"https://www.youtube.com/shorts/{vid}",
                    "published": sn.get("publishedAt", ""),
                    "channel": channel_name,
                })
        except Exception as e:
            print(f"[Shorts] {channel_name} 失敗: {e}")

    print(f"[YouTube Shorts] {len(results)} 件取得")
    return results


# ────────────────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────────────────
def main():
    all_items: list[dict] = []
    all_items += fetch_arxiv()
    all_items += fetch_rss()
    all_items += fetch_hackernews()
    all_items += fetch_github_trending()
    all_items += fetch_youtube()
    all_items += fetch_youtube_shorts()

    out_path = OUTPUT_DIR / f"raw_{TODAY}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"date": TODAY, "items": all_items}, f, ensure_ascii=False, indent=2)

    src_counts = Counter(item["source"].split(":")[0] for item in all_items)
    print(f"\n✅ 収集完了: {len(all_items)} 件 → {out_path}")
    for src, cnt in sorted(src_counts.items()):
        print(f"   {src}: {cnt}件")


if __name__ == "__main__":
    main()
