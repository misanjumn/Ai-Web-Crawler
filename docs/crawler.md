# Database Documentation
## JSON Structure Reference for Agents & Developers

This document describes the structure of the `Database/` folder produced by `crawler.py`.
It is intended for any agent or developer that needs to read, query, or process the crawled data.

---

## Folder Structure

```
Database/
├── Managing/
│   ├── _index.json
│   ├── using-maximo-manage.json
│   ├── managing-work-centers.json
│   ├── planning-and-scheduling-work.json
│   ├── managing-bim-data.json
│   ├── monitoring-maintenance-budgets.json
│   └── using-maximo-assistant.json
├── Administering/
│   ├── _index.json
│   └── ...
└── <SectionName>/
    ├── _index.json
    └── <subsection-id>.json
```

- One **folder per top-level documentation section** (e.g. Managing, Administering, Configuring)
- Folder name = the H1 heading of the crawled page (spaces replaced with nothing, exact casing)
- Each folder always contains `_index.json` as the master map
- Each direct child of the section gets its own `.json` file
- Deep nested children are stored **inside** their parent's `children[]` array (not as separate files)

---

## File: `_index.json`

The master index for a section. Always the entry point when reading a section.

```json
{
  "id": "managing",
  "title": "Managing",
  "url": "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing",
  "product": "IBM Maximo Manage",
  "version": "Continuous Delivery",
  "last_updated": "2026-06-25",
  "description": "You can plan and schedule work...",
  "breadcrumb": ["IBM Maximo Manage", "Continuous Delivery"],
  "children": [
    {
      "id": "using-maximo-manage",
      "title": "Using Maximo Manage",
      "url": "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing-using-maximo-manage",
      "file": "using-maximo-manage.json"
    }
  ]
}
```

### `_index.json` Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | kebab-case identifier derived from the section title |
| `title` | string | Exact H1 heading from the page |
| `url` | string | Full URL of the section landing page |
| `product` | string | Product name (e.g. "IBM Maximo Manage") |
| `version` | string | Documentation version (e.g. "Continuous Delivery") |
| `last_updated` | string \| null | Date string from the page (YYYY-MM-DD) or null |
| `description` | string \| null | Introductory paragraph text from the page |
| `breadcrumb` | string[] | Ordered array of breadcrumb labels |
| `children` | object[] | Direct children of this section (see below) |

### `children[]` in `_index.json`

Each child is a **pointer** to a file:

| Field | Type | Description |
|---|---|---|
| `id` | string | kebab-case identifier |
| `title` | string | Exact page title |
| `url` | string | Full URL |
| `file` | string | Filename of the child's JSON (e.g. `"using-maximo-manage.json"`) |

---

## File: `<subsection-id>.json`

Each direct child of a section has its own file. The file contains the full subtree of that subsection, with all nested children embedded recursively.

```json
{
  "id": "using-maximo-manage",
  "title": "Using Maximo Manage",
  "url": "https://www.ibm.com/docs/en/maximo-manage/cd?topic=managing-using-maximo-manage",
  "breadcrumb": ["IBM Maximo Manage", "Continuous Delivery", "Managing"],
  "last_updated": "2026-01-09",
  "description": "The IBM Maximo Manage applications are grouped into modules...",
  "has_video": false,
  "video_url": null,
  "video_title": null,
  "notes": null,
  "tables": [],
  "sections": [],
  "children": [
    {
      "id": "assets-module",
      "title": "Assets module",
      "url": "https://...",
      "breadcrumb": ["IBM Maximo Manage", "Continuous Delivery", "Managing", "Using Maximo Manage"],
      "last_updated": "2026-07-24",
      "description": "The Assets module contains applications...",
      "has_video": true,
      "video_url": "https://cdnapisec.kaltura.com/...",
      "video_title": "Introducing assets in IBM Maximo Manage",
      "notes": null,
      "tables": [],
      "sections": [],
      "children": [
        {
          "id": "assets",
          "title": "Assets",
          "url": "https://...",
          "breadcrumb": ["...", "Assets module"],
          "description": "The Assets application tracks physical assets...",
          "has_video": false,
          "video_url": null,
          "video_title": null,
          "notes": null,
          "tables": [],
          "sections": [],
          "children": []
        }
      ]
    }
  ]
}
```

### Subsection JSON Fields

| Field | Type | Description |
|---|---|---|
| `id` | string | kebab-case identifier |
| `title` | string | Exact H1 heading from the page |
| `url` | string | Full URL of the page |
| `breadcrumb` | string[] | Ordered breadcrumb path from root to this page |
| `last_updated` | string \| null | Date string (YYYY-MM-DD) or null if not shown |
| `description` | string \| null | Full body/intro text. `"PAGE_ERROR"` if page failed to load |
| `has_video` | boolean | true if an embedded video was found on the page |
| `video_url` | string \| null | The iframe src URL of the embedded video, or null |
| `video_title` | string \| null | Title text of the video, or null |
| `notes` | string \| null | Any warning, note, or deprecation callout text on the page |
| `tables` | array | Extracted tables (see Tables schema below), or empty array |
| `sections` | array | In-page anchor sections (see Sections schema below), or empty array |
| `children` | array | Recursively nested child pages following this same schema |

---

## Special Fields

### `tables[]`

Present when a page contains one or more data tables.

```json
"tables": [
  {
    "caption": "Planning and Scheduling applications",
    "rows": [
      { "Application": "Graphical Scheduling", "Description": "Maintenance planners can manage upcoming work." },
      { "Application": "Dispatching dashboard", "Description": "Supervisors can see upcoming work assignments." }
    ]
  }
]
```

### `sections[]`

Present when a page has named in-page anchor sections (e.g. Features, Best Practices, Troubleshooting).

```json
"sections": [
  {
    "anchor": "https://...#features",
    "title": "Features",
    "content": "Your system administrator determines what Maximo Assistant can do..."
  },
  {
    "anchor": "https://...#best-practices",
    "title": "Best practices",
    "content": "Start small and scale up..."
  }
]
```

---

## How to Traverse the Database (For Agents)

### Step 1 — Find the section
```
Database/
└── <SectionName>/
    └── _index.json   ← always start here
```

### Step 2 — Read `_index.json`
The `children[]` array lists all direct child files.

### Step 3 — Load a child file
Each child in `_index.json` has a `"file"` field pointing to a `.json` file in the same folder.

### Step 4 — Recurse through `children[]`
Each child JSON has its own `children[]` array with the full subtree embedded. No need to load separate files for deeply nested content — it's all inline.

### Pseudocode
```python
import json
from pathlib import Path

def load_section(section_name: str):
    index = json.loads(Path(f"Database/{section_name}/_index.json").read_text())
    for child_ref in index["children"]:
        child = json.loads(Path(f"Database/{section_name}/{child_ref['file']}").read_text())
        process(child)

def process(node: dict):
    print(node["title"], node["url"])
    for child in node.get("children", []):
        process(child)   # recurse
```

---

## Useful Queries for Agents

| Goal | How |
|---|---|
| Find all pages with videos | Recursively check `has_video == true` |
| Find all deprecated topics | Check `notes` field contains "deprecated" or "no longer available" |
| Find all leaf pages (no children) | Check `children == []` |
| Get full breadcrumb path of a page | Read the `breadcrumb` array |
| Find a page by title | Recursively search `title` field |
| Find all pages under a module | Navigate `children[]` of the module node |
| Get last updated date | Read `last_updated` field (YYYY-MM-DD string or null) |

---

## Naming Conventions

| Item | Convention | Example |
|---|---|---|
| Folder name | Exact H1 title (as-is) | `Managing`, `Administering` |
| File name | kebab-case of page title | `using-maximo-manage.json` |
| `id` field | kebab-case of page title | `"using-maximo-manage"` |
| `_index.json` | Always `_index.json` | — |

---

## Data Freshness

- Each page's `last_updated` field reflects the date shown on the IBM documentation page at the time of crawl
- To refresh data, re-run `crawler.py` with the same URLs — existing folders will be overwritten
- The crawl date is not stored in the JSON — track it externally if needed
