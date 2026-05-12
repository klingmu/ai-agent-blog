"""
publish.py — 生成記事を Zenn（GitHub）または WordPress へ投稿
"""

import os
import json
import datetime
import subprocess
import re
import requests
from pathlib import Path

TODAY = datetime.date.today().isoformat()
ARTICLES_DIR = Path("drafts")
ZENN_DIR = Path("zenn/articles")   # Zenn連携リポジトリのarticlesディレクトリ


# ────────────────────────────────────────────────────────────
# Zenn 投稿（GitHub Push）
# ────────────────────────────────────────────────────────────
def publish_to_zenn(article_path: Path) -> bool:
    """
    Zenn はGitHubリポジトリと連携するため、
    対象リポジトリに Markdown をコピーして Push するだけで公開される
    """
    ZENN_DIR.mkdir(parents=True, exist_ok=True)

    with open(article_path, encoding="utf-8") as f:
        content = f.read()

    # フロントマター除去してZenn形式に変換
    body = re.sub(r"^---\n.*?---\n\n", "", content, flags=re.DOTALL)

    # Zenn用フロントマター
    slug = f"ai-agent-{TODAY.replace('-', '')}"
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1) if title_match else f"AIエージェント最前線 {TODAY}"

    zenn_frontmatter = f"""---
title: "{title}"
emoji: "🤖"
type: "tech"
topics: ["AIエージェント", "LLM", "Claude", "機械学習", "生成AI"]
published: true
---

"""
    zenn_content = zenn_frontmatter + body

    zenn_article_path = ZENN_DIR / f"{slug}.md"
    with open(zenn_article_path, "w", encoding="utf-8") as f:
        f.write(zenn_content)

    # Git commit & push
    try:
        subprocess.run(["git", "add", str(zenn_article_path)], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"📝 AIエージェント最前線 {TODAY}"],
            check=True,
            env={**os.environ, "GIT_AUTHOR_NAME": "AI Blog Bot", "GIT_AUTHOR_EMAIL": "bot@example.com",
                 "GIT_COMMITTER_NAME": "AI Blog Bot", "GIT_COMMITTER_EMAIL": "bot@example.com"},
        )
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"✅ Zenn に投稿完了: https://zenn.dev/articles/{slug}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push 失敗: {e}")
        return False


# ────────────────────────────────────────────────────────────
# WordPress 投稿（REST API）
# ────────────────────────────────────────────────────────────
def publish_to_wordpress(article_path: Path) -> bool:
    """WordPress REST API で投稿"""
    wp_url = os.environ.get("WP_URL")
    wp_user = os.environ.get("WP_USER")
    wp_password = os.environ.get("WP_APP_PASSWORD")

    if not all([wp_url, wp_user, wp_password]):
        print("⚠️  WordPress の環境変数が未設定です (WP_URL, WP_USER, WP_APP_PASSWORD)")
        return False

    with open(article_path, encoding="utf-8") as f:
        content = f.read()

    body = re.sub(r"^---\n.*?---\n\n", "", content, flags=re.DOTALL)
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1) if title_match else f"AIエージェント最前線 {TODAY}"

    # Markdown → HTML（簡易変換。本番では markdown2 等を使用）
    html_content = body

    try:
        r = requests.post(
            f"{wp_url}/wp-json/wp/v2/posts",
            auth=(wp_user, wp_password),
            json={
                "title": title,
                "content": html_content,
                "status": "publish",
                "categories": [],
                "tags": [],
            },
            timeout=30,
        )
        r.raise_for_status()
        post_url = r.json().get("link", "")
        print(f"✅ WordPress に投稿完了: {post_url}")
        return True
    except requests.RequestException as e:
        print(f"❌ WordPress 投稿失敗: {e}")
        return False


# ────────────────────────────────────────────────────────────
# Slack 通知
# ────────────────────────────────────────────────────────────
def notify_slack(message: str):
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=5)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────────────────
def main():
    article_path = ARTICLES_DIR / f"{TODAY}.md"
    if not article_path.exists():
        raise FileNotFoundError(f"記事が見つかりません: {article_path}")

    # メタデータ確認
    with open(article_path, encoding="utf-8") as f:
        content = f.read()

    approved_match = re.search(r"^approved: (.+)$", content, re.MULTILINE)
    if approved_match and approved_match.group(1).strip() == "false":
        print("⚠️  品質チェック未承認のため投稿をスキップします")
        notify_slack(f"⚠️ {TODAY} の記事は品質チェック未承認のため投稿をスキップしました")
        return

    # 投稿先を環境変数で切り替え
    target = os.environ.get("PUBLISH_TARGET", "zenn").lower()

    success = False
    if target == "zenn":
        success = publish_to_zenn(article_path)
    elif target == "wordpress":
        success = publish_to_wordpress(article_path)
    else:
        print(f"❌ 不明な投稿先: {target} (zenn / wordpress のいずれかを指定)")

    if success:
        notify_slack(f"🤖 *AIエージェント最前線 {TODAY}* を投稿しました！")
    else:
        notify_slack(f"❌ {TODAY} の記事投稿に失敗しました。ログを確認してください")


if __name__ == "__main__":
    main()
