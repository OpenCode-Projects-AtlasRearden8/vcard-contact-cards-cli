"""Plain-text privacy rules.

Rules live in a small text file (privacy.rules) next to the contact store.
One directive per line:

    hide <field>
    show <field>

Blank lines and lines starting with '#' are ignored. Later rules override
earlier ones. The shipping default hides notes; other commonly hidden
fields are birthday and address — add them by writing your rules file.

Why: printed phone books and wallet cards end up in pockets, purses and
goodwill donation bins. Notes are the place people write the most
personal things ("diabetic, insulin in bag", "met at recovery meeting"),
so they stay off shared output unless you explicitly opt in.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Fields that privacy rules can control.
RULE_FIELDS = ("notes", "birthday", "address", "org", "title", "url", "email", "phone")

DEFAULT_RULES = "hide notes\n"

_RULES_FILENAME = "privacy.rules"


class RulesError(ValueError):
    pass


class Rules:
    def __init__(self, hidden: Optional[Dict[str, bool]] = None) -> None:
        # Empty = nothing hidden; the *default policy* (hide notes) only
        # comes from Rules.defaults() / the default rules text.
        self.hidden: Dict[str, bool] = dict(hidden or {})

    @classmethod
    def defaults(cls) -> "Rules":
        return parse_rules(DEFAULT_RULES)

    def is_hidden(self, field: str) -> bool:
        return self.hidden.get(field, False)

    def visible_phones(self, phones: List[str]) -> List[str]:
        return [] if self.is_hidden("phone") else list(phones)

    def visible_emails(self, emails: List[str]) -> List[str]:
        return [] if self.is_hidden("email") else list(emails)

    def visible_value(self, field: str, value: str) -> str:
        if self.is_hidden(field):
            return ""
        return value

    def describe(self) -> str:
        lines = []
        for f in RULE_FIELDS:
            lines.append("%s %s" % ("hide" if self.is_hidden(f) else "show", f))
        return "\n".join(lines)

    def to_text(self) -> str:
        return DEFAULT_RULES if self.hidden == {"notes": True} else self.describe() + "\n"


def parse_rules(text: str) -> Rules:
    rules = Rules()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] not in ("hide", "show"):
            raise RulesError(
                "privacy.rules line %d: expected 'hide <field>' or 'show <field>', got %r"
                % (lineno, line)
            )
        field = parts[1].lower()
        if field == "emails":
            field = "email"
        if field in ("phones", "tel", "telephone"):
            field = "phone"
        if field not in RULE_FIELDS:
            raise RulesError(
                "privacy.rules line %d: unknown field %r (known: %s)"
                % (lineno, parts[1], ", ".join(RULE_FIELDS))
            )
        if parts[0] == "hide":
            rules.hidden[field] = True
        else:
            rules.hidden.pop(field, None)
    return rules


def parse_rules_file(path: str) -> Rules:
    with open(path, "r", encoding="utf-8") as fh:
        return parse_rules(fh.read())
