# cli.py
from pathlib import Path
import sys

from dotenv import load_dotenv
import uvicorn

# Ensure the directory containing this script is importable
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

ENV_FILE = SCRIPT_DIR.parent.parent / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def _get_app_ref() -> str:
    """Find app.py or main.py next to this script and return the uvicorn reference."""
    for module in ("app", "main"):
        if (SCRIPT_DIR / f"{module}.py").exists():
            return f"{module}:app"
    print("Error: Could not find 'app.py' or 'main.py' in the same directory as cli.py.")
    sys.exit(1)


def dev() -> None:
    """Run in development mode (auto-reload) on 10.0.0.84:8000."""
    app_ref = _get_app_ref()
    print(f"DEV mode: {app_ref} → http://10.0.0.84:8000")
    print("Auto-reload: enabled")
    uvicorn.run(app_ref, host="10.0.0.84", port=8000, reload=True)


def prod() -> None:
    """Run in production mode (2 workers) on 10.0.0.84:8000."""
    app_ref = _get_app_ref()
    print(f"PROD mode: {app_ref} → http://10.0.0.84:8000")
    print("Workers: 2")
    uvicorn.run(app_ref, host="10.0.0.84", port=8000, workers=2)


if __name__ == "__main__":
    # Allows: python cli.py  OR  python cli.py dev  OR  python cli.py prod
    if len(sys.argv) > 1 and sys.argv[1] == "prod":
        prod()
    else:
        dev()
