from retrieval.normalize import normalize_arabic, tokenize


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
