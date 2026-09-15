#!/usr/bin/env python3
"""Classics Library — static site generator (stdlib only, python3.9+).

One page per posted piano piece (~/piano-bot), audiobook chapter (~/audiobook-bot) and
history episode (~/scihistory-bot), generated into this repo's root and served by GitHub
Pages at https://luchuz.github.io/classics/ .

    python3 build.py            # rebuild everything (idempotent)
"""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
sys.path.append(str(HOME / "ytgrowth"))
try:
    import gutenberg
except ImportError:      # site still builds without the chapter texts
    gutenberg = None

BASE = "https://luchuz.github.io/classics"
SITE = "Classics Library"
TAGLINE = "Free public-domain sheet music, audiobooks and history — new every day."
CHANNELS = {
    "piano": ("Ambient Ether", "https://www.youtube.com/channel/UCf1AHzKsbggTUuqkR7Y3Y-w"),
    "audiobooks": ("Read Aloud Classic Audiobooks", "https://www.youtube.com/channel/UCuFavSPjv2Q6gYJYVEW0MdA"),
    "history": ("Lamplight History", "https://www.youtube.com/channel/UC9oQJLAfL9nd4lEDRx6S5Fg"),
}
KEEP = {".git", "PUBLISH.md", "deploy.sh", "deploy.log", "build.py", "_src", ".nojekyll", "robots.txt", ".gitignore", "CNAME"}

PIANO = HOME / "piano-bot"
AUDIO = HOME / "audiobook-bot"
HIST = HOME / "scihistory-bot"

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b675f;--line:#e4e0d8;--card:#fff;--accent:#8a3b12;--accent-fg:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a19c93;--line:#2e2d2a;--card:#1f1f1c;--accent:#e0925d;--accent-fg:#161614}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent)}a:hover{text-decoration:underline}
.wrap{max-width:760px;margin:0 auto;padding:0 16px 48px}
header.site{border-bottom:1px solid var(--line);margin-bottom:24px}
header.site .wrap{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;padding:14px 16px}
header.site .brand{font-weight:700;text-decoration:none;color:var(--fg);font-size:1.05em}
header.site nav a{color:var(--muted);text-decoration:none;margin-right:14px}
h1{font-size:1.7em;line-height:1.2;margin:.2em 0 .3em}h2{font-size:1.25em;margin:1.6em 0 .5em}h3{font-size:1.05em;margin:1.2em 0 .4em}
.sub{color:var(--muted);margin:0 0 1em}
.video{position:relative;aspect-ratio:16/9;background:#000;border-radius:10px;overflow:hidden;margin:1em 0}
.video img{width:100%;height:100%;object-fit:cover;display:block;opacity:.92}
.video iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.video button{position:absolute;inset:0;width:100%;height:100%;background:transparent;border:0;cursor:pointer}
.video button::after{content:"";position:absolute;left:50%;top:50%;width:68px;height:48px;transform:translate(-50%,-50%);background:#e62117;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.5)}
.video button::before{content:"";position:absolute;left:calc(50% - 8px);top:calc(50% - 12px);border-style:solid;border-width:12px 0 12px 22px;border-color:transparent transparent transparent #fff;z-index:1}
.btns{display:flex;flex-wrap:wrap;gap:10px;margin:1em 0}
.btn{display:inline-block;padding:9px 16px;border-radius:8px;background:var(--accent);color:var(--accent-fg);text-decoration:none;font-weight:600}
.btn.alt{background:transparent;color:var(--accent);border:1.5px solid var(--accent)}
.pdf{width:100%;height:80vh;min-height:420px;border:1px solid var(--line);border-radius:10px;background:#fff}
.meta{font-size:.92em;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
ul.list{list-style:none;padding:0;margin:0}ul.list li{padding:10px 0;border-bottom:1px solid var(--line)}ul.list li:last-child{border:0}
ul.list a{text-decoration:none;font-weight:600}ul.list small{display:block;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.readalong p{margin:0 0 1em;text-align:left}
.chapters li{margin:.2em 0}
.pn{display:flex;justify-content:space-between;gap:12px;margin:1.5em 0;flex-wrap:wrap}
footer{border-top:1px solid var(--line);margin-top:40px;padding-top:16px;color:var(--muted);font-size:.88em}
img{max-width:100%}pre{white-space:pre-wrap}
.toc{font-size:.95em}
""".strip()

JS = """
document.addEventListener('click',function(e){var b=e.target.closest('.video button');if(!b)return;var v=b.parentNode,id=v.getAttribute('data-id');
var f=document.createElement('iframe');f.src='https://www.youtube-nocookie.com/embed/'+id+'?autoplay=1&rel=0';f.allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';f.allowFullscreen=true;f.title=b.getAttribute('aria-label')||'Video';
v.innerHTML='';v.appendChild(f);});
""".strip()


# ----------------------------------------------------------------------------- helpers
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def yt_id(url: str) -> str | None:
    m = re.search(r"(?:v=|/shorts/|youtu\.be/)([A-Za-z0-9_\-]{6,})", url or "")
    return m.group(1) if m else None


def iso_date(at: str) -> str:
    try:
        return datetime.fromisoformat(at).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return datetime.now().strftime("%Y-%m-%d")


def nice_date(at: str) -> str:
    try:
        return datetime.fromisoformat(at).strftime("%-d %B %Y")
    except (TypeError, ValueError):
        return ""


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def paragraphs(text: str) -> str:
    """Plain text -> <p> blocks. Gutenberg wraps lines at ~70 chars; join them."""
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        t = " ".join(ln.strip() for ln in para.split("\n") if ln.strip())
        t = re.sub(r"_(.+?)_", r"<em>\1</em>", esc(t))
        if t:
            out.append(f"<p>{t}</p>")
    return "\n".join(out)


def video_block(vid: str, label: str) -> str:
    if not vid:
        return ""
    return (f'<div class="video" data-id="{esc(vid)}"><img loading="lazy" src="https://i.ytimg.com/vi/{esc(vid)}/hqdefault.jpg" alt="{esc(label)}">'
            f'<button type="button" aria-label="Play: {esc(label)}"></button>'
            f'<noscript><a href="https://www.youtube.com/watch?v={esc(vid)}">Watch on YouTube: {esc(label)}</a></noscript></div>')


def page(path: str, title: str, desc: str, body: str, section: str, jsonld: list | None = None, og_image: str = "") -> None:
    """Write BASE/<path>/index.html. path '' = home."""
    url = f"{BASE}/{path}/" if path else f"{BASE}/"
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    chan_name, chan_url = CHANNELS.get(section, ("", ""))
    sub = f'<a class="btn alt" href="{chan_url}" rel="noopener">Subscribe on YouTube: {esc(chan_name)}</a>' if chan_url else ""
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc[:300])}">
<link rel="canonical" href="{esc(url)}">
<meta property="og:type" content="{'video.other' if og_image else 'website'}">
<meta property="og:site_name" content="{SITE}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc[:300])}">
<meta property="og:url" content="{esc(url)}">
{f'<meta property="og:image" content="{esc(og_image)}">' if og_image else ''}
<meta name="twitter:card" content="{'summary_large_image' if og_image else 'summary'}">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="site"><div class="wrap"><a class="brand" href="{BASE}/">{SITE}</a>
<nav><a href="{BASE}/piano/">Sheet music</a><a href="{BASE}/audiobooks/">Audiobooks</a><a href="{BASE}/history/">History</a></nav></div></header>
<main class="wrap">
{body}
<p class="btns">{sub}</p>
<footer>
<p>{SITE}: {esc(TAGLINE)}</p>
<p>Sheet music and MIDI from the <a href="https://www.mutopiaproject.org/" rel="noopener">Mutopia Project</a>; audiobook recordings from <a href="https://librivox.org/" rel="noopener">LibriVox</a>; texts from <a href="https://www.gutenberg.org/" rel="noopener">Project Gutenberg</a>; archival images via <a href="https://commons.wikimedia.org/" rel="noopener">Wikimedia Commons</a>. The recordings and texts here are in the public domain; each page states the licence of the score it links to.</p>
<p><a href="{BASE}/piano/">Piano tutorials &amp; sheet music</a> · <a href="{BASE}/audiobooks/">Audiobooks</a> · <a href="{BASE}/history/">History episodes</a></p>
</footer>
</main>
<script>{JS}</script>
</body>
</html>
"""
    out = HERE / path / "index.html" if path else HERE / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    PAGES.append((url, datetime.now().strftime("%Y-%m-%d")))


PAGES: list[tuple[str, str]] = []


# ----------------------------------------------------------------------------- piano
def surname(composer: str) -> str:
    return composer.split()[-1] if composer else ""


def build_piano() -> list[dict]:
    catalog = {p["id"]: p for p in load_json(PIANO / "catalog.json", [])}
    metas = {}
    for m in sorted(PIANO.glob("output/*/meta.json")):
        d = load_json(m, {})
        pid = (d.get("piece") or {}).get("id")
        if pid is not None:
            metas.setdefault(pid, {})[d.get("variant", "normal")] = d.get("youtube", {})
    pieces: dict[int, dict] = {}
    for e in load_json(PIANO / "posted.json", []):
        if str(e.get("url", "")).startswith("skipped") or not e.get("url"):
            continue
        pid = e["id"]
        variant = e.get("variant", "normal")
        p = pieces.setdefault(pid, {"id": pid, "title": e["title"], "composer": e["composer"], "videos": {}, "at": e["at"]})
        p["videos"][variant] = e["url"]
        p["at"] = min(p["at"], e["at"])
    items = []
    for pid, p in pieces.items():
        cat = catalog.get(pid, {})
        meta = metas.get(pid, {})
        yt_meta = meta.get("normal") or meta.get("slow") or {}
        headline = (yt_meta.get("snippet", {}).get("title") or p["title"]).split(" – ")[0].strip() or p["title"]
        comp = p["composer"]; sur = surname(comp)
        long_url = p["videos"].get("normal") or p["videos"].get("slow")
        vid = yt_id(long_url)
        slow_vid = yt_id(p["videos"].get("slow", ""))
        short_vid = yt_id(p["videos"].get("short", ""))
        path = f"piano/{pid}"
        title = f"{headline} – {sur} | Free Sheet Music PDF, MIDI & Piano Tutorial"
        desc = (f"{p['title']} by {comp}: free public-domain sheet music (PDF), MIDI download and a falling-notes piano tutorial video. "
                f"Learn it at full speed{' or at 50% practice speed' if slow_vid else ''}.")
        pdf, midi, info = cat.get("pdf_url", ""), cat.get("midi_url", ""), cat.get("info_url", "")
        others = [q for q in pieces.values() if q["composer"] == comp and q["id"] != pid]
        body = [f"<h1>{esc(headline)}</h1>",
                f'<p class="sub">{esc(comp)}' + (f" · {esc(cat['opus'])}" if cat.get("opus", "").strip("- ") else "") +
                (f" · {esc(cat['style'])}" if cat.get("style") else "") + "</p>",
                "<h2>Piano tutorial (falling notes)</h2>",
                video_block(vid, f"{headline} – {sur} piano tutorial")]
        if slow_vid and slow_vid != vid:
            body += ["<h3>Slow practice version (50% speed)</h3>", video_block(slow_vid, f"{headline} – slow piano tutorial")]
        body += ['<div class="btns">',
                 f'<a class="btn" href="{esc(pdf)}" rel="noopener">Download sheet music (PDF)</a>' if pdf else "",
                 f'<a class="btn alt" href="{esc(midi)}" rel="noopener">Download MIDI</a>' if midi else "",
                 f'<a class="btn alt" href="{esc(info)}" rel="noopener">Score page on Mutopia</a>' if info else "",
                 "</div>"]
        if pdf:
            body += ["<h2>Sheet music</h2>",
                     f'<iframe class="pdf" loading="lazy" src="{esc(pdf)}" title="Sheet music: {esc(p["title"])}"></iframe>',
                     f'<p class="meta">If the score does not display here, <a href="{esc(pdf)}">open the PDF directly</a>.</p>']
        lic = cat.get("license", "")
        body += ['<p class="meta">' + esc(f"{p['title']} — {comp}. ") +
                 (f"Score licence: {esc(lic)}. " if lic else "") +
                 (f"Typeset by {esc(cat['arranger'])} for the Mutopia Project. " if cat.get("arranger") else "") +
                 "The composition is in the public domain.</p>"]
        if short_vid:
            body += [f'<p class="meta">Also on YouTube as a <a href="https://www.youtube.com/shorts/{esc(short_vid)}">60-second Short</a>.</p>']
        if others:
            body += [f"<h2>More by {esc(comp)}</h2>", '<ul class="list">'] + \
                    [f'<li><a href="{BASE}/piano/{q["id"]}/">{esc(q["title"])}</a></li>' for q in sorted(others, key=lambda q: q["title"])] + ["</ul>"]
        ld = [{"@context": "https://schema.org", "@type": "VideoObject", "name": yt_meta.get("snippet", {}).get("title", f"{headline} – {sur} piano tutorial"),
               "description": desc, "thumbnailUrl": [f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"], "uploadDate": iso_date(p["at"]),
               "embedUrl": f"https://www.youtube-nocookie.com/embed/{vid}", "contentUrl": long_url},
              {"@context": "https://schema.org", "@type": "MusicComposition", "name": p["title"], "composer": {"@type": "Person", "name": comp},
               "musicCompositionForm": cat.get("style") or "Classical", "url": f"{BASE}/{path}/"}] if vid else []
        page(path, title, desc, "\n".join(body), "piano", ld, f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")
        items.append({"path": path, "headline": headline, "title": p["title"], "composer": comp, "at": p["at"], "vid": vid})
    items.sort(key=lambda x: x["at"], reverse=True)
    lis = "".join(f'<li><a href="{BASE}/{i["path"]}/">{esc(i["headline"])} – {esc(surname(i["composer"]))}</a><small>{esc(i["title"])} · {esc(i["composer"])} · free PDF + MIDI + tutorial</small></li>' for i in items)
    page("piano", "Free Piano Sheet Music & Tutorials | Classics Library",
         "Free public-domain piano sheet music (PDF + MIDI) with falling-notes tutorial videos. A new piece every day.",
         f"<h1>Piano sheet music &amp; tutorials</h1><p class=\"sub\">Every piece has a free PDF score, a MIDI file and a falling-notes video tutorial. New piece every day.</p><ul class=\"list\">{lis}</ul>",
         "piano")
    return items


# ----------------------------------------------------------------------------- audiobooks
def build_audiobooks() -> list[dict]:
    books = {b["id"]: b for b in load_json(AUDIO / "books.json", [])}
    posted = [e for e in load_json(AUDIO / "posted.json", []) if e.get("variant", "chapter") == "chapter" and e.get("url")]
    metas = {}
    for m in sorted(AUDIO.glob("output/*/meta.json")):
        d = load_json(m, {})
        metas[(d.get("book"), d.get("section"))] = d.get("youtube", {})
    by_book: dict[int, list[dict]] = {}
    for e in posted:
        by_book.setdefault(e["book_id"], []).append(e)
    items = []
    for bid, entries in by_book.items():
        book = books.get(bid, {})
        btitle = book.get("title") or entries[0]["book"]; author = book.get("author") or entries[0]["author"]
        sections = {s["number"]: s for s in book.get("sections", [])}
        entries.sort(key=lambda e: e["section"])
        n_sections = len(book.get("sections", [])) or len(entries)
        chapter_pages = []
        for k, e in enumerate(entries):
            sec = sections.get(e["section"], {})
            label = e.get("section_title") or sec.get("title") or f"Chapter {e['section']}"
            vid = yt_id(e["url"])
            reader = sec.get("reader") or book.get("reader") or ""
            path = f"audiobooks/{bid}/{e['section']}"
            short_label = re.sub(r"^(chapter|part|book|letter)\s*", "", label, flags=re.I)
            title = f"{btitle} {label.split(':')[0] if ':' in label else label} – Free Audiobook & Full Text"
            if len(title) > 70:
                title = f"{btitle} – {label.split(':')[0]} | Free Audiobook"
            desc = f"{btitle} by {author}, {label}: free public-domain audiobook read aloud (LibriVox), with the full chapter text to read along."
            text = None
            if gutenberg and book.get("url_text"):
                try:
                    text = gutenberg.chapter_for_section(book["url_text"], e["section"], label, n_sections)
                except Exception as ex:  # noqa: BLE001
                    print(f"  gutenberg failed for {btitle} s{e['section']}: {ex}")
            prev_e = entries[k - 1] if k > 0 else None
            next_e = entries[k + 1] if k + 1 < len(entries) else None
            body = [f"<h1>{esc(btitle)}: {esc(label)}</h1>",
                    f'<p class="sub">by {esc(author)}' + (f" · read by {esc(reader)}" if reader else "") +
                    (f" · {int(sec['seconds'])//60} min" if sec.get("seconds") else "") + "</p>",
                    video_block(vid, f"{btitle} – {label} audiobook"),
                    '<div class="btns">',
                    f'<a class="btn alt" href="{BASE}/audiobooks/{bid}/">All chapters of this book</a>',
                    f'<a class="btn alt" href="{esc(book["url_text"])}" rel="noopener">Full text on Project Gutenberg</a>' if book.get("url_text") else "",
                    f'<a class="btn alt" href="{esc(book["url_librivox"])}" rel="noopener">Recording on LibriVox</a>' if book.get("url_librivox") else "",
                    "</div>"]
            if text:
                body += ["<h2>Read along: full text of this chapter</h2>", f"<h3>{esc(text[0])}</h3>", '<div class="readalong">', paragraphs(text[1]), "</div>"]
            body += ['<div class="pn">',
                     f'<a href="{BASE}/audiobooks/{bid}/{prev_e["section"]}/">← Previous: {esc(prev_e.get("section_title") or "Chapter " + str(prev_e["section"]))}</a>' if prev_e else "<span></span>",
                     f'<a href="{BASE}/audiobooks/{bid}/{next_e["section"]}/">Next: {esc(next_e.get("section_title") or "Chapter " + str(next_e["section"]))} →</a>' if next_e else "<span></span>",
                     "</div>",
                     f'<p class="meta">Recording by {esc(reader)} for LibriVox, released into the public domain. Text: {esc(btitle)} by {esc(author)}, public domain.</p>']
            ld = [{"@context": "https://schema.org", "@type": "VideoObject", "name": f"{btitle} – {label} | {author} Audiobook",
                   "description": desc, "thumbnailUrl": [f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"], "uploadDate": iso_date(e["at"]),
                   "embedUrl": f"https://www.youtube-nocookie.com/embed/{vid}", "contentUrl": e["url"]},
                  {"@context": "https://schema.org", "@type": "Chapter", "name": label, "position": e["section"],
                   "isPartOf": {"@type": "Book", "name": btitle, "author": {"@type": "Person", "name": author}, "url": f"{BASE}/audiobooks/{bid}/"},
                   "url": f"{BASE}/{path}/"}] if vid else []
            page(path, title, desc, "\n".join(body), "audiobooks", ld, f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")
            chapter_pages.append((path, label, vid, e))
        # book page
        first_vid = chapter_pages[0][2] if chapter_pages else None
        body = [f"<h1>{esc(btitle)}</h1>", f'<p class="sub">by {esc(author)}' + (f" ({esc(book['author_years'])})" if book.get("author_years") else "") +
                (f" · first published {esc(book['year'])}" if book.get("year") else "") + (f" · read by {esc(book['reader'])}" if book.get("reader") else "") + "</p>"]
        if book.get("description"):
            body += [f"<p>{esc(book['description'])}</p>"]
        body += [f"<h2>Chapters ({len(chapter_pages)} of {n_sections} posted)</h2>", '<ul class="list">'] + \
                [f'<li><a href="{BASE}/{p}/">{esc(lbl)}</a><small>{nice_date(e["at"])}</small></li>' for p, lbl, v, e in chapter_pages] + \
                ["</ul>", '<div class="btns">',
                 f'<a class="btn alt" href="{esc(book["url_text"])}" rel="noopener">Full text on Project Gutenberg</a>' if book.get("url_text") else "",
                 f'<a class="btn alt" href="{esc(book["url_librivox"])}" rel="noopener">Recording on LibriVox</a>' if book.get("url_librivox") else "", "</div>"]
        ld = [{"@context": "https://schema.org", "@type": "Book", "name": btitle, "author": {"@type": "Person", "name": author}, "url": f"{BASE}/audiobooks/{bid}/",
               "workExample": {"@type": "Audiobook", "name": f"{btitle} (LibriVox)", "readBy": {"@type": "Person", "name": book.get("reader", "")}}}]
        page(f"audiobooks/{bid}", f"{btitle} – {author} | Free Audiobook & Full Text, Chapter by Chapter",
             f"{btitle} by {author}: free public-domain audiobook, one chapter a day, with the full text to read along.",
             "\n".join(body), "audiobooks", ld, f"https://i.ytimg.com/vi/{first_vid}/hqdefault.jpg" if first_vid else "")
        items.append({"path": f"audiobooks/{bid}", "title": btitle, "author": author, "n": len(chapter_pages), "at": max(e["at"] for e in entries)})
    items.sort(key=lambda x: x["at"], reverse=True)
    lis = "".join(f'<li><a href="{BASE}/{i["path"]}/">{esc(i["title"])}</a><small>{esc(i["author"])} · {i["n"]} chapter{"s" if i["n"] != 1 else ""} posted</small></li>' for i in items)
    page("audiobooks", "Free Classic Audiobooks with Full Text | Classics Library",
         "Free public-domain audiobooks read aloud, one chapter a day, each with the full text to read along.",
         f"<h1>Classic audiobooks, read aloud</h1><p class=\"sub\">Public-domain recordings from LibriVox, one chapter a day, with the full chapter text on every page.</p><ul class=\"list\">{lis}</ul>",
         "audiobooks")
    return items


# ----------------------------------------------------------------------------- history
def _run_dir(slug: str) -> Path | None:
    dirs = [d for d in sorted(HIST.glob("output/*-" + slug), reverse=True) if (d / "script.json").exists()]
    return dirs[0] if dirs else None


def build_history() -> list[dict]:
    items = []
    for e in load_json(HIST / "posted.json", []):
        slug = e.get("slug"); url = e.get("url", "")
        if not slug:
            continue
        d = _run_dir(slug)
        if d is None:
            print(f"  history: no run dir with script.json for {slug}, skipping")
            continue
        topic = load_json(d / "topic.json", {"slug": slug, "title": e.get("title", slug), "lane": e.get("lane", ""), "subject": ""})
        script = load_json(d / "script.json", {})
        meta = load_json(d / "meta.json", {}).get("snippet", {})
        plan = script.get("plan", {}); chapters = script.get("chapters", [])
        vid = yt_id(url)
        title_txt = topic.get("title") or e.get("title", slug)
        path = f"history/{slug}"
        title = f"{title_txt} | Lamplight History (full transcript)"
        desc = plan.get("blurb") or topic.get("subject") or title_txt
        # timestamps from the YouTube description's CHAPTERS block, if any
        marks = []
        m = re.search(r"CHAPTERS\n(.*?)(?:\n\n|$)", meta.get("description", ""), re.S)
        if m:
            for ln in m.group(1).split("\n"):
                mm = re.match(r"^(\d+:\d\d(?::\d\d)?)\s+(.*)$", ln.strip())
                if mm:
                    marks.append((mm.group(1), mm.group(2)))
        credits = []
        m = re.search(r"IMAGES[^\n]*\n(.*?)(?:\n\n|$)", meta.get("description", ""), re.S)
        if m:
            credits = [ln.strip("• ").strip() for ln in m.group(1).split("\n") if ln.strip()]
        lane_word = {"science": "Science history", "decision": "Decisions that changed history", "archaeology": "Archaeology"}.get(topic.get("lane", ""), "History")
        body = [f"<h1>{esc(title_txt)}</h1>", f'<p class="sub">{esc(lane_word)}' + (f" · {esc(topic['subject'])}" if topic.get("subject") else "") +
                (f" · {e['minutes']} min" if e.get("minutes") else "") + "</p>",
                video_block(vid, title_txt) if vid else "",
                f"<p>{esc(plan.get('blurb', ''))}</p>" if plan.get("blurb") else ""]
        if chapters:
            body += ["<h2>Chapters</h2>", '<ol class="chapters toc">']
            for i, c in enumerate(chapters):
                ts = marks[i][0] if i < len(marks) else ""
                link = f'<a href="https://www.youtube.com/watch?v={vid}&t={_secs(ts)}s">{esc(ts)}</a> ' if (vid and ts) else (esc(ts) + " " if ts else "")
                body.append(f'<li>{link}<a href="#ch{i+1}">{esc(c.get("title", f"Chapter {i+1}"))}</a></li>')
            body += ["</ol>", "<h2>Full transcript</h2>"]
            for i, c in enumerate(chapters):
                body += [f'<section id="ch{i+1}"><h3>{i+1}. {esc(c.get("title", ""))}</h3>', paragraphs(c.get("text", "")), "</section>"]
        sources, seen = [], set()
        for c in chapters:
            for s in c.get("sources", []):
                if s.get("url") and s["url"] not in seen:
                    seen.add(s["url"]); sources.append(s)
        if sources:
            body += ["<h2>Sources</h2>", "<ul>"] + [f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s.get("title") or s["url"])}</a></li>' for s in sources] + ["</ul>"]
        if credits:
            body += ["<h2>Image credits</h2>", '<ul class="meta">'] + [f"<li>{_linkify(esc(c))}</li>" for c in credits] + ["</ul>"]
        body += ['<p class="meta">This episode was researched and written with AI assistance from the sources above and narrated with a synthetic voice. Corrections are welcome in the YouTube comments.</p>']
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": title_txt, "description": desc[:300], "datePublished": iso_date(e.get("at", "")),
               "author": {"@type": "Organization", "name": "Lamplight History"}, "url": f"{BASE}/{path}/", "articleSection": lane_word}]
        if vid:
            ld.append({"@context": "https://schema.org", "@type": "VideoObject", "name": meta.get("title") or title_txt, "description": desc[:300],
                       "thumbnailUrl": [f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"], "uploadDate": iso_date(e.get("at", "")),
                       "embedUrl": f"https://www.youtube-nocookie.com/embed/{vid}", "contentUrl": url})
        page(path, title, desc, "\n".join(body), "history", ld, f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")
        items.append({"path": path, "title": title_txt, "lane": lane_word, "at": e.get("at", ""), "minutes": e.get("minutes")})
    items.sort(key=lambda x: x["at"], reverse=True)
    lis = "".join(f'<li><a href="{BASE}/{i["path"]}/">{esc(i["title"])}</a><small>{esc(i["lane"])}{" · " + str(i["minutes"]) + " min" if i.get("minutes") else ""} · {nice_date(i["at"])}</small></li>' for i in items)
    empty = "" if items else "<p>The first episode is on its way. Subscribe on YouTube to catch it.</p>"
    page("history", "Lamplight History – Long-Form History Episodes with Transcripts | Classics Library",
         "Calm, long-form narrated history: science, decisions and archaeology. Every episode with a full transcript and sources.",
         f"<h1>Lamplight History</h1><p class=\"sub\">Science history, decisions and archaeology, told slowly. Full transcript and sources with every episode.</p>{empty}<ul class=\"list\">{lis}</ul>",
         "history")
    return items


def _secs(ts: str) -> int:
    parts = [int(x) for x in ts.split(":")] if ts else [0]
    s = 0
    for p in parts:
        s = s * 60 + p
    return s


def _linkify(s: str) -> str:
    return re.sub(r"(https?://[^\s<]+)", r'<a href="\1" rel="noopener">\1</a>', s)


# ----------------------------------------------------------------------------- home, sitemap
def build_home(piano, audio, hist) -> None:
    def col(head, href, items, fmt):
        lis = "".join(fmt(i) for i in items[:6])
        return f'<div class="card"><h2 style="margin-top:0"><a href="{href}">{head}</a></h2><ul class="list">{lis}</ul></div>'
    body = [f"<h1>{SITE}</h1>", f'<p class="sub">{esc(TAGLINE)}</p>', '<div class="grid">',
            col("Piano sheet music", f"{BASE}/piano/", piano, lambda i: f'<li><a href="{BASE}/{i["path"]}/">{esc(i["headline"])}</a><small>{esc(i["composer"])}</small></li>'),
            col("Audiobooks", f"{BASE}/audiobooks/", audio, lambda i: f'<li><a href="{BASE}/{i["path"]}/">{esc(i["title"])}</a><small>{esc(i["author"])}</small></li>'),
            col("History", f"{BASE}/history/", hist, lambda i: f'<li><a href="{BASE}/{i["path"]}/">{esc(i["title"])}</a><small>{esc(i["lane"])}</small></li>'),
            "</div>",
            "<h2>What this is</h2>",
            "<p>Three small daily YouTube channels, and the pages that go with them: a falling-notes piano tutorial with the free score and MIDI for every piece, "
            "a classic audiobook chapter with the full text to read along, and a long-form history episode with its complete transcript and sources. "
            "Everything here is public domain or openly licensed.</p>"]
    page("", f"{SITE} – Free Sheet Music, Audiobooks & History", TAGLINE, "\n".join(body), "")


def write_sitemap() -> None:
    urls = "".join(f"<url><loc>{esc(u)}</loc><lastmod>{d}</lastmod></url>" for u, d in PAGES)
    (HERE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    (HERE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    (HERE / ".nojekyll").touch()


def clean() -> None:
    for p in HERE.iterdir():
        if p.name in KEEP:
            continue
        if p.is_dir():
            shutil.rmtree(p)
        elif p.suffix in (".html", ".xml"):
            p.unlink()


def main() -> None:
    clean()
    piano = build_piano()
    audio = build_audiobooks()
    hist = build_history()
    build_home(piano, audio, hist)
    write_sitemap()
    print(f"built {len(PAGES)} pages: {len(piano)} piano, {sum(i['n'] for i in audio)} audiobook chapters in {len(audio)} books, {len(hist)} history")


if __name__ == "__main__":
    main()
