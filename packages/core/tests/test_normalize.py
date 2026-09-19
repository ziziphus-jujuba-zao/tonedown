from tonedown.normalize import for_matching, normalize


def test_zero_width_and_fullwidth_are_removed():
    assert normalize("ｓ\u200bｂ") == "sb"


def test_greek_lookalike_in_chinese_text_maps_to_latin():
    assert normalize("主播傻β一个") == "主播傻b一个"


def test_real_greek_text_is_left_alone():
    assert normalize("καλημέρα") == "καλημέρα"


def test_cyrillic_lookalikes_inside_latin_words_are_mapped():
    assert normalize("idiоt") == "idiot"  # the о is Cyrillic


def test_long_repeats_are_collapsed():
    assert normalize("哈哈哈哈哈哈") == "哈哈哈"


def test_for_matching_strips_separators():
    assert for_matching("傻.逼 n m s l") == "傻逼nmsl"
