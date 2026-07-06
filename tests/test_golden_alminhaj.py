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


def test_quran_arabic_has_no_intraword_spaces():
    # Maryam 41 (صديقًا نبيًّا): the KFGQPC dataset writes the silent alef after open
    # tanween as a separate space-delimited char, which visibly breaks the word in
    # rendered output. The index must serve display text with those spaces removed.
    _need(os.path.join(DATA, "quran", "ara-quranuthmanihaf.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("انه كان صديقا نبيا")
    assert r["matched"] and r["surah"] == 19 and r["ayah_start"] == 41
    assert "صِدِّيقࣰا" in r["arabic"]          # joined
    assert "ࣰ ا" not in r["arabic"]            # no tanween+space+alef anywhere


def test_quran_imlai_orthography_salah_class():
    # Modern (Imla'i) spelling الصلاة vs Uthmani الصلوٰة (silent waw + dagger alef):
    # books that quote in modern orthography must still match.
    _need(os.path.join(DATA, "quran", "ara-quranuthmanihaf.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("حافظوا على الصلوات والصلاة الوسطى وقوموا لله قانتين")
    assert r["matched"] and r["surah"] == 2 and r["ayah_start"] == 238


def test_quran_imlai_orthography_amanu_class():
    # Imla'i آمنوا vs Uthmani ءَامَنُوا (hamza + alef): must still match.
    _need(os.path.join(DATA, "quran", "ara-quranuthmanihaf.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("يا أيها الذين آمنوا كتب عليكم الصيام")
    assert r["matched"] and r["surah"] == 2 and r["ayah_start"] == 183


def test_quran_arabic_has_no_rlm_chars():
    _need(os.path.join(DATA, "quran", "ara-quranuthmanihaf.json"))
    from retrieval.quran_lookup import lookup
    r = lookup("انه كان صديقا نبيا")
    assert "‏" not in r["arabic"]


def test_hadith_bukhari_79_rain_parable():
    _need(os.path.join(DATA, "hadith", "ara-bukhari.json"))
    from retrieval.hadith_lookup import match
    r = match("مثل ما بعثني الله به من الهدى والعلم كمثل الغيث الكثير أصاب أرضا")
    assert r.get("collection") == "bukhari" and r.get("number") == 79
    assert "guidance" in r["english"].lower()
