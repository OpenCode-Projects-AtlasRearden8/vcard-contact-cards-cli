"""QR payload building and SVG rendering for contact cards.

Payload formats:
  - mecard: compact N:Last,First;TEL:...;EMAIL:...;URL:... style — tiny QR,
            scanned reliably even when printed small on a wallet card.
  - vcard:  a mini vCard — bigger QR, but handy for odd readers.

Privacy rules apply before anything is encoded: with the default rules the
QR never contains notes, birthday or address.
"""

from __future__ import annotations

from typing import List, Optional

from .contacts import Contact
from .privacy import Rules
from ._vendor import qrcodegen


def _mecard_escape(value: str) -> str:
    out = []
    for ch in value:
        if ch in ("\\", ";", ",", ":"):
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def mecard_payload(contact: Contact, rules: Rules) -> str:
    parts: List[str] = ["MECARD:"]
    parts.append("N:%s,%s;" % (_mecard_escape(contact.family), _mecard_escape(contact.given)))
    if not rules.is_hidden("phone"):
        for p in contact.phones:
            if p:
                parts.append("TEL:%s;" % _mecard_escape(p))
    if not rules.is_hidden("email"):
        for e in contact.emails:
            if e:
                parts.append("EMAIL:%s;" % _mecard_escape(e))
    if not rules.is_hidden("url") and contact.url:
        parts.append("URL:%s;" % _mecard_escape(contact.url))
    if not rules.is_hidden("org") and contact.org:
        parts.append("ORG:%s;" % _mecard_escape(contact.org))
    if not rules.is_hidden("birthday") and contact.birthday:
        parts.append("BDAY:%s;" % _mecard_escape(contact.birthday))
    if not rules.is_hidden("notes") and contact.notes:
        parts.append("NOTE:%s;" % _mecard_escape(contact.notes))
    return "".join(parts) + ";"


def vcard_payload(contact: Contact, rules: Rules) -> str:
    from .vcard import contacts_to_vcf

    return contacts_to_vcf([contact], rules)


def qr_payload(contact: Contact, rules: Optional[Rules] = None, fmt: str = "mecard") -> str:
    rules = rules or Rules.defaults()
    if fmt == "vcard":
        return vcard_payload(contact, rules)
    if fmt != "mecard":
        raise ValueError("unknown QR payload format %r (use 'mecard' or 'vcard')" % fmt)
    return mecard_payload(contact, rules)


def make_qrcode(contact: Contact, rules: Optional[Rules] = None, fmt: str = "mecard",
                ecl: str = "medium") -> qrcodegen.QrCode:
    rules = rules or Rules.defaults()
    ecc_map = {
        "low": qrcodegen.QrCode.Ecc.LOW,
        "medium": qrcodegen.QrCode.Ecc.MEDIUM,
        "quartile": qrcodegen.QrCode.Ecc.QUARTILE,
        "high": qrcodegen.QrCode.Ecc.HIGH,
    }
    if ecl not in ecc_map:
        raise ValueError("unknown error-correction level %r" % ecl)
    text = qr_payload(contact, rules, fmt)
    return qrcodegen.QrCode.encode_text(text, ecc_map[ecl])


def qr_svg(qr: qrcodegen.QrCode, border_modules: int = 4, dark: str = "#111111",
           light: str = "#ffffff") -> str:
    """Render a QR Code as a standalone SVG string, with a quiet zone."""
    size = qr.get_size()
    dim = size + 2 * border_modules
    parts: List[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
        'shape-rendering="crispEdges">' % (dim, dim),
        '<rect width="%d" height="%d" fill="%s"/>' % (dim, dim, light),
    ]
    run_svgs: List[str] = []
    for y in range(size):
        x0 = -1
        # Merge horizontal runs of dark modules into single rects (smaller SVG).
        rects: List[str] = []
        for x in range(size + 1):
            dark_mod = x < size and qr.get_module(x, y)
            if dark_mod and x0 < 0:
                x0 = x
            elif (not dark_mod) and x0 >= 0:
                rects.append(
                    '<rect x="%d" y="%d" width="%d" height="1" fill="%s"/>'
                    % (x0 + border_modules, y + border_modules, x - x0, dark)
                )
                x0 = -1
        if rects:
            run_svgs.append("".join(rects))
    parts.extend(run_svgs)
    parts.append("</svg>")
    return "".join(parts)


__all__ = [
    "qr_payload",
    "mecard_payload",
    "vcard_payload",
    "make_qrcode",
    "qr_svg",
]
