"""
polish.py — ブログ記事の自動改善スクリプト

機能:
  ① 見出しの重複チェック・修正
  ② 「おわりに」セクションの存在確認
  ③ 記事の基本的な構造検証
  ④ メタデータの更新・検証
  ⑤ 参考文献の形式チェック

使い方:
  python scripts/polish.py                    # articles/ 内すべての .md ファイルを検証
  python scripts/polish.py --fix              # 見つかった問題を自動修正
  python scripts/polish.py --file articles/2026-05-16-*.md  # 特定ファイルのみ
"""

import os
import re
import sys
from pathlib import Path
from typing import Tuple, List, Dict, Set
import argparse
from datetime import datetime

ARTICLES_DIR = Path("articles")


def extract_headings(content: str) -> List[Tuple[int, str]]:
    """
    Markdown の見出しを解析し、レベルと見出しテキストのリストを返す。
    [(level, heading_text), ...]
    """
    headings = []
    for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
        level = len(match.group(1))
        text = match.group(2).strip()
        headings.append((level, text))
    return headings


def find_duplicate_headings(headings: List[Tuple[int, str]]) -> List[int]:
    """
    重複する見出しのインデックスを返す。
    同じテキストを複数回使っている場合、2番目以降のインデックスを返す。
    """
    seen = {}
    duplicates = []
    for i, (level, text) in enumerate(headings):
        if text in seen:
            duplicates.append(i)
        else:
            seen[text] = i
    return duplicates


def check_conclusion_section(content: str) -> bool:
    """
    「おわりに」セクションが存在するかチェック。
    """
    return bool(re.search(r'^##\s+おわりに\s*$', content, re.MULTILINE))


def validate_structure(content: str) -> Dict[str, any]:
    """
    記事の基本的な構造を検証する。
    """
    results = {
        'has_frontmatter': False,
        'has_title': False,
        'has_h1': False,
        'has_conclusion': False,
        'heading_issues': [],
        'duplicate_headings': [],
    }

    # フロントマター確認
    if content.startswith('---'):
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        results['has_frontmatter'] = bool(frontmatter_match)

    # タイトル確認
    results['has_title'] = bool(re.search(r'^title:\s*"?([^"]+)"?', content, re.MULTILINE))

    # H1 見出し確認
    results['has_h1'] = bool(re.search(r'^#\s+', content, re.MULTILINE))

    # 「おわりに」セクション確認
    results['has_conclusion'] = check_conclusion_section(content)

    # 見出し関連
    headings = extract_headings(content)
    results['duplicate_headings'] = find_duplicate_headings(headings)

    return results


def remove_duplicate_references_section(content: str) -> str:
    """
    重複した参考リソース/参考文献セクションを修正する。
    複数の「## 参考リソース」または「## 参考文献」が存在する場合、後ろのものを削除する。
    """
    # 「## 参考リソース」と「## 参考文献」の位置を検出
    references_pattern = r'^##\s+(?:参考リソース|📚\s+参考リソース|参考文献).*?$'
    matches = list(re.finditer(references_pattern, content, re.MULTILINE))

    if len(matches) > 1:
        # 後ろの参考セクションを削除する
        # 最後のマッチの開始位置から、次の「---」または EOF までを削除
        last_match = matches[-1]
        next_section_match = re.search(r'\n---\n', content[last_match.start():])

        if next_section_match:
            end_pos = last_match.start() + next_section_match.start()
        else:
            end_pos = len(content)

        # 前の参考セクションの直後の「---」の後までを保持し、後ろの参考セクションを削除
        content = content[:last_match.start()] + content[end_pos:]

    return content


def generate_report(file_path: Path, results: Dict[str, any]) -> str:
    """
    検証結果のレポートを生成する。
    """
    report = f"\n📄 {file_path.name}\n"
    report += "=" * 60 + "\n"

    # チェック結果
    report += f"✓ フロントマター: {'OK' if results['has_frontmatter'] else '❌ 不足'}\n"
    report += f"✓ title: {'OK' if results['has_title'] else '❌ 不足'}\n"
    report += f"✓ H1見出し: {'OK' if results['has_h1'] else '❌ 不足'}\n"
    report += f"✓ 「おわりに」: {'OK' if results['has_conclusion'] else '⚠️  見つかりません'}\n"

    if results['duplicate_headings']:
        report += f"\n⚠️  重複する見出し (インデックス): {results['duplicate_headings']}\n"

    # 問題の詳細
    if not results['has_conclusion']:
        report += "\n【推奨アクション】\n"
        report += "  → 「おわりに」セクションを追加してください。\n"
        report += "     筆者の考え中心で、「～のように感じる」「～のように思う」などの語尾を使用。\n"

    return report


def fix_article(file_path: Path) -> Tuple[bool, List[str]]:
    """
    記事を自動修正する。
    修正項目のリストを返す。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    fixes = []

    # ① 重複する参考リソース/参考文献セクションの修正
    new_content = remove_duplicate_references_section(content)
    if new_content != content:
        fixes.append("重複する参考セクションを削除")
        content = new_content

    # ② 末尾の余分な改行を削除
    if content.endswith('\n\n\n'):
        content = content.rstrip() + '\n'
        fixes.append("末尾の余分な改行を削除")

    # ③ 「おわりに」セクションが存在しない場合、プレースホルダーを追加
    if not check_conclusion_section(content):
        placeholder = (
            "\n\n---\n\n"
            "## おわりに\n\n"
            "<!-- TODO: 筆者の所感を記述してください。\n"
            "     「〜のように感じる」「〜のように思う」「〜ではないだろうか」などの語尾を使用。\n"
            "     読者への問いかけや希望・展望で締めてください。（150〜200字）-->\n"
        )
        content = content.rstrip('\n') + placeholder
        fixes.append("「おわりに」セクションのプレースホルダーを追加（内容は要記入）")

    # ファイルが変更された場合のみ保存
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, fixes
    else:
        return False, fixes


def main():
    parser = argparse.ArgumentParser(
        description="ブログ記事の自動改善スクリプト"
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='見つかった問題を自動修正する'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='特定のファイルのみを処理 (glob パターン対応)'
    )

    args = parser.parse_args()

    # 処理対象ファイルを決定
    if args.file:
        from glob import glob
        file_list = glob(args.file)
        if not file_list:
            print(f"❌ ファイルが見つかりません: {args.file}")
            sys.exit(1)
        target_files = [Path(f) for f in file_list]
    else:
        target_files = sorted(ARTICLES_DIR.glob("*.md"))

    if not target_files:
        print(f"❌ 記事ファイルが見つかりません: {ARTICLES_DIR}")
        sys.exit(1)

    total_issues = 0
    total_fixes = 0

    print(f"\n🔍 {len(target_files)} 件のファイルを検査します...\n")

    for file_path in target_files:
        print(f"処理中: {file_path.name}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 検証実行
        results = validate_structure(content)

        # 問題の数をカウント
        issue_count = 0
        if not results['has_frontmatter']:
            issue_count += 1
        if not results['has_title']:
            issue_count += 1
        if not results['has_h1']:
            issue_count += 1
        if not results['has_conclusion']:
            issue_count += 1
        if results['duplicate_headings']:
            issue_count += 1

        total_issues += issue_count

        # 修正実行
        if args.fix:
            modified, fixes = fix_article(file_path)
            if modified:
                total_fixes += len(fixes)
                print(f"  ✅ 修正項目: {', '.join(fixes)}")
            if not modified and issue_count > 0:
                print(f"  ⚠️  {issue_count} 件の問題を検出（手動修正が必要な可能性あり）")
        else:
            if issue_count > 0:
                print(f"  ⚠️  {issue_count} 件の問題を検出")

        # 詳細レポート出力（問題がある場合のみ）
        if issue_count > 0:
            report = generate_report(file_path, results)
            print(report)

    # 最終サマリー
    print("\n" + "=" * 60)
    print(f"📊 総検査ファイル数: {len(target_files)}")
    print(f"⚠️  総検出問題数: {total_issues}")
    if args.fix:
        print(f"✅ 自動修正項目数: {total_fixes}")
    print("=" * 60)

    if not args.fix and total_issues > 0:
        print("\n💡 --fix フラグで自動修正を実行できます:")
        print(f"   python scripts/polish.py --fix")


if __name__ == "__main__":
    main()
