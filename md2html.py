#!/usr/bin/env python3
import os
import re
import unicodedata
import markdown
from datetime import datetime

# Optional: if python-dateutil is available, we'll use it for more robust parsing
try:
    from dateutil import parser as dateutil_parser  # type: ignore
    DATEUTIL_AVAILABLE = True
except Exception:
    DATEUTIL_AVAILABLE = False

INPUT_DIR = "_posts"         # existing folder with .md files
OUTPUT_DIR = "html_posts"    # new folder for generated .html files
SAFE_TITLE_MAX = 50

os.makedirs(OUTPUT_DIR, exist_ok=True)

def slugify_for_filename(value):
    """Return a safe filename fragment from the title."""
    value = unicodedata.normalize("NFKD", value)
    value = re.sub(r"[^\w\s-]", "", value)        # remove punctuation except - _
    value = re.sub(r"[-\s]+", "-", value)         # collapse whitespace/hyphens to single hyphen
    value = value.strip("-").lower()
    return value[:SAFE_TITLE_MAX].rstrip("-") or "untitled-post"

def parse_date_to_iso(raw_date):
    """
    Parse a raw date string (e.g. 'Oct 10, 2012 06:02 AM PDT') and return 'YYYY-MM-DD'.
    Falls back to today's date on failure.
    """
    if not raw_date:
        return datetime.now().strftime("%Y-%m-%d")

    raw = raw_date.strip().strip('"').strip("'")

    # If dateutil is available, prefer it (handles many variants and timezones)
    if DATEUTIL_AVAILABLE:
        try:
            dt = dateutil_parser.parse(raw)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass  # prevent IndentationError

    # Try a few ISO-like direct parses
    iso_try_formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
    ]
    for fmt in iso_try_formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Remove common timezone suffixes like "PDT", "UTC", "GMT+0200", "(PDT)", etc.
    cleaned = re.sub(r"\s+\(?GMT[+-]?\d{1,4}\)?$", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\(?UTC\)?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\(?[A-Za-z]{1,5}\)?$", "", cleaned).strip()

    # Common human readable formats to try
    try_formats = [
        "%b %d, %Y %I:%M %p",  # "Oct 10, 2012 06:02 AM"
        "%b %d, %Y %H:%M",     # "Oct 10, 2012 06:02"
        "%b %d, %Y",           # "Oct 10, 2012"
        "%B %d, %Y %I:%M %p",  # "October 10, 2012 06:02 AM"
        "%B %d, %Y",           # "October 10, 2012"
    ]
    for fmt in try_formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Try to extract a month/day/year substring if present
    m = re.search(r"([A-Za-z]{3,}\s+\d{1,2},\s+\d{4})", raw)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%b %d, %Y")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Fallback: warn and use today's date
    print(f"Warning: Unrecognized date format: {raw!r}. Using today's date as fallback.")
    return datetime.now().strftime("%Y-%m-%d")

def extract_frontmatter(content):
    """
    Returns (iso_date_str, title, tags)
    """
    date_match = re.search(r'^date:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
    title_match = re.search(r'^title:\s*["\'](.+?)["\']', content, re.MULTILINE)
    tags_match = re.search(r'^tags:\s*(\[[^\]]*\])', content, re.MULTILINE)

    raw_date = date_match.group(1).strip() if date_match and date_match.group(1) else None
    iso_date = parse_date_to_iso(raw_date)

    title = title_match.group(1).strip() if title_match else "Untitled Post"
    tags = tags_match.group(1).strip() if tags_match else "[]"

    return iso_date, title, tags

def unique_output_path(base_dir, base_name):
    """
    If base_name exists in base_dir, append -1, -2, ... to avoid collisions.
    base_name should include extension (e.g. "2012-10-10-some-title.html")
    """
    candidate = os.path.join(base_dir, base_name)
    if not os.path.exists(candidate):
        return candidate

    name, ext = os.path.splitext(base_name)
    counter = 1
    while True:
        new_name = f"{name}-{counter}{ext}"
        candidate = os.path.join(base_dir, new_name)
        if not os.path.exists(candidate):
            return candidate
        counter += 1

def convert_files():
    for filename in os.listdir(INPUT_DIR):
        if not filename.lower().endswith(".md"):
            continue

        in_path = os.path.join(INPUT_DIR, filename)
        try:
            with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"Failed to read {filename}: {e}")
            continue

        iso_date, title, tags = extract_frontmatter(content)

        # Remove YAML frontmatter (if present) for conversion
        content_body = re.sub(r'^---[\s\S]*?---\s*', '', content, flags=re.MULTILINE)

        # Convert Markdown to HTML (with fallback)
        try:
            html_body = markdown.markdown(content_body, extensions=['extra', 'codehilite', 'tables'])
        except Exception as e:
            print(f"Markdown conversion failed for {filename}: {e}. Writing raw body instead.")
            html_body = "<pre>" + content_body + "</pre>"

        # Create Jekyll-compatible wrapper (HTML file with frontmatter)
        output_content = f"""---
title: "{title}"
date: "{iso_date}"
tags: {tags}
layout: post
---

{html_body}
"""

        safe_title = slugify_for_filename(title)
        output_filename_base = f"{iso_date}-{safe_title}.html"
        output_path = unique_output_path(OUTPUT_DIR, output_filename_base)

        try:
            with open(output_path, "w", encoding="utf-8") as out:
                out.write(output_content)
            print(f"Converted: {filename} → {os.path.basename(output_path)}")
        except Exception as e:
            print(f"Failed to write {output_path}: {e}")

if __name__ == "__main__":
    convert_files()
