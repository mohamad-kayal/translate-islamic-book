"""Prep one Riyad al-Salihin episode for the translate-lecture Workflow.

    .venv/bin/python scratchpad/prep_episode.py <N>

Ingests episode N's captions (via URL) into runs/riyad-NN, writes a chapter-specific
DISPATCH.md folding in data/series/riyad.md, and prints a parseable RESULT line with the
block count the Workflow needs. Idempotent: re-running just refreshes DISPATCH and re-uses
an existing ingest unless --reingest is passed.
"""
import json
import os
import pathlib
import subprocess
import sys

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
ROOT = pathlib.Path("/Users/employee/Documents/SRT-translator")
TSV = ROOT / "scratchpad" / "riyad-playlist.tsv"

# Standard English renderings for the chapters visible in the playlist, so cross-episode
# renderings stay consistent from the first block (the live glossary reinforces them after).
CHAPTER_EN = {
    "باب الإخلاص والنية": "Sincerity and Intention (Bab al-Ikhlas wa'l-Niyyah)",
    "باب التوبة": "Repentance (Bab al-Tawbah)",
    "باب الصبر": "Patience (Bab al-Sabr)",
    "باب الصدق": "Truthfulness (Bab al-Sidq)",
    "باب المراقبة": "Watchfulness of God (Bab al-Muraqabah)",
    "باب التقوى": "God-consciousness (Bab al-Taqwa)",
    "باب اليقين والتوكل": "Certainty and Reliance on God (Bab al-Yaqin wa'l-Tawakkul)",
    "باب الاستقامة": "Steadfastness (Bab al-Istiqamah)",
    "باب التفكر": "Reflection (Bab al-Tafakkur)",
    "باب المبادرة إلى الخيرات": "Hastening to Good Deeds (Bab al-Mubadarah ila'l-Khayrat)",
    "باب المجاهدة": "Striving of the Soul (Bab al-Mujahadah)",
    "باب الحث على الازدياد من الخير في أواخر العمر": "Increasing in Good Late in Life (Bab al-Hathth 'ala'l-Izdiyad)",
    "باب في بيان كثرة طرق الخير": "The Many Paths of Good (Bab Kathrat Turuq al-Khayr)",
    "باب في الاقتصاد في العبادة": "Moderation in Worship (Bab al-Iqtisad fi'l-'Ibadah)",
    "باب في المحافظة على الأعمال": "Constancy in Deeds (Bab al-Muhafazah 'ala'l-A'mal)",
    "باب في الأمر بالمحافظة على السنة وآدابها": "Adhering to the Sunnah (Bab al-Muhafazah 'ala'l-Sunnah)",
    "باب في وجوب الانقياد لحكم الله": "Submitting to God's Ruling (Bab Wujub al-Inqiyad)",
    "باب في النهي عن البدع ومحدثات الأمور": "Forbidding Innovation (Bab al-Nahy 'an al-Bid'a)",
    "باب في الدلالة على خير": "Guiding to Good (Bab al-Dalalah 'ala Khayr)",
    "باب في التعاون على البر والتقوى": "Cooperating in Righteousness (Bab al-Ta'awun 'ala'l-Birr)",
    "باب في النصيحة": "Sincere Counsel (Bab al-Nasihah)",
    "باب في الأمر بالمعروف والنهي عن المنكر": "Enjoining Good and Forbidding Evil (Bab al-Amr bi'l-Ma'ruf)",
    "باب تغليظ عقوبة من خالف قوله فعله": "Whose Deeds Belie His Words (Bab Taghliz 'Uqubat man Khalafa)",
    "باب الأمر بأداء الأمانة": "Discharging Trusts (Bab Ada' al-Amanah)",
    "باب تحريم الظلم والأمر برد المظالم": "Forbidding Wrongdoing (Bab Tahrim al-Zulm)",
    "باب تعظيم حرمات المسلمين وبيان حقوقهم": "Honoring the Rights of Muslims (Bab Ta'zim Hurumat al-Muslimin)",
    "باب ستر عورات المسلمين": "Concealing Muslims' Faults (Bab Satr 'Awrat al-Muslimin)",
    "باب قضاء حوائج المسلمين": "Meeting Muslims' Needs (Bab Qada' Hawa'ij al-Muslimin)",
    "باب الشفاعة": "Intercession (Bab al-Shafa'ah)",
    "باب الإصلاح بين الناس": "Reconciling People (Bab al-Islah bayn al-Nas)",
    "باب فضل ضعفة المسلمين": "The Virtue of the Weak (Bab Fadl Du'afa' al-Muslimin)",
}


def parse_rows():
    rows = {}
    for line in TSV.read_text(encoding="utf-8").splitlines():
        sep = "\t" if "\t" in line else "\\t"  # yt-dlp --print emits a literal \t
        idx, vid, title = line.split(sep, 2)
        rows[int(idx)] = (vid, title)
    return rows


def chapter_of(title):
    parts = [p.strip() for p in title.split("|")]
    raw = parts[1] if len(parts) > 1 else ""
    # strip a trailing part number ("باب الصبر 3" -> base "باب الصبر", part "3")
    base, part = raw, ""
    toks = raw.split()
    if toks and toks[-1].isdigit():
        base, part = " ".join(toks[:-1]), toks[-1]
    return raw, base, part


def dispatch_text(n, raw_chapter, base_chapter, part, en_hint):
    part_note = f" (part {part})" if part else ""
    en_line = (f'render as "the chapter on {en_hint}"; short form after first use.'
               if en_hint else
               'render as "the chapter on X (Bab …)" per the series convention; reuse the '
               'glossary rendering if one already exists.')
    return f"""# DISPATCH — riyad-{n:02d} ({raw_chapter}{part_note})

Series: **أنوار السنة المحمدية | رياض الصالحين** — Ahmad al-Sayyid's hadith-by-hadith
commentary on Imam al-Nawawi's *Riyad al-Salihin*. This episode: {raw_chapter}{part_note}.

## Conventions binding for this run

- **The book:** رياض الصالحين → "Riyad al-Salihin (The Gardens of the Righteous)" first use,
  "Riyad al-Salihin" after. Author: **Imam al-Nawawi**.
- **Series title:** أنوار السنة المحمدية → "The Lights of the Muhammadan Sunnah
  (Anwar al-Sunnah al-Muhammadiyyah)".
- **This chapter:** {base_chapter} → {en_line}
- **Scripture is dense — retrieval is the whole game.** Every verse al-Nawawi cites under the
  chapter → `quran_lookup`; every hadith matn → `hadith_lookup`. NEVER write a verse or matn
  from memory. Cite each hadith by its ORIGINAL collection (متفق عليه = Bukhari & Muslim;
  رواه البخاري / رواه مسلم / …), not by a Riyad al-Salihin number.
- **Session openings** are the khutbat al-hajah (praise + salawat) — formulaic prose; retrieve
  only an actually-recited verse inside it.
- **Honorifics:** ﷺ always kept; (AS) / (RA) as the speaker says them. **Numbers:** digits.

The GLOSSARY subset + any PROVISIONAL renderings are injected per block by `block_brief show`.
Reuse them exactly. Report genuinely new recurring terms/names/works in `new_terms`.
"""


def main():
    n = int(sys.argv[1])
    reingest = "--reingest" in sys.argv[2:]
    rows = parse_rows()
    if n not in rows:
        raise SystemExit(f"episode {n} not in playlist TSV")
    vid, title = rows[n]
    raw_chapter, base_chapter, part = chapter_of(title)
    en_hint = CHAPTER_EN.get(base_chapter)
    slug = f"riyad-{n:02d}"
    run = ROOT / "runs" / slug
    work = run / "work"
    blocks_json = work / "blocks.json"

    if reingest or not blocks_json.exists():
        url = f"https://www.youtube.com/watch?v={vid}"
        subprocess.run(
            [sys.executable, "-m", "scripts.ingest_video", url, "--run", f"runs/{slug}"],
            cwd=ROOT, check=True)

    work.mkdir(parents=True, exist_ok=True)
    (work / "DISPATCH.md").write_text(
        dispatch_text(n, raw_chapter, base_chapter, part, en_hint), encoding="utf-8")

    nblocks = len(json.loads(blocks_json.read_text(encoding="utf-8"))["blocks"])
    print(f"RESULT slug={slug} vid={vid} blocks={nblocks} chapter={base_chapter!r} "
          f"en_hint={'yes' if en_hint else 'NONE'}")


if __name__ == "__main__":
    main()
