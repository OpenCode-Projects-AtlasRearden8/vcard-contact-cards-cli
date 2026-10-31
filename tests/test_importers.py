"""Tests for CSV / JSON / VCF importers."""

import json
import textwrap

import pytest

from vcc import importers
from vcc.contacts import Contact
from vcc.vcard import contact_to_vcard
from vcc.privacy import Rules


def test_detect_and_reject_formats(tmp_path):
    assert importers.detect_format("a.CSV") == "csv"
    assert importers.detect_format("contacts.json") == "json"
    assert importers.detect_format("someone.vcf") == "vcf"
    with pytest.raises(ValueError):
        importers.detect_format("photo.png")


def note(content: str) -> str:
    return textwrap.dedent(content).lstrip()


def test_csv_basic_columns(tmp_path):
    path = tmp_path / "people.csv"
    path.write_text(note(
        """
        First,Last,Company,Phone,Email
        Dylan,Asdale,Asdale Dynamics LLC,+15551230000,dylan@example.test
        """),
        encoding="utf-8",
    )
    (c,) = importers.import_csv(str(path))
    assert (c.given, c.family) == ("Dylan", "Asdale")
    assert c.org == "Asdale Dynamics LLC"
    assert c.phones == ["+15551230000"]
    assert c.emails == ["dylan@example.test"]


def test_csv_google_contacts_style_and_multiple_phone_columns(tmp_path):
    path = tmp_path / "google.csv"
    path.write_text(note(
        """
        "First Name","Last Name","Phone 1 - Value","Phone 2 - Value","E-mail 1 - Value"
        Dylan,Asdale,"+1 555 123 0000","+1 555 123 0001",dylan@example.test
        """),
        encoding="utf-8",
    )
    (c,) = importers.import_csv(str(path))
    assert (c.given, c.family) == ("Dylan", "Asdale")
    assert c.phones == ["+1 555 123 0000", "+1 555 123 0001"]
    assert c.emails == ["dylan@example.test"]


def test_csv_quoted_commas_and_blank_rows(tmp_path):
    path = tmp_path / "quotes.csv"
    path.write_text(note(
        """
        Name,Org
        "Doe, Jane",Bubba Gump Shrimp Company
        ,
        Jane,Doe
        """),
        encoding="utf-8",
    )
    contacts = importers.import_csv(str(path))
    assert contacts[0].given == "Jane" and contacts[0].family == "Doe"
    assert contacts[0].org == "Bubba Gump Shrimp Company"
    # the blank row yields nothing; "Jane,Doe" becomes given/family
    assert len(contacts) == 2


def test_csv_semicolon_dialect(tmp_path):
    path = tmp_path / "semi.csv"
    path.write_text('Given;Family;Phone\nMax;Planck;+1 22\n', encoding="utf-8")
    (c,) = importers.import_csv(str(path))
    assert (c.given, c.family) == ("Max", "Planck")
    assert c.phones == ["+1 22"]


def test_json_list_and_wrapped(tmp_path):
    p1 = tmp_path / "list.json"
    p1.write_text(json.dumps([
        {"given": "Ada", "family": "Lovelace", "phones": ["+123"],
         "emails": [], "notes": "inner"},
    ]), encoding="utf-8")
    (c,) = importers.import_json(str(p1))
    assert c.family == "Lovelace" and c.notes == "inner"

    p2 = tmp_path / "wrapped.json"
    p2.write_text(json.dumps({
        "contacts": [{"name": "Grace Hopper", "phones": ["+99"]}],
    }), encoding="utf-8")
    (c2,) = importers.import_json(str(p2))
    assert c2.display_name() == "Grace Hopper"


def test_json_string_lists_accepted(tmp_path):
    p = tmp_path / "str.json"
    p.write_text(json.dumps([{"name": "A B", "phones": "+1", "emails": "a@b"}]),
                 encoding="utf-8")
    (c,) = importers.import_json(str(p))
    assert c.phones == ["+1"] and c.emails == ["a@b"]


def test_json_bad_types_raise(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps([{"given": 42}]), encoding="utf-8")
    with pytest.raises(ValueError):
        importers.import_json(str(p))
    p2 = tmp_path / "shape.json"
    p2.write_text(json.dumps({"people": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        importers.import_json(str(p2))


def test_vcf_import_roundtrip_via_store(tmp_path):
    src = tmp_path / "give.vcf"
    src.write_text(contact_to_vcard(
        Contact(given="Dylan", family="Asdale", phones=["+15551230000"],
                org="Asdale Dynamics, LLC"), Rules()), encoding="utf-8")
    contacts = importers.import_file_any(str(src))
    assert contacts[0].phones == ["+15551230000"]


def test_unknown_extension_rejected(tmp_path):
    p = tmp_path / "nothing.xlsx"
    p.write_text("binary-ish", encoding="utf-8")
    with pytest.raises(ValueError):
        importers.import_file_any(str(p))
