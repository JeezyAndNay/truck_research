#!/usr/bin/env python3
"""
Truck Research Viewer
Zero dependencies — Python 3 stdlib only.

Usage:
    python3 app.py                          # serves current directory on :8081
    python3 app.py /path/to/truck_research  # explicit repo path
    python3 app.py /path/to/truck_research 9001  # custom port

Quick start on Debian:
    git clone https://github.com/JeezyAndNay/truck_research
    cd truck_research
    python3 app.py
    # open http://localhost:8081
"""

import os
import sys
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8081

TRUCK_ORDER = ["Ram 3500", "Ford F-350", "Chevy Silverado 3500", "GMC Sierra 3500"]

# logo.dev publishable key — set via env var (never hardcode in source)
# Usage: LOGO_DEV_TOKEN=pk_xxx python3 app.py
# Get your free key at https://logo.dev/signup
LOGO_DEV_TOKEN = os.environ.get("LOGO_DEV_TOKEN", "")

TRUCK_COLORS = {
    "Overview":             "#58a6ff",
    "Ram 3500":             "#c8102e",
    "Ford F-350":           "#1565c0",
    "Chevy Silverado 3500": "#d4a017",
    "GMC Sierra 3500":      "#546e7a",
}

# External links per truck — update URLs as needed.
TRUCK_LINKS = {
    "Ram 3500": {
        "logo":   f"https://img.logo.dev/ramtrucks.com?token={LOGO_DEV_TOKEN}",
        "site":   {"label": "Ram 3500",       "url": "https://www.ramtrucks.com/ram-3500.html"},
        "models": [
            {"label": "2019–2025 (5th Gen)", "url": "https://www.ramtrucks.com/ram-3500.html"},
            {"label": "2013–2018 (4th Gen)", "url": "https://www.ramtrucks.com/"},
        ],
        "forum":  {"label": "Ram Forum",      "url": "https://www.ramforumz.com/"},
    },
    "Ford F-350": {
        "logo":   f"https://img.logo.dev/ford.com?token={LOGO_DEV_TOKEN}",
        "site":   {"label": "F-350 Super Duty", "url": "https://www.ford.com/trucks/super-duty/models/f350/"},
        "models": [
            {"label": "2020–2025 (5th Gen)", "url": "https://www.ford.com/trucks/super-duty/models/f350/"},
            {"label": "2017–2019 (4th Gen)", "url": "https://www.ford.com/trucks/super-duty/"},
            {"label": "2011–2016 (3rd Gen)", "url": "https://www.ford.com/trucks/super-duty/"},
        ],
        "forum":  {"label": "Ford Truck Forum", "url": "https://www.ford-trucks.com/forums/"},
    },
    "Chevy Silverado 3500": {
        "logo":   f"https://img.logo.dev/chevrolet.com?token={LOGO_DEV_TOKEN}",
        "site":   {"label": "Silverado HD",   "url": "https://www.chevrolet.com/trucks/silverado/silverado-hd"},
        "models": [
            {"label": "2020–2025 (4th Gen)", "url": "https://www.chevrolet.com/trucks/silverado/silverado-hd"},
            {"label": "2015–2019 (3rd Gen)", "url": "https://www.chevrolet.com/trucks/silverado/silverado-hd"},
        ],
        "forum":  {"label": "GM-Trucks Forum", "url": "https://www.gm-trucks.com/forums/"},
    },
    "GMC Sierra 3500": {
        "logo":   f"https://img.logo.dev/gmc.com?token={LOGO_DEV_TOKEN}",
        "site":   {"label": "Sierra HD",      "url": "https://www.gmc.com/trucks/sierra/sierra-hd"},
        "models": [
            {"label": "2020–2025 AT4 (4th Gen)", "url": "https://www.gmc.com/trucks/sierra/sierra-hd/models/3500hd-at4"},
            {"label": "2020–2025 Denali",         "url": "https://www.gmc.com/trucks/sierra/sierra-hd/models/3500hd-denali"},
            {"label": "2015–2019 (3rd Gen)",      "url": "https://www.gmc.com/trucks/sierra/sierra-hd"},
        ],
        "forum":  {"label": "GM-Trucks Forum", "url": "https://www.gm-trucks.com/forums/"},
    },
}

def doc_type(stem: str) -> str:
    s = stem.lower()
    if s == "readme":          return ""
    if "index"      in s:     return "index"
    if "comparison" in s:     return "compare"
    if "deep_dive"  in s:     return "dive"
    if "known_issue" in s:    return "issues"
    if "towing"     in s:     return "tow"
    if "maintenance" in s:    return "maint"
    if "product"    in s:     return "products"
    return ""

LABELS = {
    "README":                        "Overview",
    "00_index":                      "Master Index",
    "01_comparison_all_four":        "Cross-Brand Comparison",
    # Per-truck shared pattern
    "01_deep_dive":                  "Deep Dive",
    "02_known_issues":               "Known Issues by Year",
    "03_towing_data":                "Towing Data & Ratings",
    "04_maintenance_schedule":       "Maintenance Schedule",
    "05_product_list":               "Product List",
}

def label(path: Path) -> str:
    stem = path.stem
    return LABELS.get(stem) or re.sub(r"^\d+_", "", stem).replace("_", " ").title()

def build_tree() -> list:
    tree = []
    root_files = [f for f in sorted(REPO.glob("*.md")) if f.name != "README.md"]
    if root_files:
        tree.append({
            "label": "Overview",
            "color": TRUCK_COLORS["Overview"],
            "files": [{"name": label(f), "path": f.name, "badge": doc_type(f.stem)} for f in root_files],
        })
    for truck in TRUCK_ORDER:
        folder = REPO / truck
        if not folder.is_dir():
            continue
        files = sorted(folder.glob("*.md"), key=lambda f: (f.stem != "README", f.name))
        tree.append({
            "label": truck,
            "color": TRUCK_COLORS.get(truck, "#58a6ff"),
            "files": [{"name": label(f), "path": f"{truck}/{f.name}", "badge": doc_type(f.stem)} for f in files],
            "links": TRUCK_LINKS.get(truck),
        })
    return tree

def safe_read(rel: str) -> bytes | None:
    try:
        p = (REPO / unquote(rel)).resolve()
        p.relative_to(REPO)
        if p.suffix == ".md" and p.is_file():
            return p.read_bytes()
    except Exception:
        pass
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        route  = parsed.path

        if route in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", PAGE.encode())
        elif route == "/api/tree":
            self._send(200, "application/json", json.dumps(build_tree()).encode())
        elif route == "/api/file":
            rel  = parse_qs(parsed.query).get("p", [""])[0]
            body = safe_read(rel)
            if body is None:
                self.send_error(404)
            else:
                self._send(200, "text/plain; charset=utf-8", body)
        else:
            self.send_error(404)

    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Single-page HTML — all CSS/JS inline, one CDN dependency (marked.js)
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Truck Research</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0f1117;--side:#161b22;--border:#30363d;
  --text:#c9d1d9;--muted:#8b949e;--accent:#58a6ff;
  --head:#e6edf3;--code:#161b22;--row:#ffffff08;
}
body{display:flex;height:100vh;font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
     background:var(--bg);color:var(--text);overflow:hidden}

/* ── sidebar ── */
#sidebar{width:255px;min-width:255px;background:var(--side);
         border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
#sidebar-hd{padding:14px 16px;border-bottom:1px solid var(--border);flex-shrink:0}
#sidebar-hd h1{font-size:13px;font-weight:700;color:var(--head);text-transform:uppercase;letter-spacing:.6px}
#sidebar-hd p{font-size:11px;color:var(--muted);margin-top:2px}
#nav{overflow-y:auto;flex:1;padding:6px 0}
.g-label{padding:10px 14px 3px 13px;font-size:10px;font-weight:700;
          color:var(--muted);text-transform:uppercase;letter-spacing:.8px;
          border-left:3px solid transparent;margin-bottom:1px;
          display:flex;align-items:center;justify-content:space-between}
.nav-btn{display:flex;align-items:center;gap:6px;width:100%;
         padding:5px 10px 5px 22px;background:none;border:none;
         text-align:left;color:var(--muted);font-size:13px;cursor:pointer}
.nav-btn:hover{background:rgba(255,255,255,.05);color:var(--text)}
.nav-btn.active{color:#fff}
.nav-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}

/* ── doc-type badges ── */
.badge{flex-shrink:0;font-size:9px;font-weight:700;letter-spacing:.4px;
       text-transform:uppercase;padding:1px 5px;border-radius:3px}
.b-dive    {background:#0d2d6b;color:#79c0ff}
.b-issues  {background:#4a1500;color:#ffa040}
.b-tow     {background:#0a2a1a;color:#56d364}
.b-maint   {background:#1a1a0a;color:#e8b004}
.b-products{background:#0d2040;color:#58a6ff}
.b-compare {background:#0a2828;color:#39c9bb}
.b-index   {background:#202020;color:#8b949e}

/* ── external links ── */
.link-icons{display:flex;gap:5px;padding-right:2px;flex-shrink:0}
.link-icon{font-size:12px;opacity:.4;text-decoration:none;line-height:1;transition:opacity .15s}
.link-icon:hover{opacity:1}
.model-row{display:flex;flex-wrap:wrap;gap:3px;padding:2px 10px 8px 22px}
.model-tag{font-size:9px;font-weight:600;letter-spacing:.3px;padding:2px 7px;
           border-radius:3px;border:1px solid var(--border);color:var(--muted);
           background:transparent;text-decoration:none;white-space:nowrap;transition:all .15s}
.model-tag:hover{color:var(--text);border-color:var(--muted);background:rgba(255,255,255,.05)}

/* ── main ── */
#main{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;position:relative}
#bar{padding:9px 20px;border-bottom:1px solid var(--border);
     display:flex;align-items:center;flex-shrink:0;min-height:40px}
#doc-title{font-size:13px;font-weight:600;color:var(--muted)}
/* logo watermark — adjust opacity here (default .10) */
#logo-bg{position:absolute;top:40px;left:0;right:0;bottom:0;
         background-repeat:no-repeat;background-position:center;background-size:40%;
         opacity:.10;pointer-events:none;transition:background-image .35s,opacity .35s}
#scroll{flex:1;overflow-y:auto;padding:32px 48px}
#md{max-width:840px}

/* ── markdown ── */
#md h1{font-size:22px;color:var(--head);margin-bottom:16px;padding-bottom:8px;border-bottom:1px solid var(--border)}
#md h2{font-size:17px;color:var(--head);margin:28px 0 10px;padding-bottom:4px;border-bottom:1px solid var(--border)}
#md h3{font-size:14px;color:var(--head);margin:20px 0 8px}
#md h4{font-size:12px;color:var(--muted);margin:16px 0 6px;text-transform:uppercase;letter-spacing:.5px}
#md p{margin-bottom:12px;line-height:1.7}
#md ul,#md ol{margin:0 0 12px 20px;line-height:1.7}
#md li{margin-bottom:3px}
#md a{color:var(--accent);text-decoration:none}
#md a:hover{text-decoration:underline}
#md code{background:var(--code);border:1px solid var(--border);padding:1px 5px;
         border-radius:4px;font:12px/1.4 "SF Mono","Fira Code",monospace}
#md pre{background:var(--code);border:1px solid var(--border);border-radius:6px;
        padding:14px;overflow-x:auto;margin-bottom:16px}
#md pre code{border:none;padding:0;background:none}
#md blockquote{border-left:3px solid var(--accent);margin:0 0 14px;
               padding:8px 16px;background:rgba(88,166,255,.06);border-radius:0 4px 4px 0}
#md blockquote p{margin:0;color:var(--muted)}
#md table{width:100%;border-collapse:collapse;margin-bottom:20px;font-size:13px}
#md th{background:var(--side);color:var(--head);padding:8px 12px;
       text-align:left;border:1px solid var(--border);font-weight:600}
#md td{padding:7px 12px;border:1px solid var(--border);vertical-align:top}
#md tr:nth-child(even) td{background:var(--row)}
#md hr{border:none;border-top:1px solid var(--border);margin:24px 0}
#md input[type=checkbox]{margin-right:6px;accent-color:var(--accent)}

/* ── empty state ── */
#empty{display:flex;flex-direction:column;align-items:center;justify-content:center;
       height:100%;color:var(--muted);gap:12px}
#empty span{font-size:40px;opacity:.35}

/* ── scrollbar ── */
::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
</style>
</head>
<body>

<div id="sidebar">
  <div id="sidebar-hd">
    <h1>&#128763; Truck Research</h1>
    <p>Jeezy &amp; Renay</p>
  </div>
  <div id="nav"></div>
</div>

<div id="main">
  <div id="bar"><span id="doc-title">Select a document</span></div>
  <div id="logo-bg"></div>
  <div id="scroll">
    <div id="md">
      <div id="empty"><span>&#128663;</span><p>Select a document from the sidebar</p></div>
    </div>
  </div>
</div>

<script>
marked.use({ breaks: true, gfm: true });

let active = null;

function rgba(hex, a) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

async function loadTree() {
  const r = await fetch('/api/tree');
  const tree = await r.json();
  const nav = document.getElementById('nav');
  for (const section of tree) {
    const color = section.color || '#58a6ff';
    const lbl = document.createElement('div');
    lbl.className = 'g-label';
    lbl.style.color = color;
    lbl.style.borderLeftColor = color;

    const lblText = document.createElement('span');
    lblText.textContent = section.label;
    lbl.appendChild(lblText);

    if (section.links) {
      const icons = document.createElement('span');
      icons.className = 'link-icons';
      const iconDefs = [
        section.links.site  && { href: section.links.site.url,  title: section.links.site.label,  icon: '🌐' },
        section.links.forum && { href: section.links.forum.url, title: section.links.forum.label, icon: '💬' },
      ].filter(Boolean);
      for (const d of iconDefs) {
        const a = document.createElement('a');
        a.href = d.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.title = d.title; a.className = 'link-icon'; a.textContent = d.icon;
        icons.appendChild(a);
      }
      lbl.appendChild(icons);
    }
    nav.appendChild(lbl);

    if (section.links && section.links.models && section.links.models.length) {
      const row = document.createElement('div');
      row.className = 'model-row';
      for (const m of section.links.models) {
        const a = document.createElement('a');
        a.href = m.url; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.className = 'model-tag'; a.textContent = m.label;
        row.appendChild(a);
      }
      nav.appendChild(row);
    }

    for (const file of section.files) {
      const btn = document.createElement('button');
      btn.className = 'nav-btn';
      btn.title = file.path;
      btn.dataset.path = file.path;
      btn.dataset.color = color;
      btn.dataset.logo = (section.links && section.links.logo) || '';

      const nameSpan = document.createElement('span');
      nameSpan.className = 'nav-name';
      nameSpan.textContent = file.name;
      btn.appendChild(nameSpan);

      if (file.badge) {
        const badge = document.createElement('span');
        badge.className = 'badge b-' + file.badge;
        badge.textContent = file.badge === 'dive'     ? 'Deep Dive'
          : file.badge === 'issues'   ? 'Issues'
          : file.badge === 'tow'      ? 'Towing'
          : file.badge === 'maint'    ? 'Maint'
          : file.badge === 'products' ? 'Products'
          : file.badge === 'compare'  ? 'Compare'
          : file.badge === 'index'    ? 'Index'
          : file.badge;
        btn.appendChild(badge);
      }

      btn.onclick = () => openDoc(file.path, file.name, btn, color);
      nav.appendChild(btn);
    }
  }
}

async function openDoc(path, name, btn, color) {
  if (active) {
    active.classList.remove('active');
    active.style.background = '';
    active.style.color = '';
  }
  active = btn;
  btn.classList.add('active');
  btn.style.background = rgba(color, 0.12);
  btn.style.color = color;

  const bar = document.getElementById('bar');
  bar.style.borderBottomColor = rgba(color, 0.4);
  document.getElementById('doc-title').textContent = name;
  document.getElementById('doc-title').style.color = color;

  const lb = document.getElementById('logo-bg');
  lb.style.backgroundImage = btn.dataset.logo ? `url('${btn.dataset.logo}')` : 'none';

  const md = document.getElementById('md');
  md.innerHTML = '<p style="color:var(--muted)">Loading…</p>';
  try {
    const r = await fetch('/api/file?p=' + encodeURIComponent(path));
    if (!r.ok) throw new Error();
    md.innerHTML = marked.parse(await r.text());
    document.getElementById('scroll').scrollTop = 0;
  } catch {
    md.innerHTML = '<p style="color:#f85149">Failed to load document.</p>';
  }
}

loadTree();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"\n  Truck Research Viewer")
    print(f"  Repo : {REPO}")
    print(f"  URL  : http://localhost:{PORT}")
    token_status = f"loaded ({LOGO_DEV_TOKEN[:8]}...)" if LOGO_DEV_TOKEN else "NOT SET — logos will not load"
    print(f"  Logo : {token_status}")
    print(f"  Stop : Ctrl+C\n")
    try:
        HTTPServer(("", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
