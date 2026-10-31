"""vcc — offline contact cards CLI.

Import or hand-type contacts, generate printable pocket-card sheets and
wallet cards with QR codes, and write standard .vcf files others can import
with one tap. Plain-text privacy rules keep sensitive notes out of shared
output by default.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Sequence

from . import cards as cardgen
from . import importers
from .contacts import Contact, Store, new_id
from .privacy import Rules, RulesError, DEFAULT_RULES
from .qrsvg import qr_payload
from .vcard import contacts_to_vcf

PROG = "vcc"


def _add_store_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--store",
        default=argparse.SUPPRESS,
        help="contact store directory (default: ~/.vcc, or $VCC_STORE)",
    )


def _rules_from(store_dir: str, rules_file: Optional[str]) -> Rules:
    paths = ([] if rules_file is None else [rules_file]) or [
        os.path.join(store_dir, "privacy.rules")
    ]
    for path in paths:
        if os.path.exists(path):
            return parse_rules_file_quiet(path)
    return Rules.defaults()


def parse_rules_file_quiet(path: str) -> Rules:
    from .privacy import parse_rules as _parse

    with open(path, "r", encoding="utf-8") as fh:
        return _parse(fh.read())


# --- subcommand handlers ----------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    store = Store(args.store)
    store.ensure()
    _write_default_rules(store.directory)
    print("Contact store ready at %s" % store.path)
    print("Privacy rules: %s" % os.path.join(store.directory, "privacy.rules"))
    return 0


def _write_default_rules(directory: str) -> None:
    path = os.path.join(directory, "privacy.rules")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                "# vcc privacy rules (plain text, one 'hide <field>' or "
                "'show <field>' per line)\n# Fields: " + ", ".join(
                    ("notes", "birthday", "address", "org", "title", "url",
                     "email", "phone")
                ) + "\n# Notes are personal - they stay off cards and .vcf "
                "exports unless you say otherwise.\n" + DEFAULT_RULES
            )


def _make_contact_from_flags(args: argparse.Namespace) -> Contact:
    c = Contact(
        given=args.given or "",
        family=args.family or "",
        org=args.org or "",
        title=args.title or "",
        phones=args.phone or [],
        emails=args.email or [],
        url=args.url or "",
        address=args.address or "",
        birthday=args.birthday or "",
        notes=args.notes or "",
    )
    if not (c.given or c.family or c.org or c.phones or c.emails):
        raise SystemExit("need at least a name, org, phone or email — try --help")
    return c


def _prompt(label: str, default: str = "") -> str:
    suffix = " [%s]" % default if default else ""
    try:
        answer = input("%s%s: " % (label, suffix))
    except EOFError:
        answer = ""
    return (answer or default).strip()


def _prompt_list(label: str, default: str) -> List[str]:
    return [p.strip() for p in _prompt(label, default).split(";") if p.strip()]


def _add_interactively(args: argparse.Namespace) -> Contact:
    print("Hand-typing a contact. Press Enter to accept defaults; ';' separates"
          " multiple phones/emails.")
    given = _prompt("First name")
    family = _prompt("Last name")
    org = _prompt("Organization")
    if not (given or family or org):
        raise SystemExit("at least a name or organization is required")
    return Contact(
        given=given,
        family=family,
        org=org,
        title=_prompt("Title"),
        phones=_prompt_list("Phone(s), separated by ';'", ""),
        emails=_prompt_list("Email(s), separated by ';'", ""),
        url=_prompt("Web site"),
        address=_prompt("Address"),
        birthday=_prompt("Birthday (e.g. 1980-01-31)"),
        notes=_prompt("Notes (private - kept off cards and exports)"),
    )


def cmd_add(args: argparse.Namespace) -> int:
    store = Store(args.store)
    contact = (
        _make_contact_from_flags(args)
        if (args.given or args.family or args.org or args.phone or args.email)
        else _add_interactively(args)
    )
    saved = store.add(contact)
    print("Added %s (id %s)" % (saved.display_name(), saved.id))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    contacts = Store(args.store).load()
    if args.json:
        print(json.dumps(
            {"contacts": [c.to_dict() for c in contacts]}, indent=2,
            ensure_ascii=False,
        ))
        return 0
    if not contacts:
        print("No contacts yet. Try: %s add" % PROG)
        return 0
    for c in contacts:
        extras = ", ".join(
            filter(None, c.phones[:1] + c.emails[:1] + ([c.org] if c.org else []))
        )
        print("%-8s  %-28s %s" % (c.id, c.display_name(), extras))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store = Store(args.store)
    contact = store.find(args.contact)
    if contact is None:
        raise SystemExit("no contact matched %r (use '%s list' for ids)"
                         % (args.contact, PROG))
    print(json.dumps(contact.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    store = Store(args.store)
    if store.remove(args.contact):
        print("Removed %s" % args.contact)
        return 0
    raise SystemExit("no contact with id %r" % args.contact)


def cmd_import(args: argparse.Namespace) -> int:
    store = Store(args.store)
    fmt = args.fmt or importers.detect_format(args.file)
    try:
        incoming = importers.import_file(args.file, fmt)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit("could not import %s: %s" % (args.file, exc))
    existing = store.load()
    existing_keys = {
        (c.display_name().lower(), ",".join(c.phones)) for c in existing
    }
    added, skipped = 0, 0
    for c in incoming:
        c.validate()
        if c.id in {x.id for x in existing}:
            c.id = new_id()
        if (c.display_name().lower(), ",".join(c.phones)) in existing_keys:
            if args.replace:
                pass
            else:
                skipped += 1
                continue
        existing.append(c)
        existing_keys.add((c.display_name().lower(), ",".join(c.phones)))
        added += 1
    store.save(existing)
    print("Imported %d contact(s) from %s%s"
          % (added, args.file, ", skipped %d duplicate(s)" % skipped if skipped else ""))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    store = Store(args.store)
    contacts = _selected_contacts(store, args.contacts)
    rules = _rules_from(store.directory, args.rules)
    vcf = contacts_to_vcf(contacts, rules)
    if args.stdout:
        sys.stdout.write(vcf)
        return 0
    path = args.out or "contacts.vcf"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(vcf)
    print("Wrote %s (%d contact(s); privacy rules applied: %s)"
          % (path, len(contacts), ", ".join(k for k in
              ("notes", "birthday", "address") if rules.is_hidden(k)) or "none"))
    return 0


def cmd_qr(args: argparse.Namespace) -> int:
    store = Store(args.store)
    contact = store.find(args.contact)
    if contact is None:
        raise SystemExit("no contact matched %r" % args.contact)
    rules = _rules_from(store.directory, args.rules)
    print(qr_payload(contact, rules, args.format))
    return 0


def cmd_card(args: argparse.Namespace) -> int:
    store = Store(args.store)
    contact = store.find(args.contact)
    if contact is None:
        raise SystemExit("no contact matched %r" % args.contact)
    rules = _rules_from(store.directory, args.rules)
    html_doc = cardgen.single_card_document(contact, rules, args.size,
                                            qr_fmt=args.format)
    path = args.out or "%s-card.html" % _safe_name(contact)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    print("Wrote %s — open in a browser and print at 100%% scale." % path)
    return 0


def cmd_sheet(args: argparse.Namespace) -> int:
    store = Store(args.store)
    contacts = _selected_contacts(store, args.contacts)
    if not contacts:
        raise SystemExit("no contacts to put on the sheet")
    rules = _rules_from(store.directory, args.rules)
    html_doc = cardgen.sheet_document(contacts, rules, args.size,
                                      qr_fmt=args.format, copies=args.copies)
    path = args.out or "sheet-%s.html" % args.size
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html_doc)
    print("Wrote %s (%d card(s)) — open in a browser and print at 100%% scale."
          % (path, len(contacts) * args.copies))
    return 0


def _safe_name(c: Contact) -> str:
    raw = "".join(ch if ch.isalnum() else "-" for ch in c.display_name().lower())
    return raw.strip("-") or "contact"


def _selected_contacts(store: Store, refs: Optional[Sequence[str]]) -> List[Contact]:
    contacts = store.load()
    if not refs:
        return contacts
    selected: List[Contact] = []
    for ref in refs:
        for token in ref.split(","):
            token = token.strip()
            if not token:
                continue
            c = store.find(token)
            if c is None:
                raise SystemExit("no contact matched %r" % token)
            if c not in selected:
                selected.append(c)
    return selected


def cmd_privacy(args: argparse.Namespace) -> int:
    store = Store(args.store)
    rules_path = os.path.join(store.directory, "privacy.rules")
    if args.action in (None, "show"):
        rules = _rules_from(store.directory, args.rules)
        hidden = [k for k in ("notes", "birthday", "address", "org", "title",
                              "url", "email", "phone") if rules.is_hidden(k)]
        visible = [k for k in ("notes", "birthday", "address", "org", "title",
                               "url", "email", "phone") if not rules.is_hidden(k)]
        print("Rules file: %s%s" % (rules_path,
              " (not created yet)" if not os.path.exists(rules_path) else ""))
        print("Hidden from cards, QR and .vcf: %s" % (", ".join(hidden) or "none"))
        print("Shared: %s" % (", ".join(visible) or "none"))
        return 0
    if args.action == "reset":
        store.ensure()
        _write_default_rules(store.directory)
        print("Wrote default privacy rules to %s" % rules_path)
        return 0
    raise SystemExit("unknown privacy action %r" % args.action)


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Offline contact cards: import or hand-type contacts, "
        "print pocket-card sheets and wallet cards with QR codes, and share "
        "standard .vcf files. Plain-text privacy rules keep sensitive notes "
        "off shared output by default.",
    )
    parser.add_argument("--store", help="contact store directory (default: ~/.vcc)")
    subs = parser.add_subparsers(dest="command", metavar="COMMAND")
    subs.required = True

    p = subs.add_parser("init", help="create the contact store and default privacy rules")
    _add_store_arg(p)
    p.set_defaults(func=cmd_init)

    p = subs.add_parser("add", help="add a contact (flags, or an interactive prompt)")
    _add_store_arg(p)
    for flag, help_ in [
        ("--given", "first name"),
        ("--family", "last name"),
        ("--org", "organization"),
        ("--title", "job title"),
        ("--url", "web site"),
        ("--address", "mailing address"),
        ("--birthday", "birthday, e.g. 1980-01-31"),
        ("--notes", "private notes (kept off cards and exports)"),
    ]:
        p.add_argument(flag, default=None, help=help_)
    p.add_argument("--phone", action="append", default=None, metavar="NUM",
                   help="phone number (repeatable)")
    p.add_argument("--email", action="append", default=None, metavar="ADDR",
                   help="email address (repeatable)")
    p.set_defaults(func=cmd_add)

    p = subs.add_parser("list", help="list contacts (ids shown first)")
    _add_store_arg(p)
    p.add_argument("--json", action="store_true", help="output JSON")
    p.set_defaults(func=cmd_list)

    p = subs.add_parser("show", help="show one contact as JSON (by id or name)")
    _add_store_arg(p)
    p.add_argument("contact", metavar="NAME_OR_ID")
    p.set_defaults(func=cmd_show)

    p = subs.add_parser("rm", help="remove a contact by id")
    _add_store_arg(p)
    p.add_argument("contact", metavar="ID")
    p.set_defaults(func=cmd_rm)

    p = subs.add_parser("import", help="import contacts from a .csv, .json or .vcf file")
    _add_store_arg(p)
    p.add_argument("file")
    p.add_argument("--fmt", choices=("csv", "json", "vcf"),
                   help="force a format (default: detected from the extension)")
    p.add_argument("--replace", action="store_true",
                   help="re-add duplicates instead of skipping them")
    p.set_defaults(func=cmd_import)

    p = subs.add_parser("export", help="write a .vcf file others can import with one tap")
    _add_store_arg(p)
    p.add_argument("--out", help="output .vcf path (default: ./contacts.vcf)")
    p.add_argument("--stdout", action="store_true", help="print the .vcf instead")
    p.add_argument("--contacts", nargs="*", metavar="NAME_OR_ID",
                   help="limit to these contacts (default: all)")
    p.add_argument("--rules", help="privacy rules file (default: <store>/privacy.rules)")
    p.set_defaults(func=cmd_export)

    p = subs.add_parser("qr", help="print the QR payload text for a contact")
    _add_store_arg(p)
    p.add_argument("contact", metavar="NAME_OR_ID")
    p.add_argument("--format", choices=("mecard", "vcard"), default="mecard")
    p.add_argument("--rules")
    p.set_defaults(func=cmd_qr)

    p = subs.add_parser("card", help="make a single printable card file (HTML)")
    _add_store_arg(p)
    p.add_argument("contact", metavar="NAME_OR_ID")
    p.add_argument("--size", choices=("wallet", "pocket"), default="wallet")
    p.add_argument("--out", help="output .html path")
    p.add_argument("--format", choices=("mecard", "vcard"), default="mecard")
    p.add_argument("--rules")
    p.set_defaults(func=cmd_card)

    p = subs.add_parser("sheet", help="make a printable cut-out sheet (HTML)")
    _add_store_arg(p)
    p.add_argument("--size", choices=("wallet", "pocket"), default="wallet")
    p.add_argument("--out", help="output .html path")
    p.add_argument("--contacts", nargs="*", metavar="NAME_OR_ID",
                   help="limit to these contacts (default: all)")
    p.add_argument("--copies", type=int, default=1,
                   help="copies of each card (default: 1)")
    p.add_argument("--format", choices=("mecard", "vcard"), default="mecard")
    p.add_argument("--rules")
    p.set_defaults(func=cmd_sheet)

    p = subs.add_parser(
        "privacy",
        help="show privacy rules ('privacy reset' restores hide-notes default)",
    )
    _add_store_arg(p)
    p.add_argument("action", nargs="?", choices=("show", "reset"), default="show")
    p.add_argument("--rules")
    p.set_defaults(func=cmd_privacy)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # subparser --store shadows the top-level one; fold them together
    if not args.store:
        args.store = None
    try:
        return args.func(args)
    except RulesError as exc:
        sys.stderr.write("Privacy rules error: %s\n" % exc)
        return 2
    except (ValueError, OSError) as exc:
        sys.stderr.write("%s: %s\n" % (PROG, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
