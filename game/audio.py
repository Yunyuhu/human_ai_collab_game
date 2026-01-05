import os
import pygame as pg


class AudioManager:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.snd_wrong = None
        self.snd_drum = None
        self.snd_denied = None
        self.snd_agent_my = None
        self.snd_agent_your = None
        self.load()

    def load(self) -> None:
        def safe(path: str):
            if not os.path.exists(path):
                print(f"Sound not found: {path}")
                return None
            try:
                return pg.mixer.Sound(path)
            except Exception as exc:
                print(f"Load sound failed {path}: {exc}")
                return None

        self.snd_wrong = safe(os.path.join(self.base_dir, "source", "wrong.mp3"))
        self.snd_drum = safe(os.path.join(self.base_dir, "source", "small_drum.mp3"))
        self.snd_denied = safe(os.path.join(self.base_dir, "source", "denied.mp3"))
        self.snd_agent_my = safe(os.path.join(self.base_dir, "source", "agent_mysound.mp3"))
        self.snd_agent_your = safe(os.path.join(self.base_dir, "source", "agent_yoursound.mp3"))

    def play(self, snd):
        if snd:
            snd.play()
