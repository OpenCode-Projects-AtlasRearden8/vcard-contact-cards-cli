# vcc — vcard-contact-cards-cli

Five-second contact sharing, fully offline.

`vcc` imports contacts (or takes them one at a time, typed by hand), prints
**pocket-card sheets** and **wallet cards** with scannable QR codes, and
writes **standard `.vcf` files** anyone can import into their phone with a
tap. Plain-text privacy rules keep sensitive notes off everything you share —
by default, and on purpose.

No accounts. No cloud address book. No scraping. Python stdlib plus one
vendored, MIT-licensed pure-Python QR encoder — that's the whole dependency
tree.

## Who it's for

Anyone handing their details to another human without assuming an internet
connection: club members, church and recovery group leaders, small-business
owners, healthcare coworkers, grandparents. It pairs well with our
companion projects:

- **qr-label-maker-cli** — printable QR labels.
- **free-large-print-tech-kit** — big-text guides for helping relatives.

Both fit the same promise: beginner-friendly, step by step, never
condescending.

## Install

```bash
pip install .            # anywhere in a normal Python 3.9+ environment
# once installed:
vcc --help
```

Prefer running without installing? `python -m vcc ...` works from this folder.

## Quick start (about two minutes)

```bash
vcc init                       # creates ~/.vcc with default privacy rules
vcc add                        # hand-type a contact; Enter accepts defaults
vcc list                       # see contacts and their ids
vcc export --out family.vcf    # standard vCard file to share AirDrop-style
vcc sheet --size pocket        # printable cut-out sheet (HTML, print at 100%)
vcc card "Dylan" --size wallet # one card, credit-card size
```

Hand-typing without flags: `vcc add` walks you through name, phones
(`;` separates several), emails, web site, address, birthday, and notes.
You can also pass `--given --family --org --title --phone --email --url
--address --birthday --notes` directly.

### Import from elsewhere

```bash
vcc import google-contacts.csv   # CSV: Google Contacts-style exports, too
vcc import people.json           # JSON list (or {"contacts": [...]})
vcc import someone-else.vcf      # vCards others send you
```

### Print cards that scan

1. `vcc sheet --size wallet --out wallet-sheet.html`
2. Open the file in any browser (works offline; the QR is drawn as inline SVG).
3. Print at **100% scale / "Actual size"** — not "Fit to page" — on US Letter.
4. Cut along the dashed outlines.
   - **wallet** = credit-card size (85.6 × 54 mm), 8-up.
   - **pocket** = business-card size (89 × 51 mm), 10-up.

The QR carries **MECARD** contact data by default (compact, scans reliably
when printed small). `--format vcard` makes a bigger mini-vCard QR if you
prefer.

## Privacy rules (plain text, no taxes)

`~/.vcc/privacy.rules` is a text file you can edit in any editor:

```
hide notes        # the factory default — notes are personal
hide birthday     # add any lines you want
show notes        # later lines win; 'show notes' would un-hide them
```

Recognized fields: `notes`, `birthday`, `address`, `org`, `title`, `url`,
`email`, `phone`. Rules apply to `.vcf` exports, QR payloads, and printed
cards alike. `vcc privacy show` summarizes what's hidden;
`vcc privacy reset` restores `hide notes`.

Why hidden by default? Notes are where people write the most personal
things — "diabetic, insulin in bag", "met at recovery meeting". Items shared
between phones and wallets should not carry those unless you say so.

## Commands

| Command | What it does |
| --- | --- |
| `vcc init` | create the contact store and default privacy rules |
| `vcc add [flags]` | add a contact (interactive prompt without flags) |
| `vcc list` / `list --json` | list contacts / machine-readable output |
| `vcc show NAME_OR_ID` | one contact as JSON |
| `vcc rm ID` | remove a contact |
| `vcc import FILE` | import `.csv`, `.json`, or `.vcf` |
| `vcc export --out FILE.vcf` | write shareable vCard(s) (privacy rules applied) |
| `vcc qr NAME_OR_ID` | print the QR payload text |
| `vcc card NAME_OR_ID --size wallet\|pocket` | single printable card |
| `vcc sheet --size wallet\|pocket [--copies N]` | full cut-out sheet |
| `vcc privacy [show\|reset]` | summarize or restore privacy rules |

Common options: `--store DIR` switches the data directory (default `~/.vcc`,
or `$VCC_STORE`).

Standard options for export/card/sheet: `--contacts NAME_OR_ID ...`,
`--rules FILE`, `--out FILE`, `--format mecard|vcard`.

## Data storage & durability

- Contacts live in `~/.vcc/contacts.json` — one plain, portable file.
- Writes are atomic (temp file + rename), so a power blip won't corrupt it.
- Delete the folder to erase everything; nothing phones home, ever.

## Project layout

```
vcc/
  cli.py         command-line front end (argparse)
  contacts.py    Contact model + atomic JSON store
  vcard.py       vCard 3.0 writer + lenient 2.1/3.0/4.0 parser
  privacy.py     plain-text privacy rules engine
  importers.py   CSV / JSON / VCF import
  qrsvg.py       MECARD/vCard payloads + QR → inline SVG
  cards.py       printable HTML cards and cut-out sheets
  _vendor/       vendored pure-Python QR encoder (Project Nayuki, MIT)
```

## Development

```bash
pip install -e .[test]
pytest
```

67 tests cover vCard escaping/round-trips, pandas-free CSV/JSON import,
privacy rules, QR structure (finder patterns, escaping, size), card HTML
(including leak checks: private notes and HTML metacharacters), and the CLI
end to end.

## License

MIT — `LICENSE`. Copyright (c) 2026 **Asdale Dynamics, LLC**. The vendored QR
encoder keeps its own MIT notice from Project Nayuki (see `LICENSE` footer).

More from the LLC: books and guides at
[dylanasdale.github.io](https://dylanasdale.github.io) — including
*The Massive AI Manual* — aim to explain AI "like a friend would": plain
English, step by step, never condescending.
