"""
add_tags_to_daily_files.py
Adds Obsidian ticker tags to existing daily signal .md files.
Adds:
  1. YAML frontmatter with 'tags:' and 'created:'
  2. Inline #TICKER tag after each ### TICKER heading
"""
import re
import os

VAULT_PATH = r"C:\Data\Obsidian_root\Obsidian_trading\Ashley_trading"
FILES = [
    "2026-09-14-Daily-Signals.md",
    "2026-09-15-Daily-Signals.md",
    "2026-09-18-Daily-Signals.md",
    "2026-09-19-Daily-Signals.md",
    "2026-09-20-Daily-Signals.md",
    "2026-09-21-Daily-Signals.md",
    "2026-09-22-Daily-Signals.md",
    "2026-09-23-Daily-Signals.md",
    "2026-09-24-Daily-Signals.md",
]

def extract_date(fname):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
    return m.group(1) if m else None

def extract_tickers(content):
    tickers = re.findall(r"^###\s+([A-Z][A-Z0-9]{0,6})", content, re.MULTILINE)
    seen = set()
    unique = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique

def update_file(filepath, fname):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if content.startswith("---"):
        print(f"  SKIP (already has frontmatter): {fname}")
        return False

    tickers = extract_tickers(content)
    created = extract_date(fname)

    tags_str = ", ".join(tickers)
    frontmatter = f"---\ntags: [{tags_str}]\ncreated: {created}\n---\n\n"

    # Add inline tag: "### TSLA" -> "### TSLA #TSLA"
    new_content = re.sub(
        r"^(###\s+)([A-Z][A-Z0-9]{0,6})$",
        r"\1\2 #\2",
        content,
        flags=re.MULTILINE
    )

    new_content = frontmatter + new_content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"  UPDATED: {fname}  |  tickers: {tickers}")
    return True

def main():
    updated = 0
    for fname in FILES:
        filepath = os.path.join(VAULT_PATH, fname)
        if os.path.exists(filepath):
            ok = update_file(filepath, fname)
            if ok:
                updated += 1
        else:
            print(f"  MISSING: {fname}")
    print(f"\nDone. Updated {updated} files.")

if __name__ == "__main__":
    main()
