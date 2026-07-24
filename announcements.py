import time
import traceback

import ollama

from voice import VoiceEngine


# ============================================================
# EASY SETTINGS
# ============================================================

ENABLE_VOICE = True

ENABLE_AI = True

AI_MODEL = "qwen3:8b"

MAX_WORDS = 35

DEBUG = True


# ============================================================
# AI PERSONALITY
# ============================================================

SYSTEM_PROMPT = f"""
You are TWITCHER, a funny live Twitch stream dispatcher announcer.

Your job is to announce when the viewer switches between Twitch streams.

PERSONALITY:
- witty
- sarcastic
- slightly chaotic
- occasionally dramatic
- clever
- futuristic radio announcer energy
- funny but not annoying

STRICT RULES:
- Generate ONLY the final announcement.
- NEVER show thinking or reasoning.
- NEVER write "Thinking".
- NEVER explain your answer.
- Maximum 2 short sentences.
- Maximum {MAX_WORDS} words.
- No emojis.
- No hashtags.
- Do not mention AI.
- Do not mention software or prompts.
- Make the wording different and creative.
- Do not insult the streamer.

CRITICAL VOICE RULE:
- NEVER say streamer usernames.
- NEVER spell streamer usernames.
- NEVER attempt to pronounce streamer usernames.
- Usernames may contain random letters and numbers.
- Refer to channels only as "the previous channel", "the new channel",
  "the raiding channel", or "this channel".
"""


# ============================================================
# ANNOUNCEMENT ENGINE
# ============================================================

class AnnouncementEngine:

    def __init__(self):

        print("[AI] Initializing local Ollama AI...")

        self.voice = VoiceEngine()

        self.client_ready = False

        self._check_ollama()

    # ========================================================
    # DEBUG LOGGER
    # ========================================================

    def _debug(self, message):

        if DEBUG:

            print(

                f"[DEBUG] {message}"

            )

    # ========================================================
    # OLLAMA CHECK
    # ========================================================

    def _check_ollama(self):

        try:

            self._debug(

                "Calling ollama.list()..."

            )

            models_response = ollama.list()

            self._debug(

                f"Ollama response type: "
                f"{type(models_response).__name__}"

            )

            model_names = []

            for model in models_response.models:

                model_name = model.model

                self._debug(

                    f"Found model: {model_name}"

                )

                if model_name:

                    model_names.append(

                        model_name

                    )

            if not model_names:

                print()

                print(

                    "[AI ERROR] No Ollama models found."

                )

                print(

                    f"[AI ERROR] Expected: {AI_MODEL}"

                )

                return

            model_found = False

            for model_name in model_names:

                if (

                    model_name == AI_MODEL

                    or model_name.startswith(

                        AI_MODEL + ":"

                    )

                ):

                    model_found = True

                    break

            if not model_found:

                print()

                print(

                    f"[AI ERROR] Required model not found: "
                    f"{AI_MODEL}"

                )

                print()

                print(

                    "[AI] Available models:"

                )

                for model_name in model_names:

                    print(

                        f"    - {model_name}"

                    )

                return

            self.client_ready = True

            print()

            print(

                f"[AI] Local model ready: {AI_MODEL}"

            )

            print(

                "[AI] Ollama connection successful."

            )

        except Exception as error:

            print()

            print(

                "[AI ERROR] Could not connect to Ollama."

            )

            print(

                f"{type(error).__name__}: {error}"

            )

            if DEBUG:

                traceback.print_exc()

    # ========================================================
    # STREAM ENDED
    # ========================================================

    def stream_ended(

        self,

        old_streamer,

        new_streamer,

        viewers,

        category

    ):

        fallback = (

            "The previous channel has left the building. "

            f"We're moving to the new channel, "

            f"where {viewers} viewers are watching "

            f"{category}."

        )

        prompt = f"""

The previous Twitch stream just ended.

INTERNAL DATA ONLY:
Previous streamer username: {old_streamer}
New streamer username: {new_streamer}

Current viewers:
{viewers}

Category:
{category}

The usernames above are ONLY for internal context.

DO NOT say them.
DO NOT spell them.
DO NOT pronounce them.

Refer to the previous streamer only as:
"the previous channel"

Refer to the new streamer only as:
"the new channel"

Create one short, funny, sarcastic transition announcement.

"""

        return self._generate_and_speak(

            prompt,

            fallback,

            blocked_names=[

                old_streamer,

                new_streamer

            ]

        )

    # ========================================================
    # RAID
    # ========================================================

    def raid(

        self,

        from_streamer,

        to_streamer,

        viewers

    ):

        fallback = (

            "Incoming raid from the raiding channel! "

            f"{viewers} viewers are entering the operation. "

            "Everyone act natural."

        )

        prompt = f"""

A Twitch raid has been detected.

INTERNAL DATA ONLY:
Source streamer username: {from_streamer}
Destination streamer username: {to_streamer}

Incoming viewers:
{viewers}

The usernames above are ONLY for internal context.

DO NOT say them.
DO NOT spell them.
DO NOT pronounce them.

Refer to the source only as:
"the raiding channel"

Refer to the destination only as:
"this channel"

Create one short, energetic, funny raid announcement.

"""

        return self._generate_and_speak(

            prompt,

            fallback,

            blocked_names=[

                from_streamer,

                to_streamer

            ]

        )

    # ========================================================
    # MANUAL SWITCH
    # ========================================================

    def manual_switch(

        self,

        old_streamer,

        new_streamer,

        viewers,

        category

    ):

        fallback = (

            "We're leaving the previous channel "

            "and moving to the new channel. "

            f"{viewers} viewers are already watching "

            f"{category}."

        )

        prompt = f"""

The viewer manually switched Twitch streams.

INTERNAL DATA ONLY:
Previous streamer username: {old_streamer}
New streamer username: {new_streamer}

Current viewers:
{viewers}

Category:
{category}

DO NOT say or pronounce either username.

Refer to them only as:
"the previous channel"
"the new channel"

Create one short, funny transition announcement.

"""

        return self._generate_and_speak(

            prompt,

            fallback,

            blocked_names=[

                old_streamer,

                new_streamer

            ]

        )

    # ========================================================
    # AI GENERATION
    # ========================================================

    def _generate_and_speak(

        self,

        prompt,

        fallback,

        blocked_names=None

    ):

        text = None

        if blocked_names is None:

            blocked_names = []

        # ----------------------------------------------------
        # AI GENERATION
        # ----------------------------------------------------

        if self.client_ready and ENABLE_AI:

            start_time = time.perf_counter()

            try:

                print()

                print(

                    "[AI] Generating local announcement..."

                )

                self._debug(

                    f"Model: {AI_MODEL}"

                )

                self._debug(

                    f"Thinking disabled: True"

                )

                response = ollama.chat(

                    model=AI_MODEL,

                    messages=[

                        {

                            "role": "system",

                            "content": SYSTEM_PROMPT

                        },

                        {

                            "role": "user",

                            "content": prompt

                        }

                    ],

                    think=False

                )

                elapsed = (

                    time.perf_counter()

                    - start_time

                )

                self._debug(

                    f"Generation time: "
                    f"{elapsed:.2f} seconds"

                )

                self._debug(

                    f"Response type: "
                    f"{type(response).__name__}"

                )

                text = response.message.content

                if not text:

                    raise RuntimeError(

                        "Ollama returned empty text."

                    )

                self._debug(

                    f"Raw AI response: {text!r}"

                )

                text = self._clean_text(

                    text

                )

                text = self._remove_blocked_names(

                    text,

                    blocked_names

                )

                if not text:

                    raise RuntimeError(

                        "Text became empty after cleaning."

                    )

                print()

                print(

                    "[AI] Local announcement generated."

                )

            except Exception as error:

                elapsed = (

                    time.perf_counter()

                    - start_time

                )

                print()

                print(

                    "[AI ERROR] Announcement generation failed."

                )

                print(

                    f"[AI ERROR] "
                    f"{type(error).__name__}: {error}"

                )

                print(

                    f"[AI ERROR] Time elapsed: "
                    f"{elapsed:.2f} seconds"

                )

                if DEBUG:

                    traceback.print_exc()

                print()

                print(

                    "[AI] Using fallback announcement."

                )

                text = fallback

        else:

            print()

            print(

                "[AI] AI unavailable."

            )

            print(

                "[AI] Using fallback announcement."

            )

            text = fallback

        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        print()

        print(

            "=================================================="

        )

        print(

            "[ANNOUNCEMENT]"

        )

        print(

            text

        )

        print(

            "=================================================="

        )

        # ----------------------------------------------------
        # VOICE
        # ----------------------------------------------------

        if ENABLE_VOICE:

            try:

                self._debug(

                    "Sending announcement to VoiceEngine..."

                )

                self.voice.speak(

                    text

                )

                self._debug(

                    "VoiceEngine completed."

                )

            except Exception as error:

                print()

                print(

                    "[VOICE ERROR]"

                )

                print(

                    f"{type(error).__name__}: {error}"

                )

                if DEBUG:

                    traceback.print_exc()

        return text

    # ========================================================
    # CLEAN AI OUTPUT
    # ========================================================

    def _clean_text(

        self,

        text

    ):

        if not text:

            return ""

        text = text.strip()

        # Remove Qwen thinking blocks

        if "<think>" in text:

            text = text.split(

                "<think>",

                1

            )[0]

        if "</think>" in text:

            text = text.split(

                "</think>",

                1

            )[-1]

        text = text.strip()

        # Remove surrounding quotation marks

        if (

            len(text) >= 2

            and text.startswith('"')

            and text.endswith('"')

        ):

            text = text[1:-1]

        # Remove accidental labels

        prefixes = [

            "Announcement:",

            "ANNOUNCEMENT:",

            "Here's the announcement:",

            "Here is the announcement:"

        ]

        for prefix in prefixes:

            if text.startswith(prefix):

                text = text[

                    len(prefix):

                ].strip()

        # Limit word count

        words = text.split()

        if len(words) > MAX_WORDS:

            text = " ".join(

                words[:MAX_WORDS]

            )

            text += "."

        return text.strip()

    # ========================================================
    # REMOVE USERNAMES FROM FINAL SPEECH
    # ========================================================

    def _remove_blocked_names(

        self,

        text,

        blocked_names

    ):

        original_text = text

        for name in blocked_names:

            if not name:

                continue

            text = text.replace(

                name,

                "the channel"

            )

            text = text.replace(

                name.lower(),

                "the channel"

            )

            text = text.replace(

                name.upper(),

                "the channel"

            )

        if text != original_text:

            self._debug(

                "Blocked username detected and removed "
                "from spoken announcement."

            )

        return text.strip()