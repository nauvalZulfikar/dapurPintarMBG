"""Add dark: variants to text-gray-* classes that don't have them yet.

Rules:
  text-gray-500 -> + dark:text-gray-400   (muted → muted-light in dark)
  text-gray-400 -> + dark:text-gray-500
  text-gray-600 -> + dark:text-gray-300
  text-gray-700 -> + dark:text-gray-200
  text-gray-800 -> + dark:text-gray-100
  text-gray-900 -> + dark:text-white
  text-black    -> + dark:text-white

Skip pages that are intentionally dark (Countdown.jsx, Login full-screen overlays).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent / "src"

# Invert target: if class X already has a "dark:text-..." within the same
# className string, don't touch it.
RULES = {
    "text-gray-500": "dark:text-gray-400",
    "text-gray-400": "dark:text-gray-500",
    "text-gray-600": "dark:text-gray-300",
    "text-gray-700": "dark:text-gray-200",
    "text-gray-800": "dark:text-gray-100",
    "text-gray-900": "dark:text-white",
    "text-black":    "dark:text-white",
}

# Files to skip (intentionally dark, or stand-alone screens)
SKIP_FILES = {"Countdown.jsx", "Login.jsx"}

# Match className="..." OR className={`...`}
CLASS_RE = re.compile(r'className=(["\'`])([^"\'`]*?)\1')


def fix_class_string(s: str) -> tuple[str, int]:
    """Given the inner content of a className, add dark: variants.
    Returns (new_s, num_changes).
    """
    if "dark:text-" in s:
        # has at least one dark text rule already — be conservative:
        # only add for the specific light classes that don't share this string
        pass
    parts = s.split()
    changed = 0
    has_dark_text = any(p.startswith("dark:text-") for p in parts)
    for light, dark in RULES.items():
        if light in parts and not has_dark_text:
            idx = parts.index(light)
            parts.insert(idx + 1, dark)
            changed += 1
            has_dark_text = True  # added one; avoid duplicate additions in same string
    return " ".join(parts), changed


def process(path: Path) -> int:
    if path.name in SKIP_FILES:
        return 0
    src = path.read_text(encoding="utf-8")
    new_parts = []
    last = 0
    total_changes = 0
    for m in CLASS_RE.finditer(src):
        new_parts.append(src[last:m.start(2)])
        new_inner, n = fix_class_string(m.group(2))
        new_parts.append(new_inner)
        total_changes += n
        last = m.end(2)
    new_parts.append(src[last:])
    new_src = "".join(new_parts)
    if total_changes:
        path.write_text(new_src, encoding="utf-8")
    return total_changes


def main():
    total = 0
    files_touched = 0
    for p in ROOT.rglob("*.jsx"):
        n = process(p)
        if n:
            files_touched += 1
            total += n
            print(f"  {p.relative_to(ROOT)}: {n} edits")
    print(f"\ntotal: {total} edits across {files_touched} files")


if __name__ == "__main__":
    sys.exit(main())
