import pytest
from tonedown.langdetect import detect


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("这集节奏太好了", "zh"),
        ("この回、テンポが良くて最高だった", "ja"),
        ("이번 화 진짜 재밌었다", "ko"),
        ("Отличная серия", "ru"),
        ("حلقة رائعة", "ar"),
        ("क्या शानदार एपिसोड", "hi"),
        ("Tập này hay quá", "vi"),
        ("The pacing of this episode is great", "en"),
        ("Qué buen episodio, por fin mejora el ritmo", "es"),
        ("Der Ersteller ist ein Idiot", "de"),
    ],
)
def test_detect(text, lang):
    assert detect(text)[0] == lang


def test_no_letters_is_undetermined():
    assert detect("!!! 123 ???") == ("und", 0.0)
