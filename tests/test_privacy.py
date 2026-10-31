"""Tests for the plain-text privacy rules engine."""

import pytest

from vcc.contacts import Contact
from vcc.privacy import DEFAULT_RULES, Rules, RulesError, parse_rules


def test_default_rules_hide_notes_only():
    r = Rules.defaults()
    assert r.is_hidden("notes")
    assert not r.is_hidden("birthday")
    assert not r.is_hidden("address")
    assert not r.is_hidden("phone")


def test_default_rules_text_is_what_ships():
    assert parse_rules(DEFAULT_RULES).is_hidden("notes")
    assert len(DEFAULT_RULES.strip().splitlines()) == 1


def test_later_lines_override_earlier():
    r = parse_rules("hide notes\nhide birthday\nshow notes\n")
    assert not r.is_hidden("notes")
    assert r.is_hidden("birthday")


def test_rules_apply_to_contact_accessors():
    r = parse_rules("hide notes\nhide phone\n")
    c = Contact(given="A", phones=["+1"], notes="secret")
    assert r.visible_value("notes", c.notes) == ""
    assert r.visible_phones(c.phones) == []
    r2 = parse_rules("show notes\n")
    assert r2.visible_value("notes", c.notes) == "secret"


def test_aliases_and_comments():
    r = parse_rules(
        "# this file is plain text\n"
        "\n"
        "hide tel\n"
        "hide emails\n"
    )
    assert r.is_hidden("phone")
    assert r.is_hidden("email")


def test_unknown_field_raises_with_line_number():
    with pytest.raises(RulesError) as exc:
        parse_rules("show notes\nhide ssn\n")
    assert "line 2" in str(exc.value)


def test_malformed_line_raises():
    with pytest.raises(RulesError):
        parse_rules("notes hide\n")
    with pytest.raises(RulesError):
        parse_rules("bananas")


def test_describe_and_to_text_roundtrip():
    r = parse_rules("hide notes\nhide birthday\n")
    reparsed = parse_rules(r.describe())
    assert reparsed.hidden == r.hidden
    assert Rules.defaults().to_text() == DEFAULT_RULES
