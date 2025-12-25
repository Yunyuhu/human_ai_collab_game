import json
import re
import queue
import threading
import time


class VoiceSignalListener:
    def __init__(self, model_path, phrase_map, cooldown_sec=0.3, debug=False):
        self.model_path = str(model_path)
        self.phrase_map = {self._normalize(k): v for k, v in phrase_map.items()}
        self.cooldown_sec = cooldown_sec
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._last_fire = 0.0
        self._active = False
        self._debug = debug
        self._last_debug = 0.0
        self._enabled = False
        self._last_text = ""
        self._last_text_time = 0.0
        self._last_event_time = 0.0

    def start(self):
        if self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def set_enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    def poll(self):
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def is_active(self):
        return self._active and self._enabled

    def _run(self):
        try:
            from vosk import Model, KaldiRecognizer
            import sounddevice as sd
        except Exception as e:
            print("Voice listener disabled (missing deps):", e)
            return

        try:
            default_in = sd.default.device[0]
            if default_in is None or default_in < 0:
                default_in = sd.query_devices(kind="input")["index"]
            samplerate = int(sd.query_devices(default_in, "input")["default_samplerate"])
            model = Model(self.model_path)
            recognizer = KaldiRecognizer(model, samplerate)
        except Exception as e:
            print("Voice listener disabled (model load failed):", e)
            return

        def callback(indata, frames, time_info, status):
            if not self._enabled:
                return
            if status:
                return
            data = bytes(indata)
            if self._debug:
                now = time.time()
                if now - self._last_debug > 0.5:
                    try:
                        from array import array

                        samples = array("h", data)
                        level = max(abs(s) for s in samples) if samples else 0
                        print("Mic level:", level)
                    except Exception:
                        pass
                    self._last_debug = now
            if recognizer.AcceptWaveform(data):
                result = recognizer.Result()
                self._handle_result(result)
            else:
                partial = recognizer.PartialResult()
                self._handle_result(partial)

        try:
            print("Voice listener active on input device:", default_in)
            with sd.RawInputStream(
                samplerate=samplerate,
                blocksize=1600,
                dtype="int16",
                channels=1,
                device=default_in,
                callback=callback,
            ):
                self._active = True
                while not self._stop_event.is_set():
                    time.sleep(0.1)
        except Exception as e:
            print("Voice listener disabled (mic error):", e)
        finally:
            self._active = False

    def _handle_result(self, result_json):
        try:
            data = json.loads(result_json)
        except Exception:
            return
        text = data.get("text") or data.get("partial") or ""
        if not text:
            return
        norm = self._normalize(text)
        if self._debug:
            now = time.time()
            if now - self._last_debug > 0.5:
                label = "Voice heard" if data.get("text") else "Voice partial"
                print(f"{label}: {text}")
                self._last_debug = now
        now = time.time()
        if now - self._last_event_time < self.cooldown_sec:
            return
        now = time.time()
        if norm == self._last_text and now - self._last_text_time < 1.0:
            return
        for phrase, event in self.phrase_map.items():
            if phrase and self._fuzzy_contains(norm, phrase):
                self._last_fire = now
                self._last_text = norm
                self._last_text_time = now
                self._last_event_time = now
                self._queue.put(event)
                break

    def _normalize(self, text):
        text = text.strip()
        text = re.sub(
            r"[\s\u3000\-_.,，。！？!?、：:；;“”\"'‘’（）()\[\]{}<>《》]+",
            "",
            text,
        )
        return text

    def _fuzzy_contains(self, text, target):
        if target in text:
            return True
        if len(target) <= 2:
            return False
        hits = 0
        for ch in target:
            if ch in text:
                hits += 1
        return hits / len(target) >= 0.7
