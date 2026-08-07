"""Latin→Cyrillic transliteration for Twitch chat.

Maps common Latin-letter chat spellings to Cyrillic in real time as the
user types (keystroke-by-keystroke), matching the behaviour of the
original Qt TRANSLIT button.
"""

# Mapping: latin chunk -> cyrillic. Order matters (longest first).
_MAP = [
    ("shch", "щ"),
    ("zh", "ж"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("yo", "ё"),
    ("je", "э"),
    ("ii", "й"),
    ("a", "а"),
    ("b", "б"),
    ("v", "в"),
    ("g", "г"),
    ("d", "д"),
    ("e", "е"),
    ("z", "з"),
    ("i", "и"),
    ("j", "й"),
    ("k", "к"),
    ("l", "л"),
    ("m", "м"),
    ("n", "н"),
    ("o", "о"),
    ("p", "п"),
    ("r", "р"),
    ("s", "с"),
    ("t", "т"),
    ("u", "у"),
    ("f", "ф"),
    ("h", "х"),
    ("c", "ц"),
    ("w", "в"),
    ("x", "кс"),
    ("y", "ы"),
    ("'", "ь"),
]


def translit(text: str) -> str:
    out = text.lower()
    for latin, cyr in _MAP:
        if not latin:
            continue
        out = out.replace(latin, cyr)
    return out


def on_key_insert(current: str, inserted: str, index: int) -> str:
    """Return the new text after inserting *inserted* chars at *index*
    inside *current*, transliterated.
    """
    new = current[:index] + inserted + current[index:]
    return translit(new)

