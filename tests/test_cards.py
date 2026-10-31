"""Tests for printable card HTML generation."""

import pytest

from vcc import cards
from vcc.contacts import Contact
from vcc.privacy import Rules, parse_rules


def contact(**kw) -> Contact:
    base = dict(
        given="Dylan", family="Asdale", org="Asdale Dynamics, LLC",
        title="Founder", phones=["+15551230000"], emails=["dylan@example.test"],
        url="https://dylanasdale.github.io", notes="keep this private please",
    )
    base.update(kw)
    return Contact(**base)


def test_card_sizes_are_defined_and_valid():
    for size, p in cards.CARD_SIZES.items():
        assert 80 <= p["w"] <= 95
        assert 45 <= p["h"] <= 60
        assert p["cols"] * p["rows"] >= 1


def test_single_card_document_contents():
    doc = cards.single_card_document(contact(), Rules.defaults(), "wallet")
    assert doc.lstrip().startswith("<!DOCTYPE html>")
    assert "Dylan Asdale" in doc
    assert "<svg" in doc  # QR embedded inline, no network fetch
    assert 'class="card wallet"' in doc


def test_private_note_never_reaches_cards():
    doc = cards.single_card_document(contact(), Rules.defaults(), "pocket")
    assert "keep this private please" not in doc
    sheet = cards.sheet_document([contact()], Rules.defaults(), "wallet")
    assert "keep this private please" not in sheet


def test_rule_can_show_note_on_card():
    rules = parse_rules("show notes\n")
    doc = cards.single_card_document(contact(), rules, "wallet")
    assert "keep this private please" in doc


def test_sheet_pads_to_full_grid():
    # wallet is 2x4 -> one contact must yield 8 card cells
    sheet = cards.sheet_document([contact()], Rules.defaults(), "wallet")
    assert sheet.count('class="card wallet"') == 8
    # pocket is 2x5 -> 10 cells
    sheet = cards.sheet_document([contact()], Rules.defaults(), "pocket")
    assert sheet.count('class="card pocket"') == 10


def test_sheet_copies_and_counts():
    people = [contact(given="A"), contact(given="B"), contact(given="C")]
    sheet = cards.sheet_document(people, Rules.defaults(), "wallet", copies=2)
    # 3 people x 2 copies = 6 real cards, padded to 8
    for name in ("A Asdale", "B Asdale", "C Asdale"):
        assert sheet.count(name) >= 2


def test_sheet_html_escapes_names():
    tricky = Contact(given="Ada <&>", family='Lovelace"quote')
    doc = cards.single_card_document(tricky, Rules.defaults(), "wallet")
    assert "Ada <&>" not in doc
    assert "&lt;&amp;&gt;" in doc


def test_copies_must_be_positive():
    with pytest.raises(ValueError):
        cards.sheet_document([contact()], Rules.defaults(), "wallet", copies=0)


def test_unknown_size_raises():
    with pytest.raises(ValueError):
        cards.single_card_document(contact(), Rules.defaults(), "postage-stamp")
