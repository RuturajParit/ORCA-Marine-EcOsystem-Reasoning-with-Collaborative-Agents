"""Run:  python -m scripts.check_data  -> tests every data source and prints what works."""
import json
import server

for label, fn in (("core grid (Open-Meteo)", lambda: len(server.build_grid()["points"])),
                  ("extra ocean layers", lambda: {k: (v["available"], v["error"]) for k, v in server.build_ocean(None)["layers"].items()})):
    try:
        print(label, "->", json.dumps(fn(), indent=1, default=str))
    except Exception as e:
        print(label, "FAILED:", e)
