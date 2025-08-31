#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

BADGE_START = "<!-- DAILY_STATUS_START -->"
BADGE_END = "<!-- DAILY_STATUS_END -->"

SUCCESS_BADGE = "![Daily Test](https://img.shields.io/badge/daily%20test-passed-brightgreen)"
FAIL_BADGE = "![Daily Test](https://img.shields.io/badge/daily%20test-failed-red)"

def main():
    if len(sys.argv) < 2:
        print("Usage: update_readme_status.py <success|failure>")
        sys.exit(1)

    status = sys.argv[1].strip().lower()
    badge = SUCCESS_BADGE if status == "success" else FAIL_BADGE

    readme = Path("README.md")
    if not readme.exists():
        print("README.md not found")
        sys.exit(0)

    content = readme.read_text(encoding="utf-8")

    if BADGE_START in content and BADGE_END in content:
        start = content.index(BADGE_START) + len(BADGE_START)
        end = content.index(BADGE_END)
        new_content = content[:start] + "\n" + badge + "\n" + content[end:]
    else:
        # 在README顶部插入状态区块
        new_content = f"{BADGE_START}\n{badge}\n{BADGE_END}\n\n" + content

    readme.write_text(new_content, encoding="utf-8")
    print("README updated with status:", status)

if __name__ == "__main__":
    main()


