import html
import requests

from logger import debug, info, warning, error


# ============================================================
#                    TOKEN HELPERS
# ============================================================


def normalize_token(

    token

):

    token = (

        token

        or ""

    ).strip()


    if token.lower().startswith(

        "oauth:"

    ):

        token = token[6:]


    return token


def load_twitch_token():

    try:

        token = get_valid_token()


        if not token:

            debug("")

            debug(

                "[CHAT] No valid Twitch access token available."

            )

            return ""


        return normalize_token(

            token

        )


    except Exception as error:

        debug("")

        debug(

            "[CHAT] Failed to obtain valid Twitch token:"

        )

        debug(

            error

        )

        return ""


# ============================================================
#                    TRANSLITERATION HELPERS
# ============================================================


def transliterate_to_russian(text):
    """Transliterate Latin text to Cyrillic using translit.ru standard."""
    if not text:
        return ""

    # Mapping: latin chunk -> cyrillic. Order matters (longest first).
    # Matches translit.ru "Основной" standard exactly.
    combos = [
        ("shch", "щ"),
        ("zh", "ж"),
        ("ch", "ч"),
        ("sh", "ш"),
        ("yu", "ю"),
        ("ya", "я"),
        ("yo", "ё"),
        ("jj", "й"),
        ("je", "э"),
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
        "x": "х",
        "c": "ц",
        "w": "в",
        "q": "я",
        "y": "ы",
        "'": "ь",
        "ä": "э",
        "ü": "ю",
        "ö": "ё",
    }


    def match_case(

        source,

        replacement

    ):

        if source.isupper():

            return replacement.upper()

        if source[0].isupper():

            return replacement.upper()

        return replacement


    result = ""

    index = 0

    length = len(text)


    while index < length:

        chunk = None

        for latin, cyrillic in combos:

            segment = text[index:index + len(latin)]

            if segment.lower() == latin:

                chunk = match_case(

                    segment,

                    cyrillic

                )

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



def get_token_identity(

    access_token

):

    access_token = normalize_token(

        access_token

    )


    if not access_token:

        raise RuntimeError(

            "Twitch access token is empty."

        )


    response = requests.get(

        "https://id.twitch.tv/oauth2/validate",

        headers={

            "Authorization":

            f"OAuth {access_token}"

        },

        timeout=20,

    )


    if response.status_code != 200:

        raise RuntimeError(

            "Twitch token validation failed.\n\n"

            f"HTTP {response.status_code}\n"

            f"{response.text}"

        )


    data = response.json()


    login = (

        data.get(

            "login",

            ""

        )

        or ""

    ).strip().lower()


    user_id = (

        data.get(

            "user_id",

            ""

        )

        or ""

    )


    if not login:

        raise RuntimeError(

            "Twitch did not return the username belonging "

            "to the access token."

        )


    debug("")

    debug(

        "[CHAT] Twitch token identity:"

    )

    debug(

        f"        Username: {login}"

    )

    debug(

        f"        User ID:  {user_id}"

    )


    debug("")

    debug(

        "[CHAT] Twitch token scopes:"

    )

    debug(

        f"        {data.get('scopes', [])}"

    )


    return login, user_id