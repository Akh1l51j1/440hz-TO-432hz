import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .audio_engine import (
    get_devices, get_status, start_stream, stop_stream, clear_error,
    RATIO, CHUNK_SIZE, RING_SIZE,
)


def index(request):
    """Main page — list output devices and show stream status."""
    device_info = get_devices()
    status      = get_status()
    return render(request, "converter/index.html", {
        "device_info": device_info,
        "status":      status,
        "ratio":       f"{RATIO:.6f}",
        "chunk_size":  CHUNK_SIZE,
        "ring_size":   RING_SIZE,
        "ring_secs":   f"{RING_SIZE / 48000:.1f}",
    })


def api_status(request):
    """JSON endpoint polled by the UI to update status."""
    return JsonResponse(get_status())


@csrf_exempt
@require_POST
def api_start(request):
    """Start the stream with the selected output device."""
    try:
        data = json.loads(request.body)
        output_id = int(data["output_device_id"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"ok": False, "error": f"Bad request: {exc}"}, status=400)

    ok, error = start_stream(output_id)
    return JsonResponse({"ok": ok, "error": error})


@csrf_exempt
@require_POST
def api_stop(request):
    """Stop the running stream."""
    ok, error = stop_stream()
    return JsonResponse({"ok": ok, "error": error})


@csrf_exempt
@require_POST
def api_clear_error(request):
    """Dismiss a stale error and return to idle state."""
    clear_error()
    return JsonResponse({"ok": True})
