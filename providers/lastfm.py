class Provider:
    name = "lastfm"

    def __init__(self, cache_dir="."):
        raise NotImplementedError("implemented on branch spike/lastfm")

    def fetch(self, artist, track, album, isrc):
        raise NotImplementedError("implemented on branch spike/lastfm")
