"""
audio_engine.py  –  Wraps the 432 Hz converter for the Django web UI.

The audio stream runs in a SEPARATE PROCESS (stream_process.py),
identical to how 432_converter.py works from the terminal.
This avoids PortAudio/WASAPI threading issues inside Django.

Public API:
  - get_devices()   → dict with WASAPI output devices
  - get_status()    → dict describing current stream state
  - start_stream()  → spawn stream subprocess
  - stop_stream()   → kill stream subprocess
  - clear_error()   → dismiss stale error
"""

import json
import os
import sys
import subprocess
import threading
import sounddevice as sd

# ─────────────────────────────────────────────
#  CONSTANTS  (for display in the UI header)
# ─────────────────────────────────────────────
CHUNK_SIZE = 4096
RATIO      = 432 / 440
RING_BITS  = 18
RING_SIZE  = 1 << RING_BITS

# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────
_proc = None       # subprocess.Popen
_lock = threading.Lock()

_state = {
    "running":       False,
    "input_device":  None,
    "output_device": None,
    "sample_rate":   None,
    "channels":      None,
    "error":         None,
}

# Path to stream_process.py  (sits next to this file)
_STREAM_SCRIPT = os.path.join(os.path.dirname(__file__), "stream_process.py")

# Python executable  (same venv python that runs Django)
_PYTHON = sys.executable


# ─────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────

def get_devices():
    """
    Returns WASAPI output devices (excluding CABLE virtual devices).
    Mirrors the terminal's device-selection logic exactly.
    """
    devices  = sd.query_devices()
    hostapis = sd.query_hostapis()

    # ── Find WASAPI host-api index ────────────
    wasapi_index = None
    for i, api in enumerate(hostapis):
        if "WASAPI" in api["name"]:
            wasapi_index = i
            break

    # ── Auto-detect CABLE Output (input side) ─
    input_device_id   = None
    input_device_name = None
    if wasapi_index is not None:
        for i, dev in enumerate(devices):
            if ("CABLE Output" in dev["name"]
                    and dev["max_input_channels"] > 0
                    and dev["hostapi"] == wasapi_index):
                input_device_id   = i
                input_device_name = dev["name"]
                break

    # ── List WASAPI output devices, skip CABLE ─
    output_devices = []
    if wasapi_index is not None:
        for i, dev in enumerate(devices):
            if (dev["max_output_channels"] > 0
                    and dev["hostapi"] == wasapi_index
                    and "CABLE" not in dev["name"]):
                output_devices.append({
                    "id":                  i,
                    "name":               dev["name"],
                    "default_samplerate": int(dev["default_samplerate"]),
                    "max_output_channels": dev["max_output_channels"],
                })

    return {
        "wasapi_available":  wasapi_index is not None,
        "cable_found":       input_device_id is not None,
        "input_device_id":   input_device_id,
        "input_device_name": input_device_name,
        "output_devices":    output_devices,
    }


def get_status():
    """Returns a snapshot of the current stream state."""
    with _lock:
        # If process died unexpectedly, detect it
        if _state["running"] and _proc is not None and _proc.poll() is not None:
            _state["running"] = False
            if _state["error"] is None:
                _state["error"] = "Stream process exited unexpectedly."
        return dict(_state)


def clear_error():
    """Clear a stale error so the UI returns to idle."""
    with _lock:
        _state["error"] = None


def start_stream(output_device_id: int):
    """
    Start the 432 Hz stream in a separate process.
    Returns (success: bool, error_message: str | None)
    """
    global _proc

    with _lock:
        if _state["running"]:
            return False, "Stream is already running."

    devices  = sd.query_devices()
    hostapis = sd.query_hostapis()

    # Find WASAPI
    wasapi_index = None
    for i, api in enumerate(hostapis):
        if "WASAPI" in api["name"]:
            wasapi_index = i
            break
    if wasapi_index is None:
        return False, "WASAPI host-api not found."

    # Auto-detect CABLE Output (input)
    input_device_id = None
    for i, dev in enumerate(devices):
        if ("CABLE Output" in dev["name"]
                and dev["max_input_channels"] > 0
                and dev["hostapi"] == wasapi_index):
            input_device_id = i
            break
    if input_device_id is None:
        return False, "Could not auto-detect 'CABLE Output' as input device."

    # Validate output device
    if output_device_id < 0 or output_device_id >= len(devices):
        return False, f"Invalid output device ID: {output_device_id}"
    if devices[output_device_id]["max_output_channels"] < 1:
        return False, f"Device {output_device_id} has no output channels."

    # ── Spawn the stream subprocess ──────────────
    try:
        proc = subprocess.Popen(
            [_PYTHON, _STREAM_SCRIPT, str(input_device_id), str(output_device_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        # Wait for the first JSON message (either "started" or "error")
        first_line = proc.stdout.readline().strip()
        if not first_line:
            # Process died before printing anything — grab stderr
            proc.wait(timeout=3)
            stderr_out = proc.stderr.read()
            err_msg = stderr_out.strip() or "Stream process failed to start (no output)."
            return False, err_msg

        msg = json.loads(first_line)

        if msg.get("type") == "error":
            proc.wait(timeout=3)
            return False, msg.get("msg", "Unknown error from stream process.")

        # Success — stream is running
        with _lock:
            _proc = proc
            _state.update({
                "running":       True,
                "input_device":  msg.get("input_device"),
                "output_device": msg.get("output_device"),
                "sample_rate":   msg.get("sample_rate"),
                "channels":      msg.get("channels"),
                "error":         None,
            })

        return True, None

    except Exception as exc:
        return False, f"Failed to launch stream process: {exc}"


def stop_stream():
    """Kill the stream subprocess. Returns (success, error_message)."""
    global _proc

    with _lock:
        if not _state["running"]:
            return False, "No stream is currently running."
        proc = _proc

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        return False, f"Error stopping stream: {exc}"

    with _lock:
        _proc = None
        _state.update({
            "running":       False,
            "input_device":  None,
            "output_device": None,
            "sample_rate":   None,
            "channels":      None,
            "error":         None,
        })

    return True, None
