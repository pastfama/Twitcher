from core import run_in_background


class MainMenuRuntime:
    """Mixin providing background task execution.

    Note: load_twitch(), handle_user_loaded(), and handle_user_failed()
    are defined in channel_state.py which adds UI state updates (connection
    label styling). This class only provides the _run_background helper.
    """

    def _run_background(self, func, on_success, on_error):
        run_in_background(func, on_success, on_error)
