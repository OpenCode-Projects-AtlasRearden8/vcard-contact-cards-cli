"""Tests for vCard writing, escaping, and lenient parsing."""

import datetime

from vcc.contacts import Contact
from vcc.privacy import Rules, parse_rules
from vcc.vcard import (
    contact_to_vcard,
    contacts_to_vcf,
    escape_text,
    parse_vcf,
    unescape_text,
)


def sample_contact(**kw) -> Contact:
    base = dict(
        given="Dylan",
        family="Asdale",
        org="Asdale Dynamics, LLC",
        title="Founder",
        phones=["+15551230000", "+15551230001"],
        emails=["dylan@example.test"],
        url="https://dylanasdale.github.io",
        birthday="1980-01-31",
        notes="met at recovery meeting; insulin in bag",
    )
    base.update(kw)
    return Contact(**base)


# --- escaping ---------------------------------------------------------------


def test_escape_unescape_roundtrip():
    raw = 'Doe, " JD"\\;\nline2\\\\slash'
    esc = escape_text(raw)
    assert "\\," in esc and "\\;" in esc and "\\n" in esc
    assert unescape_text(esc) == raw
    assert unescape_text(None) == ""


# --- writing ----------------------------------------------------------------


def test_vcard_structure_and_required_fields():
    text = contact_to_vcard(sample_contact(), parse_rules(""))
    assert text.startswith("BEGIN:VCARD\r\n")
    assert "VERSION:3.0" in text
    assert text.rstrip().endswith("END:VCARD")
    assert "N:Asdale;Dylan;;;" in text
    assert "FN:Dylan Asdale" in text
    assert "TEL;TYPE=CELL:+15551230000" in text
    assert "EMAIL;TYPE=INTERNET:dylan@example.test" in text
    assert "ORG:Asdale Dynamics\\, LLC" in text
    assert "TITLE:Founder" in text
    assert "URL:https://dylanasdale.github.io" in text
    assert "BDAY:1980-01-31" in text
    assert "NOTE:met at recovery meeting\\; insulin in bag" in text
    assert "REV:" in text


def test_vcard_rev_timestamp_is_utc_format():
    text = contact_to_vcard(sample_contact(), parse_rules(""))
    rev = [l for l in text.split("\r\n") if l.startswith("REV:")][0][4:]
    parsed = datetime.datetime.strptime(rev, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed.year >= 2026


def test_vcf_multiple_contacts():
    vcf = contacts_to_vcf([sample_contact(), sample_contact(given="Ada")], parse_rules(""))
    assert parse_vcf(vcf)[1].given == "Ada"


# --- privacy in output ------------------------------------------------------


def test_private_note_is_omitted_by_rules():
    vcf = contact_to_vcard(sample_contact(), Rules.defaults())
    assert "NOTE:" not in vcf
    assert "insulin" not in vcf
    assert "BDAY:" in vcf  # birthday visible unless a rule hides it


def test_rule_can_show_note_and_hide_birthday():
    from vcc.privacy import parse_rules

    rules = parse_rules("show notes\nhide birthday\n")
    vcf = contact_to_vcard(sample_contact(), rules)
    assert "NOTE:met at recovery meeting\\; insulin in bag" in vcf
    assert "BDAY:" not in vcf


# --- parsing ----------------------------------------------------------------


def test_parse_roundtrip_full_contact():
    c = sample_contact()
    parsed = parse_vcf(contact_to_vcard(c, parse_rules("")))[0]
    assert parsed.family == "Asdale"
    assert parsed.given == "Dylan"
    assert parsed.org == "Asdale Dynamics, LLC"
    assert parsed.title == "Founder"
    assert parsed.phones == ["+15551230000", "+15551230001"]
    assert parsed.emails == ["dylan@example.test"]
    assert parsed.url == "https://dylanasdale.github.io"
    assert parsed.birthday == "1980-01-31"
    assert parsed.notes == "met at recovery meeting; insulin in bag"


def test_parse_handles_folded_lines():
    folded = (
        "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:David\r\n"
        "NOTE:pref:Attachment DJKL text line one\r\n text line two\r\n"
        " tek line three\r\nEND:VCARD\r\n"
    )
    c = parse_vcf(folded)[0]
    assert "text line onetext line twotek line three" in c.notes


def test_parse_accepts_v30_typical_fields():
    vcf = (
        "BEGIN:VCARD\r\nVERSION:3.0\r\nN:Gump;Forrest;;;\r\nFN:Forrest Gump\r\n"
        "ORG:Bubba Gump Shrimp Company\r\nTITLE:Shrimp Man\r\n"
        "TEL;TYPE=WORK,VOICE:+1-555-555-5555\r\n"
        "ADR;TYPE=HOME:;;42 Shore Way;Greenbow;AL;36539;USA\r\n"
        "EMAIL;TYPE=INTERNET:forrest@example.com\r\nEND:VCARD\r\n"
    )
    c = parse_vcf(vcf)[0]
    assert (c.family, c.given) == ("Gump", "Forrest")
    assert c.org == "Bubba Gump Shrimp Company"
    assert c.title == "Shrimp Man"
    assert c.phones == ["+1-555-555-5555"]
    assert "42 Shore Way" in c.address and "Greenbow" in c.address
    assert c.emails == ["forrest@example.com"]


def test_parse_fn_only_card():
    c = parse_vcf("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Jane Q Doe\r\nTEL:+1555\r\nEND:VCARD\r\n")[0]
    assert c.given == "Jane" and c.family == "Q Doe"
    assert c.phones == ["+1555"]


def test_parse_skips_garbage_outside_cards():
    contacts = parse_vcf("X-WRAPPER:hello\r\nBEGIN:VCARD\r\nFN:Only One\r\nEND:VCARD\r\n")
    assert len(contacts) == 1
    assert contacts[0].display_name() == "Only One"


def test_parse_empty_and_none():
    assert parse_vcf("") == []
    assert parse_vcf("\r\n\r\n") == []
