import json

import pytest

from scripts import post as P
from scripts.post import LIMITS, check, split_thread, to_plain_text


class _Hadith:
    def get(self, coll, num):
        return {("bukhari", "1"): {"english": "Narrated Umar: deeds depend on intentions.",
                                   "arabic": "إنما الأعمال بالنيات"}}.get((coll, str(num)))


class _Quran:
    def get_verse(self, s, a):
        return {"arabic": "بحر نهر", "saheeh": "sea river", "clear": "x"} if (s, a) == (1, 1) else None


QURAN = '<!--quran s=1 a=1-1 tr=saheeh-->\nبحر نهر [الفاتحة: ١]\n"sea river" [Al-Fatihah: 1]\n<!--/quran-->'
GOOD_H = ('<!--hadith coll=bukhari num=1 conf=1.0 src=dataset-->\n«إنما الأعمال بالنيات»\n'
          '"deeds depend on intentions" (Narrated by al-Bukhari)\n<!--/hadith-->')
OWN_H = ('<!--hadith coll=hakim num=0 conf=0 src=fallback-->\n«قول»\n'
         '"my own words" (Narrated by al-Hakim)\n<!--/hadith-->')


def _run(tmp_path, md, source="قال قولا"):
    run = tmp_path / "runs" / "p1"
    (run / "work").mkdir(parents=True)
    (run / "source.txt").write_text(source, encoding="utf-8")
    (run / "work" / "post.md").write_text(md, encoding="utf-8")
    return run


def test_plain_text_drops_markers_and_arabic_by_default():
    text = to_plain_text("Reflect on this:\n\n" + QURAN, _Hadith())
    assert '"sea river" [Al-Fatihah: 1]' in text
    assert "<!--" not in text and "بحر" not in text


def test_plain_text_can_keep_the_arabic():
    assert "بحر نهر [الفاتحة: ١]\n\"sea river\"" in to_plain_text(QURAN, _Hadith(), with_arabic=True)


def test_plain_text_strips_markup_and_keeps_line_breaks_and_hashtags():
    md = "## Title\n\nLine **one**\nLine *two* [كلمة]{lang=ar dir=rtl} #Sabr 🌿"
    assert to_plain_text(md, _Hadith()) == "Title\n\nLine one\nLine two كلمة #Sabr 🌿"


def test_verified_hadith_has_no_mark_and_no_foot_note():
    text = to_plain_text(GOOD_H, _Hadith())
    assert "†" not in text


def test_unverified_hadith_is_marked_and_explained():
    text = to_plain_text(OWN_H, _Hadith())
    assert '(Narrated by al-Hakim) †' in text
    assert text.endswith("† English is the translator's own rendering.")


def test_thread_parts_fit_and_lose_no_words():
    text = "\n\n".join(" ".join("word%d." % i for i in range(n, n + 60)) for n in (0, 60))
    parts = split_thread(text, LIMITS["x"])
    assert len(parts) > 1 and all(len(p) <= LIMITS["x"] for p in parts)
    assert parts[-1].endswith("%d/%d" % (len(parts), len(parts)))
    rejoined = " ".join(p.rsplit(" ", 1)[0] for p in parts).split()
    assert rejoined == text.split()


def test_thread_splits_a_sentence_longer_than_a_post():
    parts = split_thread("x" * 10 + " " + "y " * 400, LIMITS["x"])
    assert all(len(p) <= LIMITS["x"] for p in parts)


def test_check_passes_a_clean_post(tmp_path):
    run = _run(tmp_path, "Reflect:\n\n" + QURAN + "\n\n" + GOOD_H + "\n\nSo be mindful of it.")
    problems, notes = check(run, _Quran(), _Hadith())
    assert problems == []
    assert "'verified': 1" in notes[0]


def test_check_rejects_a_paraphrased_verse(tmp_path):
    run = _run(tmp_path, QURAN.replace("sea river", "the ocean and the stream"))
    assert any("English deviates" in p for p in check(run, _Quran(), _Hadith())[0])


def test_check_rejects_arabic_left_in_the_prose(tmp_path):
    run = _run(tmp_path, "Some words and then كلمة عربية")
    assert any("Arabic outside markers" in p for p in check(run, _Quran(), _Hadith())[0])


def test_check_rejects_book_placeholders(tmp_path):
    run = _run(tmp_path, "[[H]] words words words")
    assert any("[[H]]" in p for p in check(run, _Quran(), _Hadith())[0])


def test_check_catches_a_dropped_line(tmp_path):
    run = _run(tmp_path, "Too short.", source="كلمة " * 40)
    assert any("dropped" in p for p in check(run, _Quran(), _Hadith())[0])


def test_check_without_a_translation_says_so(tmp_path):
    run = tmp_path / "r"
    (run / "work").mkdir(parents=True)
    assert check(run, _Quran(), _Hadith())[0] == ["no work/post.md yet"]


def test_init_stores_source_and_narrows_the_glossary(tmp_path, monkeypatch):
    master = {"style": "s", "terms": {"التزكية": {"translit": "tazkiyah", "english": "e"},
                                      "الثغور": {"translit": "thughur", "english": "e"}},
              "names": {"موسى": "Musa", "نوح": "Nuh"}, "works": {}}
    path = tmp_path / "g.json"
    path.write_text(json.dumps(master, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(P, "MASTER", str(path))
    subset = P.init(tmp_path / "r", "عن تزكية النفس عند موسى")
    assert (tmp_path / "r" / "source.txt").read_text(encoding="utf-8").startswith("عن تزكية")
    assert list(subset["terms"]) == ["التزكية"] and list(subset["names"]) == ["موسى"]


def test_harvest_reads_a_posts_new_terms(tmp_path):
    from retrieval.glossary import harvest
    run = _run(tmp_path, "x")
    (run / "work" / "new_terms.json").write_text(json.dumps(
        [{"ar": "الورع", "translit": "wara'", "english": "scrupulous piety", "kind": "term"}],
        ensure_ascii=False), encoding="utf-8")
    master = tmp_path / "g.json"
    master.write_text('{"terms": {}, "names": {}}', encoding="utf-8")
    assert "الورع" in harvest(run, master, tmp_path / "log.md")["added"]


@pytest.mark.integration
def test_finish_end_to_end_on_the_real_datasets(tmp_path, monkeypatch):
    master = tmp_path / "g.json"
    master.write_text('{"terms": {}, "names": {}}', encoding="utf-8")
    monkeypatch.setattr(P, "MASTER", str(master))
    monkeypatch.setattr(P, "CHANGELOG", str(tmp_path / "log.md"))
    run = tmp_path / "p1"
    (run / "work").mkdir(parents=True)
    (run / "source.txt").write_text("قال الله تعالى: الحمد لله رب العالمين", encoding="utf-8")
    (run / "work" / "post.md").write_text(
        'Allah the Exalted said:\n\n<!--quran s=1 a=2-2 tr=saheeh-->\n'
        'ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَـٰلَمِينَ [الفاتحة: ٢]\n'
        '"[All] praise is [due] to Allah, Lord of the worlds" [Al-Fatihah: 2]\n<!--/quran-->\n',
        encoding="utf-8")
    problems, out = P.finish(run, platform="x")
    assert problems == []
    assert "Lord of the worlds" in out.read_text(encoding="utf-8")
    assert "Qur'an 1:2-2" in (run / "output" / "review.md").read_text(encoding="utf-8")
