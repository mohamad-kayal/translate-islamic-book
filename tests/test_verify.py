from out.verify import parse_markers, verify

GOOD = (
    "intro\n"
    "<!--quran s=4 a=59-59 tr=saheeh-->\n(...) [An-Nisa: 59]\n<!--/quran-->\n"
    "<!--hadith coll=bukhari num=79 conf=1.0 src=dataset-->\n[[H]] ... <!--/hadith-->\n"
)


def test_parse_counts():
    m = parse_markers(GOOD)
    assert len(m["quran"]) == 1 and len(m["hadith"]) == 1
    assert m["quran"][0]["s"] == "4" and m["hadith"][0]["coll"] == "bukhari"


def test_clean_report_has_no_problems():
    r = verify(GOOD)
    assert r["n_quran"] == 1 and r["n_hadith"] == 1
    assert r["problems"] == [] and r["flagged"] == []


def test_flags_low_confidence_and_fallback():
    md = "<!--hadith coll=ahmad num=23482 conf=0.4 src=fallback-->x<!--/hadith-->"
    r = verify(md)
    assert any("review" in f.lower() or "fallback" in f.lower() or "confidence" in f.lower()
               for f in r["flagged"])


def test_problems_on_bad_surah():
    md = "<!--quran s=200 a=1-1 tr=saheeh-->x<!--/quran-->"
    r = verify(md)
    assert any("surah" in p.lower() for p in r["problems"])
