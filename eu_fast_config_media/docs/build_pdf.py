# -*- coding: utf-8 -*-
"""Genera Manual_eu_fast_config.pdf a partir de MANUAL.md.

    python docs/build_pdf.py

Necesita `markdown` (pip install --user markdown), `selenium` y un Chrome
instalado. Convierte el Markdown a un HTML con estilos de impresión y lo manda
a Chrome headless (Page.printToPDF), que respeta CSS moderno mucho mejor que
wkhtmltopdf.

El HTML intermedio se escribe al lado del Markdown para que las rutas
relativas de `img/` resuelvan, y se borra al terminar.
"""
import base64
import os
import re
import sys
import time
import unicodedata

import markdown

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "MANUAL.md")
TMP_HTML = os.path.join(HERE, "_manual_print.html")
OUT_PDF = os.path.join(HERE, "Manual_eu_fast_config.pdf")

TITLE = "Eureka Fast Config"
SUBTITLE = "Manual de usuario"
VERSION = "0.14.1"

# Paleta del propio asistente (static/src/scss/fast_config.scss).
CSS = """
@page { size: A4; margin: 18mm 16mm 16mm 16mm; }

:root {
    --primary: #714b67;
    --primary-dark: #54374d;
    --accent: #017e84;
    --text: #1f1a2e;
    --muted: #7d7591;
    --border: #e6e1ee;
    --bg-soft: #f4f2f7;
}

* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: "Segoe UI", "Inter", system-ui, -apple-system, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: var(--text);
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
}

/* ---------------------------------------------------------- portada */
.cover {
    height: 250mm;
    display: flex;
    flex-direction: column;
    justify-content: center;
    page-break-after: always;
    text-align: left;
}
.cover-rule { width: 64mm; height: 5px; background: var(--primary); margin-bottom: 12mm; }
.cover h1 { font-size: 34pt; line-height: 1.1; margin: 0 0 4mm; color: var(--primary-dark); border: 0; padding: 0; }
.cover .sub { font-size: 17pt; color: var(--muted); margin: 0 0 18mm; font-weight: 400; }
.cover .meta { font-size: 10.5pt; color: var(--muted); }
.cover .meta b { color: var(--text); font-weight: 600; }
.cover .brand { margin-top: 16mm; font-size: 10.5pt; color: var(--primary); font-weight: 600; }

/* ---------------------------------------------------------- títulos */
h1, h2, h3, h4 { font-weight: 700; color: var(--primary-dark); page-break-after: avoid; }

h2 {
    font-size: 18pt;
    margin: 0 0 6mm;
    padding-bottom: 3mm;
    border-bottom: 2px solid var(--primary);
    page-break-before: always;
}
h2.no-break { page-break-before: avoid; }

h3 { font-size: 13pt; margin: 8mm 0 3mm; }
h4 { font-size: 11pt; margin: 6mm 0 2mm; color: var(--primary); }

p { margin: 0 0 3.2mm; orphans: 2; widows: 2; }

a { color: var(--accent); text-decoration: none; }

strong { font-weight: 600; }

/* ---------------------------------------------------------- listas */
ul, ol { margin: 0 0 3.5mm; padding-left: 6mm; }
li { margin-bottom: 1.4mm; }
li > p { margin-bottom: 1.4mm; }

/* ---------------------------------------------------------- tablas */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 0 0 5mm;
    font-size: 9.3pt;
    page-break-inside: avoid;
}
thead { display: table-header-group; }
th {
    background: var(--primary);
    color: #fff;
    text-align: left;
    font-weight: 600;
    padding: 2mm 2.5mm;
}
td { padding: 2mm 2.5mm; border-bottom: 1px solid var(--border); vertical-align: top; }
tbody tr:nth-child(even) td { background: var(--bg-soft); }

/* ---------------------------------------------------------- código */
code {
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 9pt;
    background: var(--bg-soft);
    padding: 0.4mm 1.2mm;
    border-radius: 3px;
    color: var(--primary-dark);
}
pre {
    background: #1f1a2e;
    color: #eae6f2;
    padding: 4mm;
    border-radius: 6px;
    overflow: hidden;
    font-size: 8.6pt;
    line-height: 1.45;
    page-break-inside: avoid;
    margin: 0 0 5mm;
}
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }

/* ---------------------------------------------------------- citas */
blockquote {
    margin: 0 0 5mm;
    padding: 3mm 4mm;
    border-left: 3px solid var(--accent);
    background: var(--bg-soft);
    color: var(--text);
    page-break-inside: avoid;
}
blockquote p:last-child { margin-bottom: 0; }

/* ---------------------------------------------------------- imágenes */
p.figure {
    margin: 4mm 0 6mm;
    text-align: center;
    page-break-inside: avoid;
}
p.figure img {
    max-width: 100%;
    max-height: 195mm;
    border: 1px solid var(--border);
    border-radius: 5px;
}
p.figure .caption {
    display: block;
    margin-top: 1.8mm;
    font-size: 8.6pt;
    color: var(--muted);
    font-style: italic;
}

hr { border: 0; border-top: 1px solid var(--border); margin: 6mm 0; }
"""

FOOTER = (
    '<div style="font-family:\'Segoe UI\',sans-serif;font-size:7.5pt;color:#7d7591;'
    'width:100%;padding:0 16mm;display:flex;justify-content:space-between;">'
    '<span>Eureka Fast Config · Manual de usuario</span>'
    '<span class="pageNumber"></span></div>'
)
HEADER = '<div style="font-size:0;"></div>'


def gh_slug(text):
    """Ancla al estilo GitHub: minúsculas, sin puntuación, espacios a guiones."""
    text = re.sub(r"<[^>]+>", "", text)
    text = unicodedata.normalize("NFC", text).strip().lower()
    text = re.sub(r"[^\w\s\-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def build_html():
    with open(SRC, encoding="utf-8") as fh:
        md_text = fh.read()

    # La portada se compone aparte: fuera el H1 y la línea de firma que lo sigue.
    md_text = re.sub(r"\A#\s+.*?\n", "", md_text, count=1)
    md_text = re.sub(
        r"\AAsistente de puesta en marcha.*?helpdesk@corpoeureka\.com\n",
        "", md_text, count=1, flags=re.S)

    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "toc"],
        extension_configs={"toc": {"slugify": lambda value, sep: gh_slug(value)}},
    )

    # Imágenes: envolver el párrafo para que no se parta y poner pie de figura.
    def figure(match):
        alt, src = match.group(1), match.group(2)
        return ('<p class="figure"><img alt="%s" src="%s"/>'
                '<span class="caption">%s</span></p>' % (alt, src, alt))

    body = re.sub(
        r'<p><img alt="([^"]*)" src="([^"]*)"\s*/?></p>', figure, body)

    # El primer h2 va justo después de la portada: sin salto extra.
    body = body.replace("<h2", '<h2 class="no-break"', 1)

    fecha = time.strftime("%d/%m/%Y")
    cover = """
<div class="cover">
  <div class="cover-rule"></div>
  <h1>%s</h1>
  <p class="sub">%s</p>
  <div class="meta">
    Asistente de puesta en marcha para <b>Odoo 19</b><br/>
    Versión del módulo <b>%s</b> · %s
  </div>
  <div class="brand">CorpoEureka · corpoeureka.com · helpdesk@corpoeureka.com</div>
</div>
""" % (TITLE, SUBTITLE, VERSION, fecha)

    html = ("<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\"/>"
            "<title>%s — %s</title><style>%s</style></head><body>%s%s</body></html>"
            % (TITLE, SUBTITLE, CSS, cover, body))

    with open(TMP_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    return TMP_HTML


def to_pdf(html_path):
    from selenium import webdriver

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1200,1600")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--allow-file-access-from-files")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get("file:///" + html_path.replace("\\", "/"))
        # Dar tiempo a que carguen las 26 capturas antes de imprimir.
        for _ in range(60):
            done = driver.execute_script(
                "return [...document.images].every(i => i.complete);")
            if done:
                break
            time.sleep(0.5)
        time.sleep(1.5)
        res = driver.execute_cdp_cmd("Page.printToPDF", {
            "landscape": False,
            "printBackground": True,
            "preferCSSPageSize": True,
            "displayHeaderFooter": True,
            "headerTemplate": HEADER,
            "footerTemplate": FOOTER,
            "marginTop": 0.71,
            "marginBottom": 0.63,
            "marginLeft": 0.63,
            "marginRight": 0.63,
        })
        with open(OUT_PDF, "wb") as fh:
            fh.write(base64.b64decode(res["data"]))
    finally:
        driver.quit()


def add_outline():
    """Marcadores de navegación y metadatos. Sin esto, 39 páginas son un ladrillo."""
    try:
        import pymupdf
    except ImportError:
        print("  (sin pymupdf: el PDF queda sin marcadores)")
        return

    with open(SRC, encoding="utf-8") as fh:
        headings = [
            (2 if line.startswith("## ") else 3,
             re.sub(r"[*`_]", "", line.lstrip("#").strip()))
            for line in fh
            if line.startswith("## ") or line.startswith("### ")
        ]

    doc = pymupdf.open(OUT_PDF)

    # No se busca el texto del título: en la página del Índice aparecen todos y
    # el primer acierto sería siempre esa página. Se localizan por TAMAÑO de
    # letra (h2 = 18pt, h3 = 13pt; el cuerpo es 10.5pt), recorriendo las páginas
    # en orden y emparejando con la lista de títulos. Se salta la portada.
    found = []
    for i in range(1, len(doc)):
        for block in doc[i].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s["text"].strip()]
                if not spans:
                    continue
                size = max(s["size"] for s in spans)
                if size < 12.5:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                found.append((2 if size >= 17 else 3, text, i + 1))

    toc, cursor, last_page = [], 0, 2
    for level, title in headings:
        page_no = None
        for j in range(cursor, len(found)):
            f_level, f_text, f_page = found[j]
            if f_level == level and f_text[:40] == title[:40]:
                page_no, cursor = f_page, j + 1
                break
        toc.append([level - 1, title, page_no or last_page])
        last_page = page_no or last_page

    doc.set_toc(toc)
    doc.set_metadata({
        "title": "%s — %s" % (TITLE, SUBTITLE),
        "author": "CorpoEureka",
        "subject": "Asistente de puesta en marcha para Odoo 19 (v%s)" % VERSION,
        "keywords": "Odoo, Odoo 19, configuración, Venezuela, CorpoEureka, eu_fast_config",
    })
    doc.saveIncr()
    doc.close()
    print("  marcadores: %d" % len(toc))


if __name__ == "__main__":
    path = build_html()
    to_pdf(path)
    if "--keep-html" not in sys.argv:
        os.remove(path)
    add_outline()
    print("PDF: %s  (%d KB)" % (OUT_PDF, os.path.getsize(OUT_PDF) // 1024))
