import sys
import traceback

from PySide6.QtWidgets import QApplication

from api import TwitchAPI
from mainmenu import MainMenu
from twitch_token_manager import get_valid_token


# ============================================================
#                    MONITOR DEBUGGING
# ============================================================


def print_monitors(

    app

):

    screens = app.screens()

    print()

    print(

        "============================================================"

    )

    print(

        "[DISPLAY] DETECTED MONITORS"

    )

    print(

        "============================================================"

    )

    print(

        f"[DISPLAY] Monitor count: "

        f"{len(screens)}"

    )

    primary = app.primaryScreen()

    for index, screen in enumerate(

        screens

    ):

        geometry = screen.availableGeometry()

        is_primary = (

            screen == primary

        )

        print()

        print(

            f"[DISPLAY] Monitor {index + 1}"

        )

        print(

            f"          Name: "

            f"{screen.name()}"

        )

        print(

            f"          Resolution: "

            f"{geometry.width()}x"

            f"{geometry.height()}"

        )

        print(

            f"          Position: "

            f"({geometry.x()}, "

            f"{geometry.y()})"

        )

        print(

            f"          Primary: "

            f"{is_primary}"

        )

    print()

    print(

        "============================================================"

    )


# ============================================================
#                    STARTUP ERROR
# ============================================================


def show_startup_error(

    title,

    error,

    wait=True

):

    print()

    print(

        "============================================================"

    )

    print(

        title

    )

    print(

        "============================================================"

    )

    print()

    print(

        f"{type(error).__name__}: "

        f"{error}"

    )

    print()

    traceback.print_exc()

    print()

    if wait:

        input(

            "Press Enter to exit..."

        )


# ============================================================
#                    CREATE APPLICATION
# ============================================================


def create_application():

    app = QApplication(

        sys.argv

    )

    app.setOrganizationName(

        "Twitcher"

    )

    app.setApplicationName(

        "Twitcher Control Center"

    )

    return app


# ============================================================
#                    TWITCH AUTHENTICATION
# ============================================================


def initialize_twitch_authentication():

    print()

    print(

        "[TWITCH] Validating Twitch authentication..."

    )

    access_token = get_valid_token()


    if not access_token:

        raise RuntimeError(

            "Twitch authentication is unavailable.\n\n"

            "The access token is invalid and could not be refreshed.\n\n"

            "Run twitch_auth.py to authenticate again."

        )


    print()

    print(

        "[TWITCH] Twitch authentication is ready."

    )

    print()

    return access_token


# ============================================================
#                    START TWITCHER
# ============================================================


def start_twitcher(

    app

):

    # --------------------------------------------------------
    # TWITCH AUTHENTICATION
    # --------------------------------------------------------

    initialize_twitch_authentication()


    # --------------------------------------------------------
    # TWITCH API
    # --------------------------------------------------------

    print()

    print(

        "[TWITCH] Initializing Twitch API..."

    )

    api = TwitchAPI()


    # --------------------------------------------------------
    # MAIN WINDOW
    # --------------------------------------------------------

    print()

    print(

        "[WINDOW] Creating MainMenu..."

    )

    window = MainMenu(

        api

    )

    window.show()


    # --------------------------------------------------------
    # RESTORE CONTROL CENTER
    # --------------------------------------------------------

    if hasattr(

        window,

        "restore_saved_geometry"

    ):

        print()

        print(

            "[WINDOW] Restoring Control Center geometry..."

        )

        window.restore_saved_geometry()


    elif hasattr(

        window,

        "move_to_secondary_monitor"

    ):

        print()

        print(

            "[WINDOW] Moving Control Center "

            "to secondary monitor..."

        )

        window.move_to_secondary_monitor()


    # --------------------------------------------------------
    # RESTORE VIDEO WINDOW
    # --------------------------------------------------------

    video_window = getattr(

        window,

        "video_window",

        None

    )


    if video_window:

        print()

        print(

            "[WINDOW] Restoring Video Window..."

        )


        if hasattr(

            video_window,

            "restore_saved_geometry"

        ):

            video_window.restore_saved_geometry()


        elif hasattr(

            video_window,

            "place_on_primary_monitor"

        ):

            video_window.place_on_primary_monitor()


    # --------------------------------------------------------
    # READY
    # --------------------------------------------------------

    print()

    print(

        "[WINDOW] Twitcher initialized."

    )

    print()

    print(

        "[WINDOW] Control Center: "

        "RESTORED POSITION"

    )

    print(

        "[WINDOW] Video Player: "

        "RESTORED POSITION"

    )

    print()

    return window


# ============================================================
#                    MAIN
# ============================================================


def main():

    print()

    print(

        "============================================================"

    )

    print(

        "                 TWITCHER CONTROL CENTER"

    )

    print(

        "============================================================"

    )

    print()


    # --------------------------------------------------------
    # QT APPLICATION
    # --------------------------------------------------------

    app = create_application()


    # --------------------------------------------------------
    # MONITORS
    # --------------------------------------------------------

    print_monitors(

        app

    )


    # --------------------------------------------------------
    # STARTUP
    # --------------------------------------------------------

    try:

        window = start_twitcher(

            app

        )


    except Exception as error:

        show_startup_error(

            "[STARTUP ERROR] Twitcher failed to start.",

            error

        )

        return


    # --------------------------------------------------------
    # RUN EVENT LOOP
    # --------------------------------------------------------

    try:

        sys.exit(

            app.exec()

        )


    except Exception as error:

        show_startup_error(

            "[RUNTIME ERROR] Twitcher crashed.",

            error

        )


# ============================================================
#                    ENTRY POINT
# ============================================================


if __name__ == "__main__":

    main()