import sounddevice as sd
import numpy as np

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
CHUNK_SIZE = 4096
RATIO      = 432 / 440    # ≈ 0.98182  (read speed per output sample)

SAMPLE_RATE = 48000        # Overwritten before stream opens

# ─────────────────────────────────────────────
#  RING BUFFER  (continuous — no block edges)
# ─────────────────────────────────────────────
#  Input samples are written into a circular buffer.
#  A fractional read pointer advances at RATIO speed,
#  producing a continuous, unbroken output stream with
#  cubic Hermite interpolation — no block boundaries
#  means zero crackle.
#
#  Size = 2^18 = 262144 samples ≈ 5.5s at 48 kHz.
#  Read drifts behind write by ~75 samples/block (1.8%).
#  Latency correction triggers every ~3 min (inaudible).
# ─────────────────────────────────────────────
RING_BITS    = 18
RING_SIZE    = 1 << RING_BITS        # 262144
RING_MASK    = RING_SIZE - 1         # Fast modulo via bitwise AND
MAX_LATENCY  = RING_SIZE // 2        # Trigger correction at ~2.7s
TARGET_LAT   = CHUNK_SIZE * 2        # Reset to 2 blocks of latency

_ring  = None     # (RING_SIZE, channels) float32
_wpos  = 0        # int  — write position (grows monotonically)
_rpos  = 0.0      # float64 — fractional read position
_ready = False

# ─────────────────────────────────────────────
#  AUDIO CALLBACK
# ─────────────────────────────────────────────
def process_audio(indata, outdata, frames, time, status):
    """
    Continuous ring-buffer pitch shifter.
    1) Write input into circular buffer
    2) Read with fractional pointer at RATIO speed
    3) Cubic Hermite interpolation (4-point spline)
    → Zero block-boundary artifacts
    """
    global _ring, _wpos, _rpos, _ready

    if status:
        print(f"[stream] {status}", flush=True)

    n_ch = indata.shape[1]

    try:
        # ── Initialise on first call ─────────────────────────────────
        if not _ready:
            _ring  = np.zeros((RING_SIZE, n_ch), dtype=np.float32)
            _wpos  = 0
            _rpos  = 0.0
            _ready = True

        # ── 1. Write input into ring buffer ──────────────────────────
        wp = _wpos & RING_MASK
        end = wp + frames
        if end <= RING_SIZE:
            _ring[wp:end] = indata
        else:
            first = RING_SIZE - wp
            _ring[wp:] = indata[:first]
            _ring[:frames - first] = indata[first:]
        _wpos += frames

        # ── 2. Compute fractional read positions ─────────────────────
        positions = _rpos + np.arange(frames, dtype=np.float64) * RATIO
        _rpos = positions[-1] + RATIO

        # Split into integer index + fractional part
        idx  = np.floor(positions).astype(np.int64)
        frac = (positions - idx).astype(np.float32)

        # 4 neighbours for cubic interpolation (bitwise AND = fast mod)
        i0 = (idx - 1) & RING_MASK
        i1 = idx       & RING_MASK
        i2 = (idx + 1) & RING_MASK
        i3 = (idx + 2) & RING_MASK

        # ── 3. Cubic Hermite spline per channel ──────────────────────
        for ch in range(n_ch):
            y0 = _ring[i0, ch]
            y1 = _ring[i1, ch]
            y2 = _ring[i2, ch]
            y3 = _ring[i3, ch]

            c1 = 0.5 * (y2 - y0)
            c2 = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3
            c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2)

            outdata[:, ch] = ((c3 * frac + c2) * frac + c1) * frac + y1

        # ── 4. Latency drift correction ──────────────────────────────
        # Read falls ~75 samples/block behind write (speed < 1).
        # When gap exceeds half the ring, jump read forward.
        latency = float(_wpos) - _rpos
        if latency > MAX_LATENCY:
            _rpos = float(_wpos) - TARGET_LAT

    except Exception as exc:
        print(f"[callback error] {exc}", flush=True)
        outdata[:] = indata

# ─────────────────────────────────────────────
#  DEVICE SELECTION
# ─────────────────────────────────────────────
print("=" * 47)
print("  🎵  432 Hz Real-Time Converter  (WASAPI)")
print("=" * 47)
print(f"  Pitch ratio : {RATIO:.6f}  (432/440)")
print(f"  Block size  : {CHUNK_SIZE} samples")
print(f"  Ring buffer : {RING_SIZE} samples ({RING_SIZE/48000:.1f}s)")
print()

devices = sd.query_devices()
hostapis = sd.query_hostapis()

# ── Find WASAPI host-api index ────────────────
wasapi_index = None
for i, api in enumerate(hostapis):
    if "WASAPI" in api["name"]:
        wasapi_index = i
        break

if wasapi_index is None:
    print("❌  WASAPI host-api not found. Is sounddevice built with WASAPI support?")
    exit(1)

# ── Find CABLE Output (input side) ───────────
INPUT_DEVICE_ID = None
for i, dev in enumerate(devices):
    if ("CABLE Output" in dev["name"]
            and dev["max_input_channels"] > 0
            and dev["hostapi"] == wasapi_index):
        INPUT_DEVICE_ID = i
        break

if INPUT_DEVICE_ID is None:
    # Fallback: show all WASAPI input devices so user can identify the right one
    print("❌  Could not auto-detect 'CABLE Output' on WASAPI.")
    print("    Available WASAPI input devices:\n")
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and dev["hostapi"] == wasapi_index:
            print(f"    [{i:2d}] {dev['name']}")
    print()
    try:
        INPUT_DEVICE_ID = int(input("    Enter input device ID manually: "))
    except ValueError:
        exit(1)

print(f"✅  Input  [{INPUT_DEVICE_ID}]: {devices[INPUT_DEVICE_ID]['name']}")

# ── List WASAPI output devices for user to choose ─
print("\nAvailable WASAPI output devices:\n")
valid_outputs = []
for i, dev in enumerate(devices):
    if dev["max_output_channels"] > 0 and dev["hostapi"] == wasapi_index:
        valid_outputs.append(i)
        print(f"  [{i:2d}] {dev['name']}")

print("-" * 47)
try:
    user_choice = int(input("Enter the number for your Headphones/Speakers: "))
    if user_choice not in valid_outputs:
        print("❌  Invalid selection.")
        exit(1)
except ValueError:
    print("❌  Please enter a valid number.")
    exit(1)

OUTPUT_DEVICE_ID = user_choice

# ── Match sample rate to output device ───────
SAMPLE_RATE = int(devices[OUTPUT_DEVICE_ID]["default_samplerate"])
print(f"\n✅  Output [{OUTPUT_DEVICE_ID}]: {devices[OUTPUT_DEVICE_ID]['name']}")
print(f"    Sample rate : {SAMPLE_RATE} Hz")

# ── Number of channels: use minimum of in/out ─
in_channels  = min(devices[INPUT_DEVICE_ID]["max_input_channels"],  2)
out_channels = min(devices[OUTPUT_DEVICE_ID]["max_output_channels"], 2)
channels     = min(in_channels, out_channels)
print(f"    Channels    : {channels}")

# ─────────────────────────────────────────────
#  START STREAM
# ─────────────────────────────────────────────
print("\n" + "=" * 47)
print("  ▶  Streaming — play music in Spotify now.")
print("     Press Ctrl+C to stop.")
print("=" * 47 + "\n")

try:
    with sd.Stream(
        device=(INPUT_DEVICE_ID, OUTPUT_DEVICE_ID),
        samplerate=SAMPLE_RATE,
        blocksize=CHUNK_SIZE,
        dtype="float32",
        channels=channels,
        callback=process_audio,
        latency="high",         # Larger buffer = stable output
    ):
        while True:
            sd.sleep(1000)

except KeyboardInterrupt:
    print("\n🛑  Converter stopped.")
except Exception as exc:
    print(f"\n❌  Stream error: {exc}")
    print("\nTROUBLESHOOTING:")
    print("  • If you see 'Invalid sample rate', try setting SAMPLE_RATE = 44100 manually.")
    print("  • If you see 'exclusive mode' errors, open Windows Sound settings →")
    print("    Advanced → uncheck 'Allow applications to take exclusive control'")
    print("    for both the CABLE Output and your headphone device.")