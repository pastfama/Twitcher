"""Latin → Cyrillic transliteration for Twitch chat.

Converts Latin-script messages (e.g. "privet") into Cyrillic
("привет") so Russian-speaking users can type in Latin and have
their messages appear in Cyrillic.
"""


def match_case(source: str, replacement: str) -> str:
    """Match the case of *source* when applying *replacement*."""
    if source.isupper():
        return replacement.upper()
    if source[0].isupper():
        return replacement.upper()
    return replacement


def transliterate_to_russian(text: str) -> str:
    """Transliterate Latin text to Cyrillic.

    Handles common digraphs (shch→щ, yo→ё, yu→ю, ya→я, zh→ж,
    kh→х, ts→ц, ch→ч, sh→ш, ye→е) and single-letter mappings.
    """
    if not text:
        return ""

    combos = [
        ("shch", "щ"),
        ("yo", "ё"),
        ("yu", "ю"),
        ("ya", "я"),
        ("zh", "ж"),
        ("kh", "х"),
        ("ts", "ц"),
        ("ch", "ч"),
        ("sh", "ш"),
        ("ye", "е"),
    ]

    letters = {
        "a": "а",
        "b": "б",
        "v": "в",
        "g": "г",
        "d": "д",
        "e": "е",
        "z": "з",
        "i": "и",
        "j": "й",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "o": "о",
        "p": "п",
        "r": "р",
        "s": "с",
        "t": "т",
        "u": "у",
        "f": "ф",
        "h": "х",
        "c": "ц",
        "y": "ы",
        "q": "к",
        "w": "в",
        "x": "кс",
        '"': "ь",
        "'": "ь",
        "`": "ъ",
    }

    result = ""
    index = 0
    length = len(text)

    while index < length:
        chunk = None
        for latin, cyrillic in combos:
            segment = text[index:index + len(latin)]
            if segment.lower() == latin:
                chunk = match_case(segment, cyrillic)
                index += len(latin)
                break

        if chunk is not None:
            result += chunk
            continue

        char = text[index]
        lower = char.lower()
        if lower in letters:
            result += match_case(char, letters[lower])
        else:
            result += char
        index += 1

    return result