"""V0.6 non-blocking wheel push-to-talk and microphone capture.

PTT deliberately stops at WAV capture. Speech-to-text belongs to V0.7.
The runtime imports pygame/sounddevice lazily so telemetry/tests still run without
physical audio/controller hardware.
"""
from __future__ import annotations

import threading
import time
import wave
import math
from array import array
from dataclasses import dataclass, replace
from pathlib import Path

from .app_paths import PTT_LOGS


@dataclass(frozen=True, slots=True)
class PTTConfig:
    enabled: bool = False
    controller_index: int = 0
    button_index: int = 6
    mic_device: int | None = None
    sample_rate: int = 16000
    channels: int = 1
    poll_hz: int = 100
    debounce_ms: int = 50
    output_dir: str = str(PTT_LOGS)
    backend: str = "hid"
    controller_name: str = "ESP32S3_DEV"
    hid_vendor_id: int = 0x303A
    hid_product_id: int = 0x1001
    hid_usage_page: int = 0x0001
    hid_usage: int = 0x0005


class MicrophoneRecorder:
    def __init__(self, config: PTTConfig) -> None:
        self.config = config
        self._stream = None
        self._frames: list[bytes] = []
        self._lock = threading.Lock()
        self._active_sample_rate = int(config.sample_rate)
        self.last_rms_dbfs: float | None = None
        self.last_peak_dbfs: float | None = None

    def start(self) -> None:
        import sounddevice as sd
        with self._lock:
            self._frames = []
        def callback(indata, frames, time_info, status):
            del frames, time_info
            if status:
                # PortAudio status is diagnostic only; never block telemetry.
                pass
            with self._lock:
                self._frames.append(bytes(indata))
        # A number of Windows WASAPI/Bluetooth endpoints reject 16 kHz even
        # though they work correctly at their native 44.1/48 kHz rate.  Whisper
        # accepts arbitrary WAV sample rates, so prefer 16 kHz but fall back to
        # the endpoint's native rate instead of silently recording the wrong mic
        # or failing the PTT capture.
        rate = int(self.config.sample_rate)
        try:
            sd.check_input_settings(device=self.config.mic_device, channels=self.config.channels,
                                    dtype="int16", samplerate=rate)
        except Exception:
            info = sd.query_devices(self.config.mic_device, "input")
            native = int(round(float(info.get("default_samplerate") or 0.0)))
            if native <= 0:
                raise
            sd.check_input_settings(device=self.config.mic_device, channels=self.config.channels,
                                    dtype="int16", samplerate=native)
            rate = native
        self._active_sample_rate = rate
        self._stream = sd.RawInputStream(
            samplerate=rate,
            blocksize=0,
            device=self.config.mic_device,
            channels=self.config.channels,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> Path | None:
        stream, self._stream = self._stream, None
        if stream is None:
            return None
        stream.stop(); stream.close()
        with self._lock:
            payload = b"".join(self._frames)
            self._frames = []
        if not payload:
            return None
        # Capture diagnostics make wrong/quiet microphone selection immediately
        # visible in the console without adding a blocking audio test path.
        try:
            samples = array("h")
            samples.frombytes(payload)
            if samples:
                peak = max(abs(v) for v in samples) / 32768.0
                mean_sq = sum(float(v) * float(v) for v in samples) / len(samples)
                rms = math.sqrt(mean_sq) / 32768.0
                self.last_peak_dbfs = 20.0 * math.log10(max(peak, 1e-9))
                self.last_rms_dbfs = 20.0 * math.log10(max(rms, 1e-9))
                print(f"[PTT] MIC LEVEL rms={self.last_rms_dbfs:.1f} dBFS peak={self.last_peak_dbfs:.1f} dBFS rate={self._active_sample_rate} Hz", flush=True)
        except Exception:
            self.last_peak_dbfs = self.last_rms_dbfs = None
        out = Path(self.config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / time.strftime("ptt_%Y%m%d_%H%M%S.wav")
        # Avoid collision if two captures finish within the same second.
        n = 1
        while path.exists():
            path = out / (time.strftime("ptt_%Y%m%d_%H%M%S") + f"_{n}.wav")
            n += 1
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(self.config.channels)
            wav.setsampwidth(2)
            wav.setframerate(self._active_sample_rate)
            wav.writeframes(payload)
        return path

    def abort(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try: stream.stop(); stream.close()
            except Exception: pass
        with self._lock: self._frames = []


class PTTController:
    """Poll a wheel/game-controller button without blocking the UDP receiver."""
    def __init__(self, config: PTTConfig, recorder: MicrophoneRecorder | None = None, on_capture=None, on_press=None, on_release=None) -> None:
        self.config = config
        self.recorder = recorder or MicrophoneRecorder(config)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pressed = False
        self.last_capture: Path | None = None
        self.last_error: str | None = None
        self.on_capture = on_capture
        self.on_press = on_press
        self.on_release = on_release
        self._hid_ever_opened = False

    def start(self) -> None:
        """Start PTT in a worker thread.

        Kept for tests/embedders. On Windows the application runtime uses
        run_forever() on the main thread because SDL/pygame joystick polling is
        most reliable there.
        """
        if not self.config.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="race-engineer-ptt", daemon=True)
        self._thread.start()

    def run_forever(self, external_stop: threading.Event | None = None) -> None:
        """Poll the PTT controller on the calling thread until stopped."""
        if not self.config.enabled:
            return
        self._run(external_stop)

    def close(self, *, wait: bool = True) -> None:
        self._stop.set()
        if wait and self._thread:
            self._thread.join(timeout=3.0)
        self.recorder.abort()

    def set_microphone_device(self, device: int | None) -> tuple[bool, str]:
        """Switch the capture device between PTT transmissions.

        Never swaps an active PortAudio stream mid-utterance; the selected device
        is applied to the next PTT press.
        """
        if self._pressed or getattr(self.recorder, "_stream", None) is not None:
            return False, "Release PTT before changing microphone"
        new_config = replace(self.config, mic_device=device)
        self.config = new_config
        self.recorder.config = new_config
        return True, "System default" if device is None else f"Device {device}"

    def _run(self, external_stop: threading.Event | None = None) -> None:
        if self.config.backend != "hid":
            try:
                self._run_pygame(external_stop)
            except Exception as error:
                self.last_error = str(error)
                print(f"[PTT] Disabled: {error}", flush=True)
                self.recorder.abort()
            return

        # Native USB disconnects remove the Receiver's HID interface at the same
        # instant as its CDC COM port. A transient hidapi read error must not
        # permanently disable radio for the rest of the race: close/abort the old
        # handle, wait for Windows re-enumeration, and reopen by stable VID/PID/usage.
        had_ready_link = False
        reported_error: str | None = None
        while not self._stop.is_set() and not (external_stop and external_stop.is_set()):
            try:
                self._run_hid(external_stop, reconnect=had_ready_link)
                return
            except Exception as error:
                self.last_error = str(error)
                if self._pressed:
                    self._pressed = False
                self.recorder.abort()
                message = str(error)
                if message != reported_error:
                    prefix = "HID link lost" if had_ready_link else "HID unavailable"
                    print(f"[PTT] {prefix}: {message}; waiting for Receiver...", flush=True)
                    reported_error = message
                # If we had ever successfully opened the HID interface, every
                # subsequent failure is treated as a disconnect/re-enumeration.
                had_ready_link = had_ready_link or bool(getattr(self, "_hid_ever_opened", False))
                if self._stop.wait(0.50):
                    return

    def _run_pygame(self, external_stop: threading.Event | None = None) -> None:
        import pygame
        pygame.init(); pygame.joystick.init()
        try:
            if pygame.joystick.get_count() <= self.config.controller_index:
                raise RuntimeError(f"controller index {self.config.controller_index} not found")
            joystick = pygame.joystick.Joystick(self.config.controller_index)
            joystick.init()
            if self.config.button_index < 0 or self.config.button_index >= joystick.get_numbuttons():
                raise RuntimeError(f"button {self.config.button_index} invalid; controller has {joystick.get_numbuttons()} buttons")
            print(f"[PTT] Controller: {joystick.get_name()} | button {self.config.button_index} (pygame)", flush=True)
            print("[PTT] Ready - hold the configured button to talk.", flush=True)
            delay = 1.0 / max(20, self.config.poll_hz)
            while not self._stop.is_set() and not (external_stop and external_stop.is_set()):
                pygame.event.pump()
                self._handle_button(bool(joystick.get_button(self.config.button_index)))
                time.sleep(delay)
        finally:
            pygame.joystick.quit(); pygame.quit()

    @staticmethod
    def _bit_signature(base: bytes, held: bytes, variable: bytes) -> list[tuple[int, int, int]]:
        """Legacy pure helper retained for compatibility with the V0.6 tests."""
        result = []
        for i, (a, b) in enumerate(zip(base, held)):
            changed = (a ^ b) & (~variable[i] & 0xFF)
            for bit in range(8):
                mask = 1 << bit
                if changed & mask:
                    result.append((i, mask, 1 if b & mask else 0))
        return result

    @staticmethod
    def _stable_bits(samples: list[bytes]) -> dict[tuple[int, int], int]:
        """Bits whose value is identical in every same-length report sample."""
        if not samples:
            return {}
        length = len(samples[0])
        samples = [sample for sample in samples if len(sample) == length]
        if not samples:
            return {}
        stable: dict[tuple[int, int], int] = {}
        for i in range(length):
            for bit in range(8):
                mask = 1 << bit
                values = {1 if sample[i] & mask else 0 for sample in samples}
                if len(values) == 1:
                    stable[(i, mask)] = values.pop()
        return stable

    @classmethod
    def _verified_button_signature(
        cls, released_before: list[bytes], held: list[bytes], released_after: list[bytes]
    ) -> list[tuple[int, int, int]]:
        """Find one binary HID bit that changes only while the requested button is held.

        Axis/HAT/report noise is rejected because the bit must be stable throughout all
        three phases and the two released phases must agree. A single physical button
        should resolve to exactly one bit; ambiguity is safer to reject than to create
        phantom radio presses.
        """
        a = cls._stable_bits(released_before)
        b = cls._stable_bits(held)
        c = cls._stable_bits(released_after)
        candidates: list[tuple[int, int, int]] = []
        for key, released_value in a.items():
            if key not in b or key not in c:
                continue
            if c[key] != released_value or b[key] == released_value:
                continue
            candidates.append((key[0], key[1], b[key]))
        return candidates if len(candidates) == 1 else []

    @staticmethod
    def _signature_pressed(report: bytes, signature: list[tuple[int, int, int]]) -> bool:
        if len(signature) != 1:
            return False
        i, mask, expected = signature[0]
        return i < len(report) and (1 if report[i] & mask else 0) == expected

    def _run_hid(self, external_stop: threading.Event | None = None, *, reconnect: bool = False) -> None:
        import json
        import hid

        devices = hid.enumerate()
        # The ESP32-S3 wheel has different names through DirectInput and raw HID.
        # Bind to the confirmed TinyUSB gamepad descriptor instead of a product
        # string or enumeration index (both can change across Windows APIs/reboots).
        candidates = [
            d for d in devices
            if int(d.get("vendor_id") or 0) == self.config.hid_vendor_id
            and int(d.get("product_id") or 0) == self.config.hid_product_id
            and int(d.get("usage_page") or 0) == self.config.hid_usage_page
            and int(d.get("usage") or 0) == self.config.hid_usage
        ]
        if not candidates:
            raise RuntimeError(
                "ESP32-S3 TinyUSB gamepad HID not found "
                f"({self.config.hid_vendor_id:04X}:{self.config.hid_product_id:04X}, "
                f"usage {self.config.hid_usage_page:04X}:{self.config.hid_usage:04X})"
            )
        info = candidates[0]
        dev = hid.device()
        dev.open_path(info["path"])
        dev.set_nonblocking(1)
        self._hid_ever_opened = True
        product = str(info.get("product_string") or self.config.controller_name)
        if reconnect:
            print(f"[PTT] HID RECONNECTED: {product} | logical button {self.config.button_index}", flush=True)
        else:
            print(f"[PTT] HID controller: {product} | logical button {self.config.button_index}", flush=True)

        mapping_path = Path(self.config.output_dir) / "hid_mapping.json"
        mapping_key = (
            f'{info.get("vendor_id",0):04x}:{info.get("product_id",0):04x}:'
            f'{info.get("usage_page",0):04x}:{info.get("usage",0):04x}:button{self.config.button_index}'
        )
        signature = None
        try:
            if mapping_path.exists():
                saved = json.loads(mapping_path.read_text(encoding="utf-8"))
                entry = saved.get(mapping_key)
                # Mapping schema v2 deliberately rejects the old "any changed bit"
                # calibration that could learn an axis/HAT bit and create phantom PTT.
                if isinstance(entry, dict) and entry.get("version") == 3:
                    raw = entry.get("signature")
                    if isinstance(raw, list) and len(raw) == 1:
                        signature = [(int(a), int(b), int(c)) for a, b, c in raw]
                        print("[PTT] Loaded verified HID button mapping (v3).", flush=True)
        except Exception:
            signature = None

        def collect(duration: float, *, expected_length: int | None = None) -> list[bytes]:
            result: list[bytes] = []
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline and not self._stop.is_set():
                data = dev.read(128)
                if data:
                    report = bytes(data)
                    if expected_length is None or len(report) == expected_length:
                        result.append(report)
                time.sleep(0.003)
            return result

        if signature is None:
            print("[PTT] Old/unverified HID mapping ignored. Starting safe calibration.", flush=True)
            print("[PTT] Keep ALL wheel controls released for 2 seconds...", flush=True)
            released_before = collect(2.0)
            if not released_before:
                dev.close(); raise RuntimeError("HID device opened but produced no input reports")
            length = len(released_before[-1])
            released_before = [x for x in released_before if len(x) == length]

            print(f"[PTT] PRESS AND HOLD ONLY wheel button {self.config.button_index} until told to release...", flush=True)
            held_samples: list[bytes] = []
            wait_deadline = time.monotonic() + 30.0
            # Human-paced calibration: wait for the press, then require the changed
            # state to remain stable for a full second before asking for release.
            released_stable = self._stable_bits(released_before)
            first_changed: bytes | None = None
            while time.monotonic() < wait_deadline and not self._stop.is_set():
                data = dev.read(128)
                if data and len(data) == length:
                    report = bytes(data)
                    if any((1 if report[i] & mask else 0) != value
                           for (i, mask), value in released_stable.items()):
                        first_changed = report
                        break
                time.sleep(0.003)
            if first_changed is None:
                dev.close(); raise RuntimeError("HID PTT calibration timed out; button press not detected")

            held_samples.append(first_changed)
            held_samples.extend(collect(1.0, expected_length=length))
            if len(held_samples) < 3:
                dev.close(); raise RuntimeError("Not enough stable HID reports while button was held")
            provisional = self._stable_bits(held_samples)
            changed_keys = [key for key, value in released_stable.items()
                            if key in provisional and provisional[key] != value]
            if len(changed_keys) != 1:
                dev.close(); raise RuntimeError(
                    "Could not uniquely identify Button 6 while held. Keep axes/HATs untouched and retry calibration."
                )
            button_key = changed_keys[0]
            print(f"[PTT] HOLD confirmed. NOW RELEASE button {self.config.button_index}; take your time...", flush=True)

            # Wait up to 30 seconds for the verified button bit to return to its
            # released value. Only then collect a full stable released window.
            release_deadline = time.monotonic() + 30.0
            release_seen = False
            released_value = released_stable[button_key]
            while time.monotonic() < release_deadline and not self._stop.is_set():
                data = dev.read(128)
                if data and len(data) == length:
                    report = bytes(data)
                    i, mask = button_key
                    value = 1 if report[i] & mask else 0
                    if value == released_value:
                        release_seen = True
                        break
                time.sleep(0.003)
            if not release_seen:
                dev.close(); raise RuntimeError("HID PTT calibration timed out waiting for button release")

            print("[PTT] RELEASE detected. Keep controls untouched while verifying for 1 second...", flush=True)
            released_after = collect(1.0, expected_length=length)
            signature = self._verified_button_signature(released_before, held_samples, released_after)
            if not signature:
                dev.close(); raise RuntimeError(
                    "Could not uniquely verify the PTT button bit. Keep axes/HATs untouched and retry calibration."
                )

            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                saved = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
            except Exception:
                saved = {}
            saved[mapping_key] = {"version": 3, "signature": [list(x) for x in signature]}
            mapping_path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
            byte_index, mask, expected = signature[0]
            print(f"[PTT] Verified button mapping: byte {byte_index}, mask 0x{mask:02X}, pressed={expected}", flush=True)
            print("[PTT] HID mapping saved (v3). Calibration complete.", flush=True)

        print("[PTT] Ready - hold the configured button to talk.", flush=True)
        delay = 1.0 / max(20, self.config.poll_hz)
        debounce_seconds = max(0.0, self.config.debounce_ms / 1000.0)
        candidate_state = False
        candidate_since = time.monotonic()
        try:
            while not self._stop.is_set() and not (external_stop and external_stop.is_set()):
                data = dev.read(128)
                if data:
                    last = bytes(data)
                    raw_pressed = self._signature_pressed(last, signature)
                    now = time.monotonic()
                    if raw_pressed != candidate_state:
                        candidate_state = raw_pressed
                        candidate_since = now
                # Some TinyUSB gamepads emit reports only when input state
                # changes.  Debounce must therefore advance on poll time, not
                # require a second identical HID packet after the edge.
                now = time.monotonic()
                if candidate_state != self._pressed and (now - candidate_since) >= debounce_seconds:
                    self._handle_button(candidate_state)
                time.sleep(delay)
            if self._pressed:
                self._handle_button(False)
        finally:
            dev.close()

    def _handle_button(self, pressed: bool) -> None:
        if pressed == self._pressed:
            return
        self._pressed = pressed
        if pressed:
            if self.on_press is not None:
                self.on_press()
            print("[PTT] PRESSED - LISTENING", flush=True)
            try:
                self.recorder.start()
                self.last_error = None
            except Exception as error:
                # Keep the logical pressed state latched until the physical button
                # is released.  Resetting _pressed here caused the HID poll loop
                # to re-enter this branch continuously while the button was still
                # held, producing repeated microphone errors.  More importantly,
                # on_release never ran, leaving SpeechOutput permanently in
                # listening mode and silencing CORNER COACH for the rest of the
                # session.
                self.last_error = str(error)
                self.recorder.abort()
                print(f"[PTT] Microphone error: {error}. Release PTT and select a valid MIC device.", flush=True)
        else:
            print("[PTT] RELEASED - capture complete", flush=True)
            try:
                self.last_capture = self.recorder.stop()
                if self.last_capture:
                    print(f"[PTT] WAV: {self.last_capture}", flush=True)
                    if self.on_capture is not None:
                        self.on_capture(self.last_capture)
                else:
                    print("[PTT] No audio captured", flush=True)
                if self.on_release is not None:
                    self.on_release(self.last_capture)
            except Exception as error:
                self.last_error = str(error)
                print(f"[PTT] Capture error: {error}", flush=True)


def list_audio_devices() -> None:
    from .audio_devices import query_audio_devices
    devices = query_audio_devices()
    if not devices:
        print("No audio devices detected.")
        return
    for d in devices:
        roles = []
        if d.input_capable: roles.append("IN")
        if d.output_capable: roles.append("OUT")
        print(f"{d.index}: {d.name} | {'/'.join(roles) or '-'} | {d.default_samplerate:g} Hz")


def list_controllers() -> None:
    import pygame
    pygame.init(); pygame.joystick.init()
    try:
        count = pygame.joystick.get_count()
        if not count:
            print("No game controllers detected.")
        for i in range(count):
            j = pygame.joystick.Joystick(i); j.init()
            print(f"{i}: {j.get_name()} | buttons={j.get_numbuttons()} axes={j.get_numaxes()} hats={j.get_numhats()}")
    finally:
        pygame.joystick.quit(); pygame.quit()


def _hid_text(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()
    return str(value)


def list_hid_devices() -> None:
    """Print HID descriptors needed to select the wheel's raw HID interface."""
    import hid

    devices = hid.enumerate()
    if not devices:
        print("No HID devices detected.")
        return

    print(f"HID devices detected: {len(devices)}")
    print("=" * 72)
    for index, info in enumerate(devices):
        vid = int(info.get("vendor_id") or 0)
        pid = int(info.get("product_id") or 0)
        usage_page = int(info.get("usage_page") or 0)
        usage = int(info.get("usage") or 0)
        interface = info.get("interface_number")
        path = _hid_text(info.get("path"))
        product = _hid_text(info.get("product_string"))
        manufacturer = _hid_text(info.get("manufacturer_string"))
        serial = _hid_text(info.get("serial_number"))
        game_controller = usage_page == 0x01 and usage in (0x04, 0x05)

        print(f"HID {index}")
        print(f"  Product      : {product}")
        print(f"  Manufacturer : {manufacturer}")
        print(f"  VID:PID      : {vid:04X}:{pid:04X}")
        print(f"  Usage        : 0x{usage_page:04X}:0x{usage:04X}" + ("  <-- Joystick/Gamepad" if game_controller else ""))
        print(f"  Interface    : {interface if interface is not None else 'N/A'}")
        print(f"  Serial       : {serial}")
        print(f"  Path         : {path}")
        print("-" * 72)
