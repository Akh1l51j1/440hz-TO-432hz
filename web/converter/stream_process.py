"""
stream_process.py  –  Standalone process that runs the 432 Hz audio stream.

Usage:  python stream_process.py <input_device_id> <output_device_id>

Runs until killed (SIGTERM / Ctrl+C).  Prints status as JSON to stdout.
This is spawned by the Django web UI so the audio stream runs in its
own process — identical to how 432_converter.py works from the terminal.
"""

import sys
import json
import signal
import sounddevice as sd
import numpy as np

# ─────────────────────────────────────────────
#  SETTINGS  (identical to 432_converter.py)
# ─────────────────────────────────────────────
CHUNK_SIZE = 4096
RATIO      = 432 / 440

RING_BITS   = 18
RING_SIZE   = 1 << RING_BITS
RING_MASK   = RING_SIZE - 1
MAX_LATENCY = RING_SIZE // 2
TARGET_LAT  = CHUNK_SIZE * 2

_ring  = None
_wpos  = 0
_rpos  = 0.0
_ready = False


# ─────────────────────────────────────────────
#  AUDIO CALLBACK  (verbatim from 432_converter.py)
# ─────────────────────────────────────────────
def process_audio(indata, outdata, frames, time, status):
    global _ring, _wpos, _rpos, _ready

    if status:
        print(json.dumps({"type": "warning", "msg": str(status)}), flush=True)

    n_ch = indata.shape[1]

    try:
        if not _ready:
            _ring  = np.zeros((RING_SIZE, n_ch), dtype=np.float32)
            _wpos  = 0
            _rpos  = 0.0
            _ready = True

        wp  = _wpos & RING_MASK
        end = wp + frames
        if end <= RING_SIZE:
            _ring[wp:end] = indata
        else:
            first = RING_SIZE - wp
            _ring[wp:] = indata[:first]
            _ring[:frames - first] = indata[first:]
        _wpos += frames

        positions = _rpos + np.arange(frames, dtype=np.float64) * RATIO
        _rpos = positions[-1] + RATIO

        idx  = np.floor(positions).astype(np.int64)
        frac = (positions - idx).astype(np.float32)

        i0 = (idx - 1) & RING_MASK
        i1 = idx       & RING_MASK
        i2 = (idx + 1) & RING_MASK
        i3 = (idx + 2) & RING_MASK

        for ch in range(n_ch):
            y0 = _ring[i0, ch]
            y1 = _ring[i1, ch]
            y2 = _ring[i2, ch]
            y3 = _ring[i3, ch]

            c1 = 0.5 * (y2 - y0)
            c2 = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3
            c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2)

            outdata[:, ch] = ((c3 * frac + c2) * frac + c1) * frac + y1

        latency = float(_wpos) - _rpos
        if latency > MAX_LATENCY:
            _rpos = float(_wpos) - TARGET_LAT

    except Exception as exc:
        print(json.dumps({"type": "error", "msg": str(exc)}), flush=True)
        outdata[:] = indata


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    if len(sys.argv) != 3:
        print(json.dumps({"type": "error", "msg": "Usage: stream_process.py <input_id> <output_id>"}), flush=True)
        sys.exit(1)

    input_id  = int(sys.argv[1])
    output_id = int(sys.argv[2])

    devices = sd.query_devices()

    in_dev  = devices[input_id]
    out_dev = devices[output_id]

    sample_rate  = int(out_dev["default_samplerate"])
    in_channels  = min(in_dev["max_input_channels"],  2)
    out_channels = min(out_dev["max_output_channels"], 2)
    channels     = min(in_channels, out_channels)

    # Report ready
    print(json.dumps({
        "type":          "started",
        "input_device":  in_dev["name"],
        "output_device": out_dev["name"],
        "sample_rate":   sample_rate,
        "channels":      channels,
    }), flush=True)

    try:
        with sd.Stream(
            device=(input_id, output_id),
            samplerate=sample_rate,
            blocksize=CHUNK_SIZE,
            dtype="float32",
            channels=channels,
            callback=process_audio,
            latency="high",
        ):
            # Block until killed
            signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
            while True:
                sd.sleep(1000)

    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(json.dumps({"type": "error", "msg": str(exc)}), flush=True)
        sys.exit(1)
    finally:
        print(json.dumps({"type": "stopped"}), flush=True)


if __name__ == "__main__":
    main()
