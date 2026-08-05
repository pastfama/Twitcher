import os
import sys
import time
import traceback
import threading
from pathlib import Path

from PySide6.QtCore import (
    QCoreApplication,
    QMetaObject,
    Qt,
    QDir,
    QLockFile
)
from PySide6.QtWidgets import QApplication

from logger import debug, info, warning, error

from api import TwitchAPI
from mainmenu import MainMenu
from twitch_auth import authenticate
from twitch_token_manager import get_valid_token
from video import VideoWindow


# ============================================================
#                    MONITOR DEBUGGING
# ============================================================


def print_monitors(app):
    screens = app.screens()
    print()
    print("=" * 60)
    print("[DISPLAY] DETECTED MONITORS")
    print("=" * 60)
    print()
    print(f"[DISPLAY] Monitor count: {len(screens)}")
    print()
    primary = app.primaryScreen()

    for index, screen in enumerate(screens):
        geometry = screen.availableGeometry()
        is_primary = screen == primary
        print()
        print(f"[DISPLAY] Monitor {index + 1}")
        print(f"          Name: {screen.name()}")
        print()
        print(f"          Resolution: {geometry.width()}x{geometry.height()}")
        print()
        print(f"          Position: ({geometry.x()}, {geometry.y()})")
        print()
        print(f"          Primary: {is_primary}")

    print()
    print("=" * 60)


# ============================================================
#                    STARTUP ERROR
# ============================================================


def show_startup_error(title, error, wait=True):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()
    print(f"{type(error).__name__}: {error}")
    print()
    traceback.print_exc()
    print()
    if wait:
        input("Press Enter to exit...")


# ============================================================
#                    CREATE APPLICATION
# ============================================================


def create_application():
    app = QApplication(sys.argv)
    app.setOrganizationName("Watcher")
    app.setApplicationName("Watcher Control Center")
    return app


# ============================================================
#                    TWITCH AUTHENTICATION
# ============================================================


def initialize_twitch_authentication():
    """Initialize authentication for all platforms."""
    from account_manager import AccountManager
    am = AccountManager()

    print()
    print("[AUTH] Checking platform authentication...")

    # Check Twitch
    print("[AUTH] Checking Twitch...")
    access_token = get_valid_token()
    if not access_token:
        print("[AUTH] No valid Twitch token found.")
        print("[AUTH] Starting Twitch authorization flow...")
        if am.login_twitch():
            access_token = get_valid_token()
        else:
            print("[AUTH] Twitch login failed or was cancelled.")

    if access_token:
        print("[AUTH] Twitch authentication is ready.")
    else:
        print("[AUTH] Twitch authentication unavailable.")

    # Check Kick
    print("[AUTH] Checking Kick...")
    if am.is_kick_configured():
        print("[AUTH] Kick configured (public API).")
    else:
        print("[AUTH] Kick not configured.")
        print("[AUTH] To enable Kick, set KICK_CLIENT_ID and KICK_CLIENT_SECRET in .env")
        print("[AUTH] Or run: python -c \"from account_manager import AccountManager; AccountManager().login_kick()\"")

    # Check YouTube
    print("[AUTH] Checking YouTube...")
    if am.is_youtube_configured():
        print("[AUTH] YouTube configured.")
    else:
        print("[AUTH] YouTube not configured.")
        print("[AUTH] To enable YouTube, set YOUTUBE_API_KEY or YOUTUBE_CLIENT_ID in .env")
        print("[AUTH] Or run: python -c \"from account_manager import AccountManager; AccountManager().login_youtube()\"")

    print()
    return access_token


# ============================================================
#                    START WATCHER
# ============================================================


def start_watcher(app):
    # --------------------------------------------------------
    # AUTH-INDEPENDENT VIDEO WINDOW
    # --------------------------------------------------------
    #
    # The video window does NOT need any Twitch auth. Create it
    # first so playback of the last played channels can start
    # immediately, then authenticate for the API features in
    # the background.

    print()
    print("[VIDEO] Creating standalone VideoWindow (auth-free)...")
    video_window = VideoWindow()
    video_window.play_last_channels()
    print()
    print("[VIDEO] Video Window shown (auth-independent)")

    # --------------------------------------------------------
    # TWITCH AUTHENTICATION
    # --------------------------------------------------------

    access_token = initialize_twitch_authentication()

    # --------------------------------------------------------
    # TWITCH API
    # --------------------------------------------------------

    print()
    print("[TWITCH] Initializing Twitch API...")
    api = TwitchAPI(access_token=access_token)

    # --------------------------------------------------------
    # MAIN WINDOW
    # --------------------------------------------------------

    print()
    print("[WINDOW] Creating MainMenu...")
    window = MainMenu(api, video_window=video_window)
    window.show()

    # --------------------------------------------------------
    # RESTORE CONTROL CENTER
    # --------------------------------------------------------

    if hasattr(window, "restore_saved_geometry"):
        print()
        print("[WINDOW] Restoring Control Center geometry...")
        window.restore_saved_geometry()

    elif hasattr(window, "move_to_secondary_monitor"):
        print()
        print("[WINDOW] Moving Control Center to secondary monitor...")
        window.move_to_secondary_monitor()

    # --------------------------------------------------------
    # RESTORE VIDEO WINDOW
    # --------------------------------------------------------

    video_window = getattr(window, "video_window", None)

    if video_window:
        print()
        print("[WINDOW] Restoring Video Window...")

        if hasattr(video_window, "restore_saved_state"):
            video_window.restore_saved_state()

        elif hasattr(video_window, "restore_saved_geometry"):
            video_window.restore_saved_geometry()

        elif hasattr(video_window, "place_on_primary_monitor"):
            video_window.place_on_primary_monitor()

        video_window.show()
        print()
        print("[WINDOW] Video Window shown")

    # --------------------------------------------------------
    # READY
    # --------------------------------------------------------

    print()
    print("[WINDOW] Watcher initialized.")
    print()
    print("[WINDOW] Control Center: RESTORED POSITION")
    print("[WINDOW] Video Player: RESTORED POSITION")
    print()

    return window


# ============================================================
#                    MAIN
# ============================================================


def enable_verbose_logging():
    """Enable DEBUG-level logging when WATCHER_DEBUG=1 is set."""
    if os.environ.get("WATCHER_DEBUG") == "1":
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        print("[DEBUG] Verbose logging enabled (WATCHER_DEBUG=1)")


def main():
    # --------------------------------------------------------
    # VERBOSE DEBUGGING (from start_watcher_watch.bat)
    # --------------------------------------------------------
    enable_verbose_logging()

    # --------------------------------------------------------
    # SINGLE INSTANCE GUARD
    # --------------------------------------------------------
    #
    # Prevent two Watcher processes from running at the same
    # time. Two instances would each create an EventSub
    # subscription for the same channel, and Twitch rejects the
    # second one with HTTP 429 ("maximum subscriptions with type
    # and condition exceeded"), which also floods the logs.

    lock_file = QLockFile(
        os.path.join(QDir.tempPath(), "watcher-control-center.lock")
    )

    if not lock_file.tryLock(100):
        print()
        print("[LOCK] Another Watcher instance is already running. "
              "This instance will exit.")
        print()
        return

    print()
    print("=" * 60)
    print("                 WATCHER CONTROL CENTER")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # QT APPLICATION
    # --------------------------------------------------------

    app = create_application()

    # --------------------------------------------------------
    # FIRST-RUN WIZARD (poster + install folder confirmation)
    # --------------------------------------------------------

    try:
        from wizard import run_first_run_wizard
        run_first_run_wizard()
    except Exception as exc:
        print(f"[WIZARD] Could not show first-run wizard: {exc}")

    # --------------------------------------------------------
    # MONITORS
    # --------------------------------------------------------

    print_monitors(app)

    # --------------------------------------------------------
    # STARTUP
    # --------------------------------------------------------

    try:
        window = start_watcher(app)

    except Exception as error:
        show_startup_error("[STARTUP ERROR] Watcher failed to start.", error)
        return

    # --------------------------------------------------------
    # RUN EVENT LOOP
    # --------------------------------------------------------

    try:
        if os.environ.get("WATCHER_WATCH") == "1":
            debug("Watch mode enabled; starting source watcher")
            root = Path(__file__).parent
            skip = {".venv", "venv", "__pycache__", ".git", "build", "dist"}
            watch_files_and_exit_on_change([
                __file__,
                *sorted({
                    str(path)
                    for path in root.rglob("*.py")
                    if path.name != Path(__file__).name
                    and not skip.intersection(path.relative_to(root).parts)
                })
            ])

        info("Entering Qt event loop")
        exit_code = app.exec()
        info(f"Qt event loop exited with code {exit_code}")
        sys.exit(exit_code)

    except Exception as error:
        show_startup_error("[RUNTIME ERROR] Watcher crashed.", error)


def watch_files_and_exit_on_change(paths, interval=1.0):
    """Exit when a watched Python source file changes.

    This is a simple developer helper. Run with WATCHER_WATCH=1 and
    restart your app from the shell when the process exits.
    """
    mtimes = {}
    for path in paths:
        try:
            mtimes[path] = Path(path).stat().st_mtime
        except OSError:
            mtimes[path] = 0

    def watcher():
        while True:
            time.sleep(interval)
            for path in paths:
                try:
                    mtime = Path(path).stat().st_mtime
                except OSError:
                    mtime = 0
                if mtime != mtimes.get(path):
                    debug(f"Source change detected: {path}")
                    app = QCoreApplication.instance()
                    if app is not None:
                        debug("Requesting Qt application quit from watcher thread")
                        QMetaObject.invokeMethod(
                            app,
                            "quit",
                            Qt.QueuedConnection
                        )
                        return

                    warning("No Qt application instance available; falling back to os._exit(3)")
                    os._exit(3)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()


# ============================================================
#                    ENTRY POINT
# ============================================================


if __name__ == "__main__":
    main()