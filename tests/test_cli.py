"""End-to-end CLI tests using an isolated store."""

import pytest

from vcc import cli


@pytest.fixture()
def env(tmp_path, monkeypatch):
    store = tmp_path / "store"
    monkeypatch.delenv("VCC_STORE", raising=False)

    def run(*argv):
        return cli.main(["--store", str(store), *argv])

    out = type("Env", (), {})()
    out.path = store
    out.run = run
    return out


def test_init_add_list_export_flow(tmp_path, env):
    assert env.run("init") == 0
    assert (env.path / "contacts.json").exists()
    assert (env.path / "privacy.rules").exists()  # default rules written

    assert env.run("add", "--given", "Dylan", "--family", "Asdale",
                   "--org", "Asdale Dynamics, LLC", "--phone", "+15551230000",
                   "--email", "dylan@example.test", "--notes", "private note") == 0

    outvcf = tmp_path / "out.vcf"
    assert env.run("export", "--out", str(outvcf)) == 0
    text = outvcf.read_text(encoding="utf-8")
    assert "BEGIN:VCARD" in text and "N:Asdale;Dylan;;;" in text
    assert "private note" not in text  # privacy default


def test_import_csv_then_export_vcf(tmp_path, env):
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("First,Last,Phone,Email\nAda,Lovelace,+1 222,ada@x.test\n",
                        encoding="utf-8")
    assert env.run("init") == 0
    assert env.run("import", str(csv_path)) == 0

    outvcf = tmp_path / "ada.vcf"
    assert env.run("export", "--contacts", "Ada", "--out", str(outvcf)) == 0
    text = outvcf.read_text(encoding="utf-8")
    assert "N:Lovelace;Ada;;;" in text
    assert "+1 222" in text


def test_import_skips_duplicates(tmp_path, env):
    csv1 = tmp_path / "a.csv"
    csv1.write_text("First,Last\nAda,Lovelace\n", encoding="utf-8")
    env.run("init")
    env.run("import", str(csv1))
    # same file again: duplicate skipped (add idempotent), still one contact
    env.run("import", str(csv1))
    ids = [c.id for c in _load_store(env.path)]
    assert len(ids) == 1


def test_card_and_sheet_commands(tmp_path, env):
    env.run("init")
    env.run("add", "--given", "Dylan", "--family", "Asdale", "--phone", "+1555")
    card = tmp_path / "card.html"
    sheet = tmp_path / "sheet.html"
    assert env.run("card", "Dylan", "--size", "pocket", "--out", str(card)) == 0
    assert env.run("sheet", "--size", "wallet", "--out", str(sheet)) == 0
    card_text = card.read_text(encoding="utf-8")
    sheet_text = sheet.read_text(encoding="utf-8")
    assert "<svg" in card_text and "Dylan Asdale" in card_text
    assert sheet_text.count('class="card wallet"') == 8  # full 2x4 grid


def test_privacy_show_and_reset(env, capsys):
    env.run("init")
    assert env.run("privacy", "show") == 0
    captured = capsys.readouterr()
    assert "notes" in captured.out and "Hidden" in captured.out
    assert env.run("privacy", "reset") == 0
    rules_text = (env.path / "privacy.rules").read_text(encoding="utf-8")
    assert "hide notes" in rules_text


def test_custom_rules_hide_phone(env, tmp_path, capsys):
    env.run("init")
    env.run("add", "--given", "S", "--family", "P", "--phone", "+1555")

    (env.path / "privacy.rules").write_text(
        "hide phone\n" + "show notes\n", encoding="utf-8"
    )
    capsys.readouterr()
    assert env.run("privacy", "show") == 0
    assert "phone" in capsys.readouterr().out

    outvcf = tmp_path / "s.vcf"
    assert env.run("export", "--out", str(outvcf)) == 0
    text = outvcf.read_text(encoding="utf-8")
    assert "TEL" not in text and "BEGIN:VCARD" in text


def test_bad_rules_file_fails_cleanly(env, tmp_path, capsys):
    env.run("init")
    env.run("add", "--given", "X", "--family", "Y")
    (env.path / "privacy.rules").write_text("hide ssn\n", encoding="utf-8")
    capsys.readouterr()
    assert env.run("export") == 2
    assert "ssn" in capsys.readouterr().err


def test_show_and_rm(env, capsys):
    env.run("init")
    env.run("add", "--given", "Temp", "--family", "Person")
    ids = [c.id for c in _load_store(env.path)]
    assert env.run("show", ids[0]) == 0
    assert '"given": "Temp"' in capsys.readouterr().out
    assert env.run("rm", ids[0]) == 0
    assert _load_store(env.path) == []


def _load_store(store_path):
    from vcc.contacts import Store

    return Store(str(store_path)).load()


def test_qr_command_output(env, capsys):
    env.run("init")
    env.run("add", "--given", "D", "--family", "A", "--phone", "+1555",
            "--notes", "secret")
    capsys.readouterr()
    assert env.run("qr", "D", "--format", "mecard") == 0
    out = capsys.readouterr().out
    assert out.startswith("MECARD:") and "secret" not in out
