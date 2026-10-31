"""Import contacts from CSV (e.g. a Google Contacts export) or JSON."""

from __future__ import annotations

import csv
import json
import os
import re
from typing import Dict, List, Optional

from .contacts import Contact


def _norm_header(h: str) -> str:
    """'Phone 1 - Value' -> 'phone1value' (punctuation/case-insensitive)."""
    return re.sub(r"[^a-z0-9]", "", h.strip().lower())


# Canonical field -> acceptable header spellings.
_HEADER_ALIASES: Dict[str, str] = {}
for _canon, _alts in {
    "given": ("given", "first", "firstname", "first name"),
    "family": ("family", "last", "lastname", "last name", "surname"),
    "org": ("org", "organization", "organisation", "company", "employer"),
    "title": ("title", "job title", "role", "position"),
    "phones": ("phones", "phone", "tel", "telephone", "mobile",
               "phone 1 - value", "phone 2 - value", "phone 3 - value"),
    "emails": ("emails", "email", "e-mail", "email address",
               "email 1 - value", "email 2 - value"),
    "url": ("url", "website", "web site", "homepage", "webpage"),
    "address": ("address", "street", "street address", "address 1 - value"),
    "birthday": ("birthday", "bday", "date of birth", "dob"),
    "notes": ("notes", "note", "misc", "comments"),
    "name": ("name", "full name", "display name", "fn"),
}.items():
    for _alt in _alts:
        _HEADER_ALIASES[_norm_header(_alt)] = _canon


def detect_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".tsv"):
        return "csv"
    if ext == ".json":
        return "json"
    if ext in (".vcf", ".vcard"):
        return "vcf"
    raise ValueError("unsupported file type %r — expected .csv, .json or .vcf" % ext)


def import_file(path: str, fmt: str) -> List[Contact]:
    if fmt == "csv":
        return import_csv(path)
    if fmt == "json":
        return import_json(path)
    if fmt == "vcf":
        from .vcard import parse_vcf

        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return parse_vcf(fh.read())
    raise ValueError("unknown format %r" % fmt)


def import_file_any(path: str) -> List[Contact]:
    return import_file(path, detect_format(path))


def import_csv(path: str) -> List[Contact]:
    with open(path, "r", encoding="utf-8-sig", newline="", errors="replace") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.get_dialect("excel")
        rows = list(csv.reader(fh, dialect))
    if not rows:
        return []
    header, body = rows[0], rows[1:]

    # canon -> list of column indexes (e.g. Google exports several phone columns)
    col_map: Dict[str, List[int]] = {}
    for idx, h in enumerate(header):
        canon = _HEADER_ALIASES.get(_norm_header(h))
        if canon:
            col_map.setdefault(canon, []).append(idx)

    contacts: List[Contact] = []
    for row in body:
        if not row or not any(cell.strip() for cell in row):
            continue
        c = _row_to_contact(row, col_map)
        if c is not None:
            contacts.append(c)
    return contacts


def _cells(row: List[str], idxs: List[int]) -> List[str]:
    out = []
    for i in idxs:
        if i < len(row) and row[i].strip():
            out.append(row[i].strip())
    return out


def _row_to_contact(row: List[str], col_map: Dict[str, List[int]]) -> Optional[Contact]:
    def many(field: str) -> List[str]:
        return _cells(row, col_map.get(field, []))

    def one(field: str) -> str:
        cells = many(field)
        return cells[0] if cells else ""

    name = one("name")
    given, family = one("given"), one("family")
    org, title, url = one("org"), one("title"), one("url")
    address, birthday, notes = one("address"), one("birthday"), one("notes")
    phones, emails = many("phones"), many("emails")

    if not any((name, given, family, org, title, url, address, birthday, notes,
                phones, emails)):
        return None

    c = Contact(
        given=given,
        family=family,
        org=org,
        title=title,
        phones=phones,
        emails=emails,
        url=url,
        address=address,
        birthday=birthday,
        notes=notes,
    )
    if not given and not family and name:
        if ", " in name:  # "Doe, Jane" style = Family, Given
            family, _, given2 = name.partition(", ")
            c.given, c.family = given2, family
        else:
            g, _, f = name.partition(" ")
            c.given, c.family = g, f
    if not (c.given or c.family or c.org or c.phones or c.emails):
        return None
    return c


def import_json(path: str) -> List[Contact]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return contacts_from_json_data(data)


def contacts_from_json_data(data: object) -> List[Contact]:
    if isinstance(data, dict) and isinstance(data.get("contacts"), list):
        entries = data["contacts"]
    elif isinstance(data, list):
        entries = data
    else:
        raise ValueError(
            "JSON must be a list of contacts or an object with a 'contacts' list"
        )
    out: List[Contact] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each contact must be a JSON object")
        known = {}
        for f in ("given", "family", "org", "title", "url", "address",
                  "birthday", "notes"):
            v = entry.get(f, "")
            if not isinstance(v, str):
                raise ValueError("contact field %r must be a string" % f)
            known[f] = v
        for f in ("phones", "emails"):
            v = entry.get(f, [])
            if isinstance(v, str):
                v = [v]
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise ValueError("contact field %r must be a list of strings" % f)
            known[f] = v
        contact = Contact(**known)
        if not contact.given and not contact.family:
            # fall back to a plain "name"/"full name" field if present
            name = entry.get("name") or entry.get("full name") or entry.get("display name")
            if isinstance(name, str) and name.strip():
                name = name.strip()
                if ", " in name:
                    family, _, given = name.partition(", ")
                    contact.given, contact.family = given, family
                else:
                    given, _, family = name.partition(" ")
                    contact.given, contact.family = given, family
        if not (contact.given or contact.family or contact.org or contact.phones
                or contact.emails):
            continue
        out.append(contact)
    return out


__all__ = [
    "detect_format",
    "import_file",
    "import_file_any",
    "import_csv",
    "import_json",
    "contacts_from_json_data",
]
