# crawler.py — Requirements & Setup Guide

## Overview

`crawler.py` is a web crawler orchestrator that uses **Bob CLI** in **Browser Dev mode** to crawl IBM documentation pages and extract structured JSON data into the `Database/` folder.

---

## Prerequisites

### 1. Python 3.10+
`crawler.py` requires Python 3.10 or later.

**Check your version:**
```bash
python3 --version
```

**Install if needed:**
- Mac: `brew install python`
- Linux: `sudo apt install python3`
- Windows: https://www.python.org/downloads/

---

### 2. Bob CLI
Bob must be installed and accessible on your system PATH.

**Check if Bob is installed:**
```bash
which bob
bob --version
```

**Expected output:**
```
/usr/local/bin/bob
bob/x.x.x
```

**Install Bob:**
Follow the IBM Bob installation guide for your platform.
After installation, verify with `bob --version`.

---

### 3. Chrome Browser
Bob's Browser Dev mode uses Chrome (via Chrome DevTools Protocol).
Chrome must be installed on your machine.

**Check:**
```bash
# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version

# Linux
google-chrome --version
```

**Install:** https://www.google.com/chrome/

---

### 4. Node.js 18+
Bob CLI and its MCP servers require Node.js.

**Check:**
```bash
node --version
npm --version
```

**Install:**
- Mac: `brew install node`
- Linux: `sudo apt install nodejs npm`
- Windows: https://nodejs.org/

---

### 5. Chrome DevTools MCP Server
Bob's Browser Dev mode requires the **Chrome DevTools MCP server** to be registered in Bob.

**Check if it's configured:**
```bash
bob mcp list
```
Look for `chrome-devtools` in the output.

**Add it if missing:**
```bash
bob mcp add chrome-devtools npx -- -y chrome-devtools-mcp@latest
```

This registers `npx -y chrome-devtools-mcp@latest` as the transport command. `npx` will auto-download the package on first use — no separate `npm install` needed.

**Verify the config** (optional):
```bash
cat ~/.bob/settings/mcp.json
```
You should see:
```json
"chrome-devtools": {
  "command": "npx",
  "args": ["-y", "chrome-devtools-mcp@latest"]
}
```

---

## Project Structure Required

Ensure the following files are present before running:

```
Product-Content-POC/
├── crawler.py                  ← main script
├── prompts/
│   └── crawler.txt             ← Bob crawl prompt (required)
├── Database/                   ← auto-created if missing
└── docs/
    ├── requirements.md         ← this file
    └── crawler.md              ← JSON schema reference
```

---

## Running the Script

### Single URL
```bash
python3 crawler.py --url "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing"
```

### Multiple URLs
```bash
python3 crawler.py \
  --url "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing" \
  --url "https://www.ibm.com/docs/en/maximo-manage/cd?topic=administering" \
  --url "https://www.ibm.com/docs/en/maximo-manage/cd?topic=configuring"
```

### Help
```bash
python3 crawler.py --help
```

---

## What Happens When You Run It

1. Script auto-detects Bob CLI path (cross-platform)
2. Loads `prompts/crawler.txt` and injects the target URL
3. Invokes Bob with:
   - `--chat-mode browser-dev` → Browser Dev mode
   - `--hide-intermediary-output` → no thinking/reasoning shown in terminal
   - `--approval-mode yolo` → auto-approves all tool calls (no prompts)
4. Bob opens Chrome via Chrome DevTools MCP, navigates to the URL
5. Bob crawls all TOC levels recursively and writes JSON to `Database/<SectionName>/`
6. Repeats for each `--url` provided
7. Prints a final summary (✓ / ✗ per URL)

---

## Timeouts

Each URL is allowed up to **30 minutes** to crawl.
Large documentation sections with many nested pages may take significant time.
This is expected — the crawler is thorough by design.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Bob CLI not found` | Run `which bob` — if empty, reinstall Bob and ensure it's on PATH |
| `Prompt file missing` | Ensure `prompts/crawler.txt` exists |
| `chrome-devtools not found` | Run `bob mcp add chrome-devtools npx -- -y chrome-devtools-mcp@latest` |
| `Chrome not found` | Install Chrome from https://www.google.com/chrome/ |
| `Timeout` | Increase `timeout=1800` in `crawler.py` |
| `Permission denied` | Run `chmod +x crawler.py` on Mac/Linux |

---

## Platform Support

| Platform | Supported |
|---|---|
| macOS (Intel) | ✅ |
| macOS (Apple Silicon) | ✅ |
| Linux | ✅ |
| Windows | ✅ |
