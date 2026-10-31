"""Contact model and local JSON store.

Everything lives in one plain JSON file on disk — no accounts, no cloud.
Default store location is ~/.vcc (override with --store or the VCC_STORE
environment variable).
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Optional

STORE_VERSION = 1

# Fields a contact can carry. "phones" and "emails" are simple lists of
# plain strings; vCard and MECARD writers apply sane TYPE labels.
FIELDS = (
    "given",
    "family",
    "org",
    "title",
    "phones",
    "emails",
    "url",
    "address",
    "birthday",
    "notes",
)


@dataclass
class Contact:
    given: str = ""
    family: str = ""
    org: str = ""
    title: str = ""
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    url: str = ""
    address: str = ""
    birthday: str = ""
    notes: str = ""
    id: str = ""

    def full_name(self) -> str:
        parts = [self.given.strip(), self.family.strip()]
        name = " ".join(p for p in parts if p).strip()
        return name or "(unnamed)"

    def display_name(self) -> str:
        """Preferred display name: full name first, org as fallback."""
        name = self.full_name()
        if name != "(unnamed)":
            return name
        return self.org.strip() or "(unnamed)"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["display_name"] = self.display_name()
        return d

    def validate(self) -> None:
        if not isinstance(self.phones, list) or not isinstance(self.emails, list):
            raise ValueError("phones and emails must be lists")
        if self.phones and not all(isinstance(p, str) for p in self.phones):
            raise ValueError("phone entries must be strings")
        if self.emails and not all(isinstance(e, str) for e in self.emails):
            raise ValueError("email entries must be strings")
        for f in FIELDS:
            v = getattr(self, f)
            if f not in ("phones", "emails") and not isinstance(v, str):
                raise ValueError("field %r must be a string" % f)

    def nonempty(self) -> Dict[str, Any]:
        """Dict of fields that actually carry data (useful for cards/QR)."""
        out: Dict[str, Any] = {}
        for f in FIELDS:
            v = getattr(self, f)
            if isinstance(v, list):
                if v:
                    out[f] = list(v)
            elif v:
                out[f] = v
        return out


def new_id() -> str:
    return uuid.uuid4().hex[:8]


class Store:
    """A tiny JSON-backed contact store."""

    def __init__(self, directory: Optional[str] = None) -> None:
        base = directory or os.environ.get("VCC_STORE") or os.path.join(
            os.path.expanduser("~"), ".vcc"
        )
        self.directory = base
        self.path = os.path.join(base, "contacts.json")

    def ensure(self) -> None:
        os.makedirs(self.directory, exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"version": STORE_VERSION, "contacts": []})

    def load(self) -> List[Contact]:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return []
        contacts: List[Contact] = []
        for entry in data.get("contacts", []):
            known = {f: entry.get(f, "" if f not in ("phones", "emails") else []) for f in FIELDS}
            c = Contact(id=entry.get("id", ""), **known)
            if not c.id:
                c.id = new_id()
            contacts.append(c)
        return contacts

    def save(self, contacts: List[Contact]) -> None:
        for c in contacts:
            c.validate()
        self._write(
            {"version": STORE_VERSION, "contacts": [_contact_dict(c) for c in contacts]}
        )

    def add(self, contact: Contact) -> Contact:
        contacts = self.load()
        if not contact.id:
            contact.id = new_id()
        while any(c.id == contact.id for c in contacts):
            contact.id = new_id()
        contacts.append(contact)
        self.save(contacts)
        return contact

    def find(self, ref: str) -> Optional[Contact]:
        """Look up by id (exact) or case-insensitive name/org substring."""
        contacts = self.load()
        for c in contacts:
            if c.id == ref:
                return c
        ref_l = ref.strip().lower()
        matches = [c for c in contacts if ref_l in c.display_name().lower()]
        if len(matches) == 1:
            return matches[0]
        return None

    def remove(self, cid: str) -> bool:
        contacts = self.load()
        remaining = [c for c in contacts if c.id != cid]
        if len(remaining) == len(contacts):
            return False
        self.save(remaining)
        return True

    def _write(self, data: Dict[str, Any]) -> None:
        os.makedirs(self.directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".contacts-", dir=self.directory)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, self.path)


def _contact_dict(c: Contact) -> Dict[str, Any]:
    d = asdict(c)
    return d


__all__ = ["Contact", "Store", "FIELDS", "new_id", "replace"]
