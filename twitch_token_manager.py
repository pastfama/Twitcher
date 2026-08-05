import json
import os

import requests
from dotenv import load_dotenv

from twitch_auth import SCOPES as REQUIRED_SCOPES
from twitch_api.config_loader import get_never_request_scopes


# ============================================================
#                    CONFIGURATION
# ============================================================


from paths import get_data_dir

_DATA_DIR = get_data_dir()

ENV_FILE = os.path.join(
    _DATA_DIR,
    ".env"
)


TOKEN_FILE = os.path.join(
    _DATA_DIR,
    "twitch_token.json"
)


VALIDATE_URL = (
    "https://id.twitch.tv/oauth2/validate"
)


TOKEN_URL = (
    "https://id.twitch.tv/oauth2/token"
)


# ============================================================
#                    LOAD ENVIRONMENT
# ============================================================


load_dotenv(
    ENV_FILE
)


CLIENT_ID = (
    os.getenv(
        "TWITCH_CLIENT_ID",
        ""
    )
    or ""
).strip()


CLIENT_SECRET = (
    os.getenv(
        "TWITCH_CLIENT_SECRET",
        ""
    )
    or ""
).strip()


# ============================================================
#                    TOKEN MANAGER
# ============================================================


class TwitchTokenManager:


    # ========================================================
    #                    LOAD TOKEN
    # ========================================================


    @staticmethod
    def load_token():

        if not os.path.exists(
            TOKEN_FILE
        ):

            print()

            print(
                "[TWITCH AUTH] Token file not found."
            )

            print(
                TOKEN_FILE
            )

            return None


        try:

            with open(
                TOKEN_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                token_data = json.load(
                    file
                )


            if not isinstance(
                token_data,
                dict
            ):

                print()

                print(
                    "[TWITCH AUTH] Token file is invalid."
                )

                return None


            return token_data


        except Exception as error:

            print()

            print(
                "[TWITCH AUTH] Failed to read token file:"
            )

            print(
                error
            )

            return None


    # ========================================================
    #                    SAVE TOKEN
    # ========================================================


    @staticmethod
    def save_token(
        token_data
    ):

        with open(
            TOKEN_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                token_data,
                file,
                indent=4
            )


    # ========================================================
    #                    VALIDATE TOKEN
    # ========================================================


    @staticmethod
    def validate_token(
        access_token
    ):

        access_token = (
            access_token
            or ""
        ).strip()


        if not access_token:

            return False


        try:

            response = requests.get(

                VALIDATE_URL,

                headers={

                    "Authorization":

                    f"OAuth {access_token}"

                },

                timeout=15

            )


            print()

            print(
                "[TWITCH AUTH] Token validation:"
            )

            print(
                f"HTTP {response.status_code}"
            )


            if response.status_code == 200:

                data = response.json()


                print()

                print(
                    "[TWITCH AUTH] Token belongs to:"
                )

                print(
                    f"          "
                    f"{data.get('login')}"
                )


                print()

                print(
                    "[TWITCH AUTH] Token scopes:"
                )

                scopes = data.get(
                    "scopes",
                    []
                ) or []

                print(
                    f"          "
                    f"{scopes}"
                )

                missing_scopes = [
                    scope
                    for scope in REQUIRED_SCOPES
                    if scope not in scopes
                ]

                if missing_scopes:

                    print()

                    print(
                        "[TWITCH AUTH] Token is missing some scopes (non-fatal):"
                    )

                    for scope in missing_scopes:

                        print(
                            f"          {scope}"
                        )

                    print(
                        "[TWITCH AUTH] Token is still valid — "
                        "some features may be unavailable."
                    )

                # ------------------------------------------------
                # FORBIDDEN SCOPE CHECK
                # Check if token has any scopes from the
                # never_request list in config.yaml
                # ------------------------------------------------

                try:
                    forbidden_scopes = [
                        scope
                        for scope in scopes
                        if scope in get_never_request_scopes()
                    ]
                except Exception:
                    forbidden_scopes = []

                if forbidden_scopes:

                    print()

                    print(
                        "[TWITCH AUTH] WARNING: Token has forbidden scopes:"
                    )

                    for scope in forbidden_scopes:

                        print(
                            f"          {scope}"
                        )

                    print(
                        "[TWITCH AUTH] These scopes should never be requested."
                    )

                    print(
                        "[TWITCH AUTH] See twitch_api/config.yaml for details."
                    )

                return True


            print()

            print(
                response.text
            )


            return False


        except Exception as error:

            print()

            print(
                "[TWITCH AUTH] Validation error:"
            )

            print(
                error
            )


            return False


    # ========================================================
    #                    REFRESH TOKEN
    # ========================================================


    @classmethod
    def refresh_token(
        cls,
        refresh_token_value,
        previous_scope=None
    ):

        if not CLIENT_ID:

            print()

            print(
                "[TWITCH AUTH] "
                "TWITCH_CLIENT_ID missing."
            )

            return None


        if not CLIENT_SECRET:

            print()

            print(
                "[TWITCH AUTH] "
                "TWITCH_CLIENT_SECRET missing."
            )

            return None


        if not refresh_token_value:

            print()

            print(
                "[TWITCH AUTH] "
                "Refresh token missing."
            )

            return None


        print()

        print(
            "[TWITCH AUTH] "
            "Access token is invalid or expired."
        )


        print()

        print(
            "[TWITCH AUTH] Refreshing token..."
        )


        try:

            response = requests.post(

                TOKEN_URL,

                params={

                    "client_id":

                    CLIENT_ID,

                    "client_secret":

                    CLIENT_SECRET,

                    "grant_type":

                    "refresh_token",

                    "refresh_token":

                    refresh_token_value,

                },

                timeout=30

            )


        except Exception as error:

            print()

            print(
                "[TWITCH AUTH] "
                "Token refresh request failed:"
            )

            print(
                error
            )

            return None


        if response.status_code != 200:

            print()

            print(
                "[TWITCH AUTH] "
                "Token refresh failed."
            )

            print(
                f"HTTP {response.status_code}"
            )

            print(
                response.text
            )

            return None


        try:

            new_token_data = response.json()


        except Exception as error:

            print()

            print(
                "[TWITCH AUTH] "
                "Invalid refresh response:"
            )

            print(
                error
            )

            return None


        new_access_token = (
            new_token_data.get(
                "access_token"
            )
            or ""
        ).strip()


        if not new_access_token:

            print()

            print(
                "[TWITCH AUTH] "
                "Refresh response contains "
                "no access token."
            )

            return None


        # ----------------------------------------------------
        # PRESERVE REFRESH TOKEN
        # ----------------------------------------------------


        if not new_token_data.get(
            "refresh_token"
        ):

            new_token_data[
                "refresh_token"
            ] = refresh_token_value


        self_token_data = {

            "access_token":

            new_token_data.get(
                "access_token"
            ),

            "refresh_token":

            new_token_data.get(
                "refresh_token"
            ),

            "scope":

            new_token_data.get(
                "scope",
                previous_scope
            ),

        }


        if new_token_data.get(
            "expires_in"
        ) is not None:

            self_token_data[
                "expires_in"
            ] = new_token_data[
                "expires_in"
            ]


        cls.save_token(
            self_token_data
        )


        print()

        print(
            "[TWITCH AUTH] "
            "Token refreshed successfully."
        )


        return self_token_data


    # ========================================================
    #                    GET VALID TOKEN
    # ========================================================


    @classmethod
    def get_valid_token(
        cls
    ):

        token_data = (
            cls.load_token()
        )


        if not token_data:

            return None


        access_token = (
            token_data.get(
                "access_token"
            )
            or ""
        ).strip()


        if not access_token:

            print()

            print(
                "[TWITCH AUTH] "
                "Access token missing."
            )

            return None


        # ----------------------------------------------------
        # VALID ACCESS TOKEN
        # ----------------------------------------------------


        if cls.validate_token(
            access_token
        ):

            print()

            print(
                "[TWITCH AUTH] "
                "Existing token is valid."
            )


            return access_token


        # ----------------------------------------------------
        # REFRESH ACCESS TOKEN
        # ----------------------------------------------------


        refresh_token_value = (
            token_data.get(
                "refresh_token"
            )
            or ""
        ).strip()


        if not refresh_token_value:

            print()

            print(
                "[TWITCH AUTH] "
                "No refresh token available."
            )

            return None


        new_token_data = (
            cls.refresh_token(
                refresh_token_value,
                previous_scope=token_data.get(
                    "scope"
                )
            )
        )


        if not new_token_data:

            return None


        return (
            new_token_data.get(
                "access_token"
            )
        )


# ============================================================
#                    COMPATIBILITY FUNCTION
# ============================================================


def get_valid_token():

    return (
        TwitchTokenManager.get_valid_token()
    )