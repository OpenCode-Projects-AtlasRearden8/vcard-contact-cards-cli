"""vCard 3.0 writing and lenient parsing (2.1 / 3.0 / 4.0 read support).

Output targets VERSION:3.0, the flavour every major phone and address book
import accepts with one tap. Parsing is deliberately forgiving: real-world
.vcf files are messy, so we take what we recognise and ignore the rest.
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional, Tuple

from .contacts import Contact
from .privacy import Rules

# --- escaping for TEXT vCard values (RFC 2426) ------------------------------


def escape_text(value: str) -> str:
    v = value if isinstance(value, str) else str(value)
    out = []
    for ch in v:
        if ch in ("\r", "\n"):
            out.append("\\n")
        elif ch in ("\\", ";", ","):
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def unescape_text(value: Optional[str]) -> str:
    if not value:
        return ""
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in ("n", "N"):
                out.append("\n")
                i += 2
                continue
            if nxt in ("\\", ";", ","):
                out.append(nxt)
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def _now_rev() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def contact_to_vcard(contact: Contact, rules: Optional[Rules] = None) -> str:
    rules = rules or Rules.defaults()
    lines: List[str] = ["BEGIN:VCARD", "VERSION:3.0"]

    lines.append("N:%s;%s;;;" % (escape_text(contact.family), escape_text(contact.given)))
    lines.append("FN:%s" % escape_text(contact.display_name()))

    if contact.org and not rules.is_hidden("org"):
        lines.append("ORG:%s" % escape_text(contact.org))
    if contact.title and not rules.is_hidden("title"):
        lines.append("TITLE:%s" % escape_text(contact.title))

    if not rules.is_hidden("phone"):
        for p in contact.phones:
            lines.append("TEL;TYPE=CELL:%s" % escape_text(p))
    if not rules.is_hidden("email"):
        for e in contact.emails:
            lines.append("EMAIL;TYPE=INTERNET:%s" % escape_text(e))

    if contact.url and not rules.is_hidden("url"):
        lines.append("URL:%s" % escape_text(contact.url))
    if contact.address and not rules.is_hidden("address"):
        # A single free-form address line goes into the "street" slot.
        lines.append("ADR;TYPE=HOME:;;%s;;;;" % escape_text(contact.address))
    if contact.birthday and not rules.is_hidden("birthday"):
        lines.append("BDAY:%s" % contact.birthday)
    if contact.notes and not rules.is_hidden("notes"):
        lines.append("NOTE:%s" % escape_text(contact.notes))

    lines.append("REV:%s" % _now_rev())
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def contacts_to_vcf(contacts: List[Contact], rules: Optional[Rules] = None) -> str:
    return "".join(contact_to_vcard(c, rules) for c in contacts)


# --- parsing ----------------------------------------------------------------


def _unfold(text: str) -> List[str]:
    """RFC-style unfolding: continuation lines start with a space or tab."""
    out: List[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line and line[0] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return [ln for ln in out if ln]


def _split_property(line: str) -> Tuple[str, Dict[str, str], str]:
    """Split 'NAME;PARAM=VAL;PARAM=VAL:value' -> (name, params, raw_value)."""
    in_quotes = False
    colon = -1
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ":" and not in_quotes:
            colon = i
            break
    if colon < 0:
        return line.upper(), {}, ""
    head, value = line[:colon], line[colon + 1 :]
    segs = _split_unescaped(head, ";")
    name = segs[0].strip().upper()
    params: Dict[str, str] = {}
    for seg in segs[1:]:
        if "=" in seg:
            k, v = seg.split("=", 1)
            params[k.strip().upper()] = v.strip().strip('"').upper()
        elif seg:
            params[seg.strip().upper()] = ""  # bare TYPE value (2.1 style)
    return name, params, value


def _split_unescaped(value: str, sep: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            buf.append(ch)
            buf.append(value[i + 1])
            i += 2
            continue
        if ch == sep:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _apply_n(value: str, contact: Contact) -> None:
    # N:Family;Given;Additional;Prefixes;Suffixes
    parts = _split_unescaped(value, ";")
    if parts:
        contact.family = unescape_text(parts[0])
    if len(parts) > 1:
        contact.given = unescape_text(parts[1])


def _apply_adr(value: str, contact: Contact) -> None:
    # ADR: pobox;extended;street;locality;region;postal;country
    parts = _split_unescaped(value, ";")
    street = unescape_text(parts[2]) if len(parts) > 2 else ""
    extra = [unescape_text(s) for s in parts[3:7] if len(parts) > 3 and s]
    if street and extra:
        contact.address = street + ", " + ", ".join(extra)
    else:
        contact.address = street


def parse_vcf(text: str) -> List[Contact]:
    contacts: List[Contact] = []
    current: Optional[Contact] = None
    saw_n = False
    fn_used = False

    for line in _unfold(text):
        name, params, value = _split_property(line)
        if name == "BEGIN" and value.strip().upper() == "VCARD":
            current = Contact()
            saw_n = False
            fn_used = False
            continue
        if name == "END" and value.strip().upper() == "VCARD":
            if current is not None:
                contacts.append(current)
            current = None
            continue
        if current is None:
            continue

        if name == "N" and value.strip():
            _apply_n(value, current)
            saw_n = True
        elif name == "FN" and value.strip() and not saw_n and not fn_used:
            # FN-only card: split "Given Family" once.
            given, _, family = unescape_text(value).partition(" ")
            current.given, current.family = given, family
            fn_used = True
        elif name == "ORG" and value:
            current.org = unescape_text(_split_unescaped(value, ";")[0])
        elif name == "TITLE" and value:
            current.title = unescape_text(value)
        elif name == "TEL" and value:
            current.phones.append(unescape_text(value))
        elif name == "EMAIL" and value:
            current.emails.append(unescape_text(value))
        elif name == "URL" and value and not current.url:
            current.url = unescape_text(value)
        elif name == "ADR" and value:
            _apply_adr(value, current)
        elif name == "BDAY" and value:
            current.birthday = unescape_text(value).strip()
        elif name == "NOTE" and value:
            current.notes = unescape_text(value)

    return contacts


__all__ = [
    "escape_text",
    "unescape_text",
    "contact_to_vcard",
    "contacts_to_vcf",
    "parse_vcf",
]
