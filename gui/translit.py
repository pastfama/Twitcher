"""Latin→Cyrillic transliteration for Twitch chat.

Maps Latin-letter chat spellings to Cyrillic in real time as the
user types (keystroke-by-keystroke), matching the translit.ru
"Основной" (Basic) standard.

Reference: https://translit.ru — Основной (default) layout.
"""

# Mapping: latin chunk -> cyrillic. Order matters (longest first).
# Matches translit.ru "Основной" standard exactly.
_MAP = [
    ("shch", "щ"),
    ("zh", "ж"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("yo", "ё"),
    ("jj", "й"),
    ("je", "э"),
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
    ("x", "х"),
    ("c", "ц"),
    ("w", "в"),
    ("q", "я"),
    ("y", "ы"),
    ("'", "ь"),
    ("ä", "э"),
    ("ü", "ю"),
    ("ö", "ё"),
]


def translit(text: str) -> str:
    """Convert Latin transliteration to Cyrillic text."""
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