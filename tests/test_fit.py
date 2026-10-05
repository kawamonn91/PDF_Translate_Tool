from ja_translator.fit import fit_text, text_height, wrap


def fixed(text: str, size: float) -> float:
    """1文字 = 1em の単純な計測(日本語の全角幅を想定)"""
    return len(text) * size


def test_wrap_breaks_japanese_by_width():
    lines = wrap("あいうえおかきくけこ", width=50, size=10, measure=fixed)
    assert lines == ["あいうえお", "かきくけこ"]


def test_closing_punctuation_never_starts_a_line():
    lines = wrap("あいうえお。かきくけこ", width=50, size=10, measure=fixed)
    assert all(not line.startswith("。") for line in lines)


def test_ascii_words_are_not_split_when_they_fit():
    half_width = lambda t, s: len(t) * s * 0.5
    lines = wrap("Revenue grew twelve", width=40, size=10, measure=half_width)
    assert lines == ["Revenue", "grew", "twelve"]


def test_newline_forces_a_break():
    assert wrap("一行目\n二行目", width=500, size=10, measure=fixed) == ["一行目", "二行目"]


def test_short_text_keeps_original_size():
    result = fit_text("短い", box_width=100, box_height=30, base_size=12, measure=fixed)
    assert result.fits
    assert result.scale == 1.0
    assert result.font_size == 12


def test_long_text_shrinks_until_it_fits():
    text = "これは枠に収めるためにサイズを下げる必要がある長めの文章です"
    result = fit_text(text, box_width=120, box_height=40, base_size=12, measure=fixed)
    assert result.fits
    assert result.font_size < 12
    assert text_height(len(result.lines), result.font_size) <= 40.01


def test_text_that_cannot_fit_is_reported():
    text = "とても長い文章です。" * 40
    result = fit_text(text, box_width=50, box_height=10, base_size=12, measure=fixed)
    assert not result.fits
    assert result.scale == 0.55
