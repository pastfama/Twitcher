import time

from announcements import AnnouncementEngine


engine = AnnouncementEngine()


engine.stream_ended(

    old_streamer="KNIG04Ei",

    new_streamer="M1gal",

    viewers=100,

    category="Grand Theft Auto V"

)


time.sleep(

    15

)