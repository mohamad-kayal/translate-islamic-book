import os

import pytest

pytestmark = pytest.mark.integration
DATA = os.environ.get("RETRIEVAL_DATA_DIR",
                      os.path.join(os.path.dirname(__file__), "..", "data"))


def _need(path):
    if not os.path.exists(path):
        pytest.skip("run scripts/setup_data.py first (%s missing)" % path)


def test_quran_annisa_59_partial_quote():
    # The source quotes only the second half of An-Nisa 59 -> mid-ayah match must work.
    _need(os.path.join(DATA, "quran", "eng-ummmuhammad.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("فإن تنازعتم في شيء فردوه إلى الله والرسول")
    assert r["matched"] and r["surah"] == 4 and r["ayah_start"] == 59
    assert r["ref_en"] == "[An-Nisa: 59]"
    assert "refer it to Allah and the Messenger" in r["english_saheeh"]


def test_quran_multiayah_range_ashshura_52_53():
    _need(os.path.join(DATA, "quran", "ara-quranuthmanihaf.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("وإنك لتهدي إلى صراط مستقيم صراط الله الذي له ما في السماوات وما في الأرض")
    assert r["matched"] and r["surah"] == 42
    assert (r["ayah_start"], r["ayah_end"]) == (52, 53)


def test_hadith_bukhari_79_rain_parable():
    _need(os.path.join(DATA, "hadith", "ara-bukhari.json"))
    from retrieval.hadith_lookup import match
    r = match("مثل ما بعثني الله به من الهدى والعلم كمثل الغيث الكثير أصاب أرضا")
    assert r.get("collection") == "bukhari" and r.get("number") == 79
    assert "guidance" in r["english"].lower()
