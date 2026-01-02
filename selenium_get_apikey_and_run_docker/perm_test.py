from pathlib import Path
p = Path(r"C:\Users\jzsmi\OneDrive\Desktop\lol analysis\lol_analysis\selenium_get_apikey_and_run_docker\apikey.txt")
try:
    p.write_text("test", encoding="utf-8")
    print("Wrote OK to", p.resolve())
except Exception as e:
    import os, traceback
    print("TYPE:", type(e))
    print("REPR:", repr(e))
    print("STR :", str(e))
    try:
        print("errno:", e.errno)
    except Exception:
        pass
    try:
        print("winerror:", e.winerror)
    except Exception:
        pass
    traceback.print_exc()