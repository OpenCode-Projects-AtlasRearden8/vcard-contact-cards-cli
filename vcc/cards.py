"""Printable HTML cards: wallet (credit-card size) and pocket (business-card
size), single cards and full cut-out sheets.

Open the generated file in any browser, print at 100% scale ("Actual size",
not "Fit to page"), and cut along the dashed outlines. Pages are laid out for
US Letter. No images are fetched — the QR code is drawn as inline SVG, so the
file works fully offline.
"""

from __future__ import annotations

import html
from typing import List, Optional

from .contacts import Contact
from .privacy import Rules
from .qrsvg import make_qrcode, qr_svg

# name -> (width_mm, height_mm, cols, rows, gap_mm, description)
CARD_SIZES = {
    "wallet": {
        "w": 85.6,
        "h": 53.98,
        "cols": 2,
        "rows": 4,
        "gap": 3.0,
        "label": "Wallet card (credit-card size, 85.6 x 54 mm)",
    },
    "pocket": {
        "w": 88.9,
        "h": 50.8,
        "cols": 2,
        "rows": 5,
        "gap": 0.0,
        "label": "Pocket card (business-card size, 89 x 51 mm)",
    },
}


def _esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def _card_fields(contact: Contact, rules: Rules) -> List[str]:
    lines: List[str] = []
    if contact.org and not rules.is_hidden("org"):
        lines.append(_esc(contact.org))
    if contact.title and not rules.is_hidden("title"):
        lines.append(_esc(contact.title))
    if not rules.is_hidden("phone"):
        for p in contact.phones[:1]:
            lines.append(_esc(p))
    if not rules.is_hidden("email"):
        for e in contact.emails[:1]:
            lines.append(_esc(e))
    if contact.notes and not rules.is_hidden("notes"):
        lines.append(_esc(contact.notes))
    return lines


def card_html(contact: Contact, rules: Optional[Rules] = None, size: str = "wallet",
              with_qr: bool = True, qr_fmt: str = "mecard") -> str:
    rules = rules or Rules.defaults()
    if size not in CARD_SIZES:
        raise ValueError("unknown card size %r (use 'wallet' or 'pocket')" % size)
    profile = CARD_SIZES[size]
    body = _card_fields(contact, rules)
    qr = qr_svg(make_qrcode(contact, rules, qr_fmt)) if with_qr else ""

    return (
        '<div class="card {size}" style="width:{w}mm;height:{h}mm">'
        '<div class="qr">{qr}</div>'
        '<div class="who">'
        '<div class="name">{name}</div>'
        '<div class="lines">{lines}</div>'
        "</div>"
        '<div class="brand">vcc</div>'
        "</div>"
    ).format(
        size=size,
        w=profile["w"],
        h=profile["h"],
        qr=qr,
        name=_esc(contact.display_name()),
        lines="".join('<div>%s</div>' % ln for ln in body),
    )


def _inner_css() -> str:
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #f0f0f0; font-family: Georgia, 'Times New Roman', serif; }
    .card {
      background: #fff; border: 1px dashed #999; position: relative;
      overflow: hidden; text-align: left;
    }
    .qr { position: absolute; left: 4mm; top: 4mm; width: 24mm; height: 24mm; }
    .qr > svg { width: 100%; height: 100%; display: block; }
    .who { position: absolute; left: 32mm; right: 4mm; top: 4mm; bottom: 4mm;
           display: flex; flex-direction: column; justify-content: center; }
    .name { font-size: 14pt; font-weight: bold; line-height: 1.15;
            margin-bottom: 2mm; word-wrap: break-word; }
    .lines div { font-size: 9pt; line-height: 1.35; word-wrap: break-word;
                 overflow-wrap: anywhere; }
    .brand { position: absolute; right: 4mm; bottom: 2mm; font-size: 6pt;
             color: #999; font-family: sans-serif; }
    /* Print layout */
    @page { size: letter; margin: 0; }
    @media print {
      body { background: #fff; }
      .sheet { page-break-after: always; }
    }
    .sheet { display: flex; flex-wrap: wrap; align-content: center;
             justify-content: center; width: 216mm; min-height: 279mm;
             margin: 0 auto; }
    .single { min-height: 279mm; width: 216mm; display: flex;
              align-items: center; justify-content: center; }
    .single .card { box-shadow: 0 0 4mm rgba(0,0,0,.15); border-style: solid;
                    border-color: #ccc; }
    .sheet .cell { flex: none; }
    .note { font-family: sans-serif; font-size: 9pt; text-align: center;
            color: #555; }
    """


def single_card_document(contact: Contact, rules: Optional[Rules] = None,
                         size: str = "wallet", qr_fmt: str = "mecard") -> str:
    if size not in CARD_SIZES:
        raise ValueError("unknown card size %r (use 'wallet' or 'pocket')" % size)
    profile = CARD_SIZES[size]
    card = card_html(contact, rules, size, with_qr=True, qr_fmt=qr_fmt)
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>vcc card - {title}</title>
<style>{css}</style></head>
<body>
<p class="note">{desc} - print at 100% scale ("Actual size"), then cut along the outline.</p>
<div class="single">{card}</div>
</body></html>""".format(
        title=_esc(contact.display_name()),
        css=_inner_css(),
        desc=_esc(profile["label"]),
        card=card,
    )


def sheet_document(contacts: List[Contact], rules: Optional[Rules] = None,
                   size: str = "wallet", qr_fmt: str = "mecard",
                   copies: int = 1) -> str:
    rules = rules or Rules.defaults()
    if size not in CARD_SIZES:
        raise ValueError("unknown card size %r (use 'wallet' or 'pocket')" % size)
    if copies < 1:
        raise ValueError("copies must be at least 1")
    profile = CARD_SIZES[size]
    cells = profile["cols"] * profile["rows"]
    cards: List[str] = []
    for c in contacts:
        card = card_html(c, rules, size, qr_fmt=qr_fmt)
        for _ in range(copies):
            cards.append(card)
    while len(cards) % cells != 0:
        cards.append('<div class="card %s" style="width:%smm;height:%smm"></div>'
                     % (size, profile["w"], profile["h"]))

    pages: List[str] = []
    for i in range(0, len(cards), cells):
        chunk = "".join(
            '<div class="cell" style="margin:%gmm">%s</div>' % (profile["gap"], card)
            for card in cards[i : i + cells]
        )
        pages.append('<div class="sheet">%s</div>' % chunk)

    count = len(contacts)
    return """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>vcc sheet - {desc}</title>
<style>{css}</style></head>
<body>
<p class="note">{count} contact(s), {size} cards on US Letter - print at 100% scale
("Actual size"), then cut along the outlines. {n} card(s) total incl. duplicates/blanks.</p>
{pages}
</body></html>""".format(
        desc=_esc(profile["label"]),
        css=_inner_css(),
        count=count,
        size=_esc(size),
        n=len(cards),
        pages="".join(pages),
    )


__all__ = ["card_html", "single_card_document", "sheet_document", "CARD_SIZES"]
