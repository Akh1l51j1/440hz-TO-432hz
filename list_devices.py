import sounddevice as sd

devices = sd.query_devices()
apis = sd.query_hostapis()

print("ALL OUTPUT DEVICES:")
print("=" * 70)
for i, d in enumerate(devices):
    if d["max_output_channels"] > 0:
        api_name = apis[d["hostapi"]]["name"]
        print(f"  [{i:2d}] {d['name']:<45} {api_name}")
print("=" * 70)
