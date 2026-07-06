from retrieval.normalize import fix_kfgqpc_spaces, normalize_arabic, tokenize


def test_strips_tashkeel():
    # مُحَمَّدٌ with harakat must reduce to bare محمد
    voweled = "مُحَمَّدٌ"
    assert normalize_arabic(voweled) == "محمد"


def test_unifies_alef_variants():
    # إِنَّ ٱللَّه (hamza-below alef + wasla alef) == bare ان الله
    voweled = "إنَّ ٱلله"
    assert normalize_arabic(voweled) == normalize_arabic("ان الله") == "ان الله"


def test_unifies_alef_maqsura_and_ta_marbuta():
    assert normalize_arabic("على") == "علي"      # ى -> ي
    assert normalize_arabic("رحمة") == "رحمه"     # ة -> ه


def test_drops_symbols_digits_tatweel():
    # U+06DD end-of-ayah sign + Arabic-Indic digit ٢ + tatweel all vanish
    assert normalize_arabic("الحمد ۝٢ لله") == "الحمد لله"
    assert normalize_arabic("مــحمد") == "محمد"


def test_superscript_alef_removed():
    # هٰذا (with dagger alef U+0670) -> هذا
    assert normalize_arabic("هٰذا") == "هذا"


def test_empty_and_none_safe():
    assert normalize_arabic("") == ""
    assert normalize_arabic(None) == ""
    assert tokenize("بحر   نهر") == ["بحر", "نهر"]


def test_kfgqpc_space_before_silent_alef_removed():
    # KFGQPC Hafs text writes open tanween + SPACE + silent alef (صِدِّيقࣰ ا);
    # the space must go so the alef stays joined to its word in any standard font.
    assert fix_kfgqpc_spaces("صِدِّيقࣰ ا نَّبِيًّا") == "صِدِّيقࣰا نَّبِيًّا"


def test_kfgqpc_space_before_silent_alef_maqsura_removed():
    # 2:2 هُدࣰ ى -> هُدࣰى
    assert fix_kfgqpc_spaces("هُدࣰ ى لِّلۡمُتَّقِينَ") == "هُدࣰى لِّلۡمُتَّقِينَ"


def test_kfgqpc_open_dammatan_before_silent_alef_removed():
    # 44:33 بَلَٰٓؤࣱ ا۟ -> the silent alef rejoins even with a following annotation mark
    assert fix_kfgqpc_spaces("بَلَٰٓؤࣱ ا۟") == "بَلَٰٓؤࣱا۟"


def test_kfgqpc_space_removed_when_marks_follow_the_tanween():
    # the mark cluster may continue AFTER the open tanween: 19:44 عَصِيࣰّ ا has
    # shadda after it; 2:48 شَيۡـࣰٔ ا has hamza-above after it. Both must rejoin.
    assert fix_kfgqpc_spaces("عَصِيࣰّ ا") == "عَصِيࣰّا"
    assert fix_kfgqpc_spaces("شَيۡـࣰٔ ا") == "شَيۡـࣰٔا"


def test_kfgqpc_word_boundaries_kept():
    # after open tanween a REAL next word starts with a voweled letter -> space stays
    assert fix_kfgqpc_spaces("ظُلُمَٰتࣱ وَرَعۡدࣱ") == "ظُلُمَٰتࣱ وَرَعۡدࣱ"
    assert fix_kfgqpc_spaces("كَصَيِّبࣲ مِّنَ ٱلسَّمَآءِ") == "كَصَيِّبࣲ مِّنَ ٱلسَّمَآءِ"
