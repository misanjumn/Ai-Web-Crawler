#!/usr/bin/env python3
# © Copyright IBM Corporation 2026
# Author: Misbah Anjum N <misanjumn@ibm.com>
# All rights reserved.

"""
crawler.py — BFS Web Crawler + Text Exporter
Powered by Bob CLI in Browser Dev mode.

Architecture:
  Python drives a BFS queue over the TOC tree.
  Bob handles ONE page at a time: navigate → snapshot → extract content + direct children.
  Python assembles the full nested tree and writes the final JSON files.
  Optionally converts all output JSON to readable .txt files for transcription/training.

Usage:
    python3 crawler.py --url <URL>              # crawl only → Database/
    python3 crawler.py --url <URL> --text       # crawl + export TXT → Database/ + Text/
    python3 crawler.py --url <URL1> --url <URL2> --text
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path


# Constants
PROMPT_FILE       = Path(__file__).parent / "prompts" / "extract_page.txt"
DATABASE_DIR      = Path(__file__).parent / "Database"
CACHE_DIR         = Path(__file__).parent / ".cache" / "crawler"
MCP_SETTINGS_FILE = Path.home() / ".bob" / "settings" / "mcp_settings.json"
MCP_JSON_FILE     = Path.home() / ".bob" / "settings" / "mcp.json"


# Bob CLI Detection
def find_bob() -> str | None:
    bob_in_path = shutil.which("bob")
    if bob_in_path:
        return bob_in_path
    for path in [
        "/usr/local/bin/bob",
        "/opt/homebrew/bin/bob",
        "/usr/bin/bob",
        os.path.expanduser("~/.local/bin/bob"),
    ]:
        if os.path.isfile(path):
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
                continue
    return None


# MCP Config Patcher
def patch_mcp_config() -> dict | None:
    """
    Inject chrome-devtools into mcp_settings.json — the file Bob subprocess reads.
    Returns original content for restore.
    """
    if not MCP_SETTINGS_FILE.exists():
        print(f"[WARN] mcp_settings.json not found — skipping patch")
        return None

    settings = json.loads(MCP_SETTINGS_FILE.read_text(encoding="utf-8"))
    original = json.loads(json.dumps(settings))

    servers = settings.setdefault("mcpServers", {})
    if "chrome-devtools" in servers:
        print("  chrome-devtools already in mcp_settings.json")
        return original

    # Copy definition from mcp.json if available
    chrome_def = None
    if MCP_JSON_FILE.exists():
        mcp_json = json.loads(MCP_JSON_FILE.read_text(encoding="utf-8"))
        chrome_def = mcp_json.get("mcpServers", {}).get("chrome-devtools")

    if not chrome_def:
        chrome_def = {"command": "npx", "args": ["-y", "chrome-devtools-mcp@latest"]}

    servers["chrome-devtools"] = chrome_def
    MCP_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print("  Patched mcp_settings.json — chrome-devtools injected")
    return original


def restore_mcp_config(original: dict) -> None:
    MCP_SETTINGS_FILE.write_text(json.dumps(original, indent=2), encoding="utf-8")
    print("  mcp_settings.json restored")


# Prompt Loader
def load_prompt(url: str, output_file: str) -> str:
    template = PROMPT_FILE.read_text(encoding="utf-8")
    return template.replace("{URL}", url).replace("{OUTPUT_FILE}", output_file)


# Single Page Extractor
def extract_page(bob_path: str, url: str, output_file: str) -> dict | None:
    """
    Invoke Bob to extract content from a single page.
    Bob writes a JSON file to output_file.
    Returns the parsed JSON dict, or None on failure.
    """
    prompt = load_prompt(url, output_file)

    # Remove any stale output file from a previous run
    if os.path.exists(output_file):
        os.remove(output_file)

    process: subprocess.Popen | None = None
    try:
        process = subprocess.Popen(
            [bob_path, "--chat-mode", "browser-dev", "--approval-mode", "yolo", prompt],
            cwd=str(Path(__file__).parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        if process.stdout:
            for line in process.stdout:
                print("  │ " + line, end="", flush=True)

        process.wait(timeout=300)  # 5 min per page

        if process.stderr:
            stderr_out = process.stderr.read().strip()
            if stderr_out:
                filtered = "\n".join(
                    l for l in stderr_out.splitlines()
                    if "DeprecationWarning" not in l and "punycode" not in l
                )
                if filtered.strip():
                    print(f"  │ [STDERR] {filtered[:300]}")

    except subprocess.TimeoutExpired:
        print(f"  │ [TIMEOUT] Page extraction timed out: {url}")
        if process:
            process.kill()
        return None
    except Exception as e:
        print(f"  │ [ERROR] {e}")
        return None

    # Read the output file Bob wrote
    if not os.path.exists(output_file):
        print(f"  │ [ERROR] Bob did not write output file: {output_file}")
        return None

    try:
        content = Path(output_file).read_text(encoding="utf-8").strip()
        # Strip markdown code fences if Bob wrapped it
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  │ [ERROR] Invalid JSON in output file: {e}")
        return None


# kebab-case helper
def to_kebab(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


# BFS Crawler
def crawl_section(bob_path: str, root_url: str) -> tuple[dict, dict, str]:
    """
    BFS crawl starting from root_url.
    Returns (visited, child_order, root_url).
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # BFS state
    queue = deque([root_url])
    visited = {}        # url → extracted page dict (with children as URL list)
    parent_map = {}     # url → parent url
    child_order = {}    # url → ordered list of child URLs

    total_pages = 0
    failed_pages = []

    print(f"\n  Starting BFS from: {root_url}")

    while queue:
        url = queue.popleft()

        if url in visited:
            continue

        depth = 0
        u = url
        while u in parent_map:
            u = parent_map[u]
            depth += 1

        total_pages += 1
        print(f"\n  [{total_pages}] depth={depth} → {url}")

        # Temp output file for this page
        safe_name = to_kebab(url.split("?")[-1].replace("topic=", "").replace("/", "-"))[:80]
        output_file = str(CACHE_DIR / f"{safe_name}.json")

        page_data = extract_page(bob_path, url, output_file)

        if page_data is None:
            print(f"  │ [SKIP] Extraction failed — marking as error")
            visited[url] = {
                "title": "EXTRACTION_ERROR",
                "url": url,
                "breadcrumb": [],
                "last_updated": None,
                "description": "PAGE_ERROR",
                "has_video": False,
                "video_url": None,
                "video_title": None,
                "notes": None,
                "tables": [],
                "sections": [],
                "_child_urls": [],
            }
            failed_pages.append(url)
            continue

        # Extract child URL stubs — skip any URL already seen (cycle detection)
        child_stubs = page_data.pop("children", [])
        queued = set(queue)  # O(1) membership check
        child_urls = []
        for stub in child_stubs:
            child_url = stub.get("url", "").strip()
            if not child_url:
                continue
            if child_url == url:
                print(f"  │ [CYCLE] Skipping self-referencing child: {child_url}")
                continue
            if child_url in visited or child_url in queued:
                continue
            child_urls.append(child_url)
            parent_map[child_url] = url
            queue.append(child_url)
            queued.add(child_url)

        page_data["_child_urls"] = child_urls
        visited[url] = page_data
        child_order[url] = child_urls

        print(f"  │ ✓ Extracted: {page_data.get('title', '?')} ({len(child_urls)} children)")

    print(f"\n  BFS complete. Pages visited: {len(visited)}  Failed: {len(failed_pages)}")
    if failed_pages:
        print(f"  Failed URLs:")
        for u in failed_pages:
            print(f"    ✗ {u}")

    return visited, child_order, root_url  # type: ignore[return-value]


# Tree Assembler
def assemble_node(url: str, visited: dict, child_order: dict, seen: set | None = None) -> dict:
    """
    Recursively assemble a node and all its descendants into a nested dict.
    `seen` guards against cycles in the URL graph.
    """
    if seen is None:
        seen = set()
    if url in seen:
        # Cycle detected — return a stub to break the loop
        node = dict(visited.get(url, {}))
        node.pop("_child_urls", None)
        node["children"] = []
        node["_cycle"] = True
        return node
    seen = seen | {url}  # immutable copy so siblings don't block each other

    node = dict(visited.get(url, {}))
    child_urls = node.pop("_child_urls", [])

    children = []
    for child_url in child_urls:
        if child_url in visited:
            children.append(assemble_node(child_url, visited, child_order, seen))

    node["children"] = children
    return node


# File Writer
def write_section_files(section_node: dict, section_dir: Path) -> None:
    """
    Write _index.json and one .json per level-1 child.
    """
    section_dir.mkdir(parents=True, exist_ok=True)

    section_id  = to_kebab(section_node.get("title", "section"))
    level1_children = section_node.get("children", [])

    # Build _index.json
    index = {
        "id": section_id,
        "title": section_node.get("title"),
        "url": section_node.get("url"),
        "product": "IBM Maximo Manage",
        "version": "Continuous Delivery",
        "last_updated": section_node.get("last_updated"),
        "description": section_node.get("description"),
        "breadcrumb": section_node.get("breadcrumb", []),
        "children": [
            {
                "id": to_kebab(c.get("title", "")),
                "title": c.get("title"),
                "url": c.get("url"),
                "file": f"{to_kebab(c.get('title', ''))}.json",
            }
            for c in level1_children
        ],
    }

    index_path = section_dir / "_index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Wrote: {index_path.relative_to(Path(__file__).parent)}")

    # Write one file per level-1 child (with full nested children inside)
    for child in level1_children:
        child_id   = to_kebab(child.get("title", ""))
        child_file = section_dir / f"{child_id}.json"
        child_out  = {
            "id": child_id,
            "title": child.get("title"),
            "url": child.get("url"),
            "breadcrumb": child.get("breadcrumb", []),
            "last_updated": child.get("last_updated"),
            "description": child.get("description"),
            "has_video": child.get("has_video", False),
            "video_url": child.get("video_url"),
            "video_title": child.get("video_title"),
            "notes": child.get("notes"),
            "tables": child.get("tables", []),
            "sections": child.get("sections", []),
            "children": child.get("children", []),
        }
        child_file.write_text(json.dumps(child_out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Wrote: {child_file.relative_to(Path(__file__).parent)}")


# Text Exporter
def node_to_text(node: dict, depth: int = 0) -> str:
    """
    Convert a single JSON node (page) into a readable text block.
    Recursively appends children indented by depth.
    """
    lines = []
    indent = "  " * depth

    title = node.get("title") or "Untitled"
    url   = node.get("url") or ""
    breadcrumb = " > ".join(node.get("breadcrumb") or [])
    last_updated = node.get("last_updated") or ""
    description  = node.get("description") or ""
    notes        = node.get("notes") or ""
    has_video    = node.get("has_video", False)
    video_url    = node.get("video_url") or ""
    video_title  = node.get("video_title") or ""
    sections     = node.get("sections") or []
    tables       = node.get("tables") or []
    children     = node.get("children") or []

    # Title block
    lines.append(f"{indent}{'=' * 60}")
    lines.append(f"{indent}{title.upper()}")
    lines.append(f"{indent}{'=' * 60}")
    if breadcrumb:
        lines.append(f"{indent}Breadcrumb : {breadcrumb}")
    if url:
        lines.append(f"{indent}URL        : {url}")
    if last_updated:
        lines.append(f"{indent}Updated    : {last_updated}")
    if has_video and video_url:
        label = f" ({video_title})" if video_title else ""
        lines.append(f"{indent}Video      : {video_url}{label}")
    lines.append("")

    # Main description
    if description:
        lines.append(f"{indent}{description}")
        lines.append("")

    # Notes / warnings
    if notes:
        lines.append(f"{indent}--- NOTES / WARNINGS ---")
        lines.append(f"{indent}{notes}")
        lines.append("")

    # Structured sections (if present and not already in description)
    if sections:
        for sec in sections:
            heading = sec.get("heading") or ""
            body    = sec.get("body") or ""
            if heading:
                lines.append(f"{indent}## {heading}")
            if body:
                lines.append(f"{indent}{body}")
            lines.append("")

    # Tables
    for table in tables:
        t_title   = table.get("title") or ""
        headers   = table.get("headers") or []
        rows      = table.get("rows") or []
        if t_title:
            lines.append(f"{indent}[TABLE: {t_title}]")
        if headers:
            lines.append(f"{indent}" + " | ".join(headers))
            lines.append(f"{indent}" + "-+-".join(["-" * len(h) for h in headers]))
        for row in rows:
            lines.append(f"{indent}" + " | ".join(str(row.get(h, "")) for h in headers))
        lines.append("")

    # Children (recursive)
    if children:
        lines.append(f"{indent}--- CHILD PAGES ({len(children)}) ---")
        lines.append("")
        for child in children:
            lines.append(node_to_text(child, depth=depth + 1))

    return "\n".join(lines)


def json_file_to_text(json_path: Path, txt_path: Path) -> None:
    """Convert a single .json file to a .txt file."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    text = node_to_text(data)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(text, encoding="utf-8")


def run_text_export(section_filter: str | None = None) -> None:
    """
    Walk Database/ and convert every .json file to a matching .txt file.
    Output goes to Text/<SectionName>/<filename>.txt mirroring the JSON structure.
    """
    text_dir = Path(__file__).parent / "Text"

    if not DATABASE_DIR.exists():
        print(f"[ERROR] Database folder not found: {DATABASE_DIR}")
        sys.exit(1)

    sections = [d for d in DATABASE_DIR.iterdir() if d.is_dir()]
    if section_filter:
        sections = [d for d in sections if d.name.lower() == section_filter.lower()]
        if not sections:
            print(f"[ERROR] Section '{section_filter}' not found in {DATABASE_DIR}")
            sys.exit(1)

    total_written = 0
    print("=" * 60)
    print("  Text Export Mode")
    print("=" * 60)

    for section_dir in sorted(sections):
        print(f"\n  Section: {section_dir.name}")
        out_section = text_dir / section_dir.name
        for json_file in sorted(section_dir.glob("*.json")):
            txt_file = out_section / json_file.with_suffix(".txt").name
            json_file_to_text(json_file, txt_file)
            print(f"  Wrote: {txt_file.relative_to(Path(__file__).parent)}")
            total_written += 1

    print(f"\n  Total files written: {total_written}")
    print("=" * 60)


# Main
def main():
    parser = argparse.ArgumentParser(
        description="BFS Crawler + Text Exporter — IBM Maximo docs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Crawl only:
  python3 crawler.py --url "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing"

  # Crawl and also export to Text/:
  python3 crawler.py --url "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing" --text

  # Crawl multiple sections and export:
  python3 crawler.py --url <URL1> --url <URL2> --text
        """
    )
    parser.add_argument("--url",  action="append", metavar="URL", dest="urls", help="URL to crawl (repeat for multiple)")
    parser.add_argument("--text", action="store_true",                          help="Also export crawled JSON to Text/ as .txt files")
    args = parser.parse_args()

    if not args.urls:
        parser.error("Provide at least one --url to crawl.")

    urls = args.urls

    print("=" * 60)
    print("  Maximo Docs BFS Crawler — Powered by Bob")
    print("=" * 60)
    print(f"  Root URLs     : {len(urls)}")
    print(f"  Output folder : {DATABASE_DIR}/")
    print("=" * 60)

    # Bob detection
    print("\nDetecting Bob CLI...")
    bob_path = find_bob()
    if not bob_path:
        print("[ERROR] Bob CLI not found.")
        sys.exit(1)
    print(f"  Bob found at: {bob_path}")

    # Prompt check
    if not PROMPT_FILE.exists():
        print(f"[ERROR] Prompt file missing: {PROMPT_FILE}")
        sys.exit(1)

    # Patch MCP config
    print("\nPatching MCP config...")
    original_mcp = patch_mcp_config()

    results = []

    try:
        for root_url in urls:
            print(f"\n{'='*60}")
            print(f"  Crawling section: {root_url}")
            print(f"{'='*60}")

            visited, child_order, root = crawl_section(bob_path, root_url.strip())

            if not visited:
                print(f"  [ERROR] Nothing extracted from {root_url}")
                results.append((root_url, False))
                continue

            # Assemble full tree
            print(f"\n  Assembling tree...")
            section_tree = assemble_node(root, visited, child_order)

            # Determine section directory name from root page title
            section_title = section_tree.get("title", "section")
            section_dir   = DATABASE_DIR / section_title

            # Write files
            print(f"\n  Writing files to Database/{section_title}/")
            write_section_files(section_tree, section_dir)

            # If --text flag set, export this section's JSON to TXT immediately
            if args.text:
                print(f"\n  Exporting to Text/{section_title}/")
                run_text_export(section_filter=section_title)

            results.append((root_url, True))

    finally:
        print("\nCleaning up...")
        if original_mcp is not None:
            restore_mcp_config(original_mcp)

    # Summary
    print("\n" + "=" * 60)
    print("  CRAWL SUMMARY")
    print("=" * 60)
    for url, ok in results:
        print(f"  {'✓' if ok else '✗'} {url}")
    done   = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n  Total: {len(results)}  Done: {done}  Failed: {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
