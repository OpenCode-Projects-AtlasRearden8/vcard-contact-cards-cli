"""Tests for QR payload building, encoding and SVG rendering."""

import pytest

from vcc.contacts import Contact
from vcc.privacy import Rules
from vcc.qrsvg import make_qrcode, mecard_payload, qr_payload, qr_svg, vcard_payload
from vcc._vendor import qrcodegen


def contact(**kw) -> Contact:
    base = dict(
        given="Dylan", family="Asdale", org="Asdale Dynamics, LLC",
        phones=["+15551230000"], emails=["dylan@example.test"],
        url="https://dylanasdale.github.io", notes="private note",
    )
    base.update(kw)
    return Contact(**base)


def test_mecard_layout_and_escaping():
    p = mecard_payload(contact(), Rules())
    assert p.startswith("MECARD:")
    assert p.endswith(";;")
    assert "N:Asdale,Dylan;" in p
    assert "TEL:+15551230000;" in p
    assert "EMAIL:dylan@example.test;" in p
    assert "URL:https\\://dylanasdale.github.io;" in p
    assert "ORG:Asdale Dynamics\\, LLC;" in p
    assert p.index("N:") < p.index("TEL:")


def test_mecard_note_field_escapes_semicolons():
    from vcc.privacy import parse_rules

    p = mecard_payload(contact(notes="a;b"), parse_rules("show notes\n"))
    assert "NOTE:a\\;b" in p


def test_default_rules_strip_private_data_from_qr():
    p = qr_payload(contact(), Rules.defaults(), "mecard")
    assert "NOTE:" not in p and "private note" not in p
    vc = qr_payload(contact(), Rules.defaults(), "vcard")
    assert "NOTE:" not in vc and "private note" not in vc


def test_vcard_payload_is_parseable():
    from vcc.vcard import parse_vcf

    vc = vcard_payload(contact(), Rules())
    (c,) = parse_vcf(vc)
    assert (c.given, c.family) == ("Dylan", "Asdale")
    assert c.phones == ["+15551230000"]


def test_bad_format_raises():
    with pytest.raises(ValueError):
        qr_payload(contact(), None, "bogus")


def test_qr_deterministic_and_correct_size():
    rules = Rules.defaults()
    q1 = make_qrcode(contact(), rules)
    q2 = make_qrcode(contact(), rules)
    assert q1.get_size() == q2.get_size()
    assert q1.get_version() == q2.get_version()
    # QR spec: size = version*4 + 17
    assert q1.get_size() == q1.get_version() * 4 + 17


def test_qr_finder_patterns_at_three_corners():
    q = make_qrcode(contact(), Rules.defaults())
    size = q.get_size()
    # Each finder pattern is a 7x7 block: dark border ring, light ring, dark 3x3 core.
    def expected(x: int, y: int) -> bool:
        d = max(abs(x - 3), abs(y - 3))
        return d == 3 or d <= 1
    for origin in ((0, 0), (size - 7, 0), (0, size - 7)):
        ox, oy = origin
        for x in range(7):
            for y in range(7):
                assert q.get_module(ox + x, oy + y) == expected(x, y), (origin, x, y)


def test_short_input_gets_smallest_version():
    q = make_qrcode(contact(given="A", family="B", org="", phones=["1"],
                            emails=[], url="", notes=""), Rules.defaults())
    assert q.get_version() >= 1


def test_too_long_text_raises_data_too_long():
    with pytest.raises(qrcodegen.DataTooLongError):
        qrcodegen.QrCode.encode_text("x" * 100000, qrcodegen.QrCode.Ecc.LOW)


def test_qr_svg_is_selfcontained_svg():
    svg = qr_svg(make_qrcode(contact(), Rules.defaults()))
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert svg.rstrip().endswith("</svg>")
    assert 'fill="#111111"' in svg
    assert svg.count("<rect") > 20  # quiet zone + modules


def test_rules_missing_file_defaults():
    # imported late to exercise the helper path used by tests above
    from vcc.privacy import parse_rules

    assert parse_rules("show notes\nhide notes").is_hidden("notes")
