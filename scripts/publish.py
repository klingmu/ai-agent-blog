"""
publish.py — 生成記事を Zenn（GitHub Push）または WordPress へ投稿
generate.py が articles/ に Zenn フロントマター付きで直接出力するため、
このスクリプトは git push と通知のみを担当する。
"""

import os
import json
import re
import subprocess
import datetime
import requests
from pathlib import Path

_JST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(_JST).date().isoformat()
ARTICLES_DIR = Path("articles")


# ────────────────────────────────────────────────────────────
# Zenn 投稿（git push のみ）
# ────────────────────────────────────────────────────────────
def publish_to_zenn(article_path: Path, meta: dict) -> bool:
    gh_token = os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    try:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "AI Blog Bot",
            "GIT_AUTHOR_EMAIL": "bot@example.com",
            "GIT_COMMITTER_NAME": "AI Blog Bot",
            "GIT_COMMITTER_EMAIL": "bot@example.com",
        }
        if gh_token and repo:
            remote_url = f"https://x-access-token:{gh_token}@github.com/{repo}.git"
        else:
            result = subprocess.run(["git", "remote", "get-url", "origin"],
                                    capture_output=True, text=True)
            remote_url = result.stdout.strip()
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], check=True)
        subprocess.run(["git", "add", str(article_path)], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"📝 AIエージェント最前線 {TODAY} (score:{meta.get('quality_score',0)}/100)"],
            check=True, env=env,
        )
        subprocess.run(["git", "push", "origin", "main"], check=True)
        slug = article_path.stem
        print(f"✅ Zenn 投稿完了: https://zenn.dev/articles/{slug}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git push 失敗: {e}")
        return False


# ────────────────────────────────────────────────────────────
# WordPress 投稿
# ────────────────────────────────────────────────────────────
def publish_to_wordpress(article_path: Path, meta: dict) -> bool:
    wp_url = os.environ.get("WP_URL")
    wp_user = os.environ.get("WP_USER")
    wp_password = os.environ.get("WP_APP_PASSWORD")
    if not all([wp_url, wp_user, wp_password]):
        print("⚠️  WordPress 環境変数が未設定")
        return False

    with open(article_path, encoding="utf-8") as f:
        content = f.read()
    body = re.sub(r"^---\n.*?---\n\n", "", content, flags=re.DOTALL)
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1) if title_match else f"AIエージェント最前線 {TODAY}"

    try:
        r = requests.post(
            f"{wp_url}/wp-json/wp/v2/posts",
            auth=(wp_user, wp_password),
            json={"title": title, "content": body, "status": "publish"},
            timeout=30,
        )
        r.raise_for_status()
        print(f"✅ WordPress 投稿完了: {r.json().get('link', '')}")
        return True
    except requests.RequestException as e:
        print(f"❌ WordPress 投稿失敗: {e}")
        return False


# ────────────────────────────────────────────────────────────
# Slack 通知
# ────────────────────────────────────────────────────────────
def notify_slack(meta: dict, success: bool, url: str = ""):
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        return
    score = meta.get("quality_score", 0)
    highlight = meta.get("highlight_sentence", "")[:60]
    scores = meta.get("scores", {})
    score_detail = " / ".join(f"{k}:{v}" for k, v in scores.items())

    if success:
        text = (
            f"🤖 *AIエージェント最前線 {TODAY}* を投稿しました！\n"
            f"📊 品質スコア: *{score}/100* ({score_detail})\n"
            f"💬 ハイライト: _{highlight}_\n"
            f"🔗 {url}"
        )
    else:
        text = f"❌ {TODAY} の記事投稿に失敗しました。GitHubのログを確認してください。"

    try:
        requests.post(webhook, json={"text": text}, timeout=5)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────
# メタデータ読み込み
# ────────────────────────────────────────────────────────────
def load_meta(article_path: Path) -> dict:
    with open(article_path, encoding="utf-8") as f:
        content = f.read()
    meta_match = re.match(r"^---\n(.*?)---\n", content, re.DOTALL)
    if not meta_match:
        return {}
    meta = {}
    for line in meta_match.group(1).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            try:
                meta[k.strip()] = json.loads(v.strip())
            except Exception:
                meta[k.strip()] = v.strip()
    return meta


# ────────────────────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────────────────────
def main():
    matches = sorted(ARTICLES_DIR.glob(f"{TODAY}-*.md"))
    if not matches:
        raise FileNotFoundError(f"記事が見つかりません: articles/{TODAY}-*.md")
    article_path = matches[-1]
    print(f"📄 記事: {article_path}")

    meta = load_meta(article_path)
    approved = meta.get("approved", False)

    if not approved:
        print(f"⚠️  品質未承認（スコア: {meta.get('quality_score', 0)}/100）→ 投稿スキップ")
        notify_slack(meta, success=False)
        return

    target = os.environ.get("PUBLISH_TARGET", "zenn").lower()
    success = False
    url = ""

    if target == "zenn":
        slug = article_path.stem
        url = f"https://zenn.dev/articles/{slug}"
        success = publish_to_zenn(article_path, meta)
    elif target == "wordpress":
        success = publish_to_wordpress(article_path, meta)

    notify_slack(meta, success, url)


if __name__ == "__main__":
    main()
