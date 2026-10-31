# STATUS — vcard-contact-cards-cli (`vcc`)

Built: 2026-10-31 · by Asdale Dynamics, LLC · MIT licensed
offline contact cards CLI, v1.0.0

## What was built

An offline CLI for five-second contact sharing. Nothing phones home; the
only dependency tree is the Python stdlib plus one vendored pure-Python QR
encoder (Project Nayuki, MIT; `vcc/_vendor/qrcodegen.py`).

Features:

- **Contact store** — one plain JSON file (`~/.vcc/contacts.json`, atomic
  writes); `vcc init`, `add` (flags or interactive hand-typing), `list`,
  `show`, `rm`.
- **Imports** — `.csv` (incl. Google Contacts-style exports: quoted commas,
  semicolon dialect, multiple phone/e-mail columns), `.json` (list or
  `{"contacts": [...]}`, with `name` fallback), `.vcf` (lenient vCard
  2.1/3.0/4.0 reader: folded lines, parameters, N/ORG/TITLE/TEL/EMAIL/URL/
  ADR/BDAY/NOTE).
- **Exports** — standard **vCard 3.0** `.vcf` with RFC-2426 escaping
  (`\,` `\;` `\n` `\\`); verified round-trip: export → re-import → parse.
- **Printables** — `vcc card` (single) and `vcc sheet` (cut-out sheet):
  - *wallet*: credit-card size 85.6 × 54 mm, 2 × 4 per US Letter page.
  - *pocket*: business-card size 89 × 51 mm, 2 × 5 per US Letter page.
  - QR rendered as inline SVG (no network fetch); HTML meets print-friendly
    CSS. Print at 100% / "Actual size", cut along dashed outlines.
- **QR payloads** — MECARD by default (compact, scans small);
  `--format vcard` for a mini-vCard QR; error correction auto-boosted.
- **Privacy rules** — plain text `~/.vcc/privacy.rules`
  (`hide <field>` / `show <field>`, later lines win). Shipping default:
  `hide notes`. Rules gate `.vcf`, QR payload, and printed cards alike;
  `privacy show` / `privacy reset`.

## How to run it

```bash
pip install .            # or: python -m vcc without installing
vcc init
vcc add                  # interactive, or use --given --family --org ...
vcc import people.csv    # csv / json / vcf, format auto-detected
vcc export --out contacts.vcf
vcc sheet --size pocket  # open the HTML in a browser, print at 100%
vcc card "Dylan" --size wallet
vcc privacy show
```

Full command reference and examples: see `README.md`.

## Verification results (2026-10-31)

- `pytest` — **67 passed** (also clean under `-W error`;
  `pyflakes vcc tests` clean).
- Suite covers: vCard escaping + write→parse round-trips, folded lines,
  FN-only cards; CSV/JSON/vCard import edge cases; privacy-rule parsing
  (overrides, aliases, malformed-line errors); QR structure (finder-pattern
  geometry, MECARD escaping, size law `size = 4×version+17`,
  `DataTooLongError`); card HTML leak checks (private notes never reach
  output, HTML metacharacters escaped); end-to-end CLI flows with an
  isolated store (`--store` tmp dirs).
- CLI smoke test end to end: init → typed add with a marker note → CSV
  import → `.vcf` export → **fresh-store re-import of that `.vcf`** → both
  contacts intact with correct fields and org; exported file contains **no**
  private notes-sounding content (privacy default enforced across `.vcf`,
  QR payload, card, and sheet HTML).
- Interactive `vcc add` verified with piped stdin: all eight fields captured
  correctly.
- Package builds via setuptools; `vcc` console script installed and
  functional (`pip install .`).

## Known gaps

- No `vcc edit`; change a contact by `rm` + `add` for now.
- Cards are single-sided only (no back-of-card layout).
- QR is not decoded back by the tool (encoding verified structurally and
  via the canonical Nayuki implementation; scanners worldwide were the
  intended "decoder").
- Photo/image fields in `.vcf` (PHOTO, `embeddedBase64`) are ignored on
  import; TEL parameters (work/home distinction) are not preserved —
  all phones are stored as plain strings.
- No timezone/i18n niceties: `REV` is UTC ISO-8601; sheet pages assume US
  Letter (A4 users should print at 100% and verify a card with the ruler
  table above).
- No GUI, no spell-check, no automatic duplicate resolution beyond a
  name+phones-keyed skip on import.

## Files of note

- `LICENSE` — MIT; copyright line exactly:
  `Copyright (c) 2026 Asdale Dynamics, LLC`
- `README.md` — usage, privacy rationale, crediting Asdale Dynamics, LLC
- `vcc/_vendor/qrcodegen.py` — vendored QR encoder with its MIT notice
- `tests/` — pytest suite described above
