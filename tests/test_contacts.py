"""Tests for the contact model and JSON store."""

import json

import pytest

from vcc.contacts import Contact, Store, new_id


def test_full_name_and_display_name():
    c = Contact(given="Dylan", family="Asdale")
    assert c.full_name() == "Dylan Asdale"
    assert c.display_name() == "Dylan Asdale"
    org_only = Contact(org="Asdale Dynamics, LLC")
    assert org_only.display_name() == "Asdale Dynamics, LLC"
    assert Contact().display_name() == "(unnamed)"


def test_validation_rejects_bad_types():
    c = Contact(given="A", phones={"not": "a list"})
    with pytest.raises(ValueError):
        c.validate()
    c2 = Contact(given="A", notes=7)
    with pytest.raises(ValueError):
        c2.validate()


def test_nonempty_lists_only_populated_fields():
    c = Contact(given="Dylan", phones=["+15551230000"], emails=[], notes="")
    d = c.nonempty()
    assert d == {"given": "Dylan", "phones": ["+15551230000"]}


def test_store_add_load_roundtrip(tmp_path):
    store = Store(str(tmp_path))
    store.ensure()
    c = Contact(given="Dylan", family="Asdale", org="Asdale Dynamics, LLC",
                phones=["+15551230000"], notes="private note")
    saved = store.add(c)
    assert saved.id
    again = Store(str(tmp_path)).load()
    assert len(again) == 1
    assert again[0].given == "Dylan"
    assert again[0].phones == ["+15551230000"]


def test_store_file_is_plain_json(tmp_path):
    store = Store(str(tmp_path))
    store.add(Contact(given="A", family="B"))
    with open(store.path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["version"] == 1
    assert {"given", "family"} <= set(data["contacts"][0])


def test_find_by_id_and_by_name(tmp_path):
    store = Store(str(tmp_path))
    c = store.add(Contact(given="Unique", family="Query"))
    assert store.find(c.id).given == "Unique"
    assert store.find("unique qu").given == "Unique"
    assert store.find("nobody") is None


def test_remove(tmp_path):
    store = Store(str(tmp_path))
    c = store.add(Contact(given="Gone", family="Soon"))
    assert store.remove(c.id) is True
    assert store.remove("nope") is False
    assert store.load() == []


def test_ids_are_unique(tmp_path):
    store = Store(str(tmp_path))
    a = store.add(Contact(given="A"))
    b = store.add(Contact(given="B"))
    assert a.id != b.id
    assert len(new_id()) == 8
