import os
import sys
import time
import shutil
import subprocess
import requests
import frappe

DEFAULT_OLLAMA_MODEL = "llama3.2:1b"


def find_ollama_binary():
    """Find ollama CLI binary across macOS (Apple Silicon / Intel / App) and Linux."""
    # 1. Check current PATH
    bin_path = shutil.which("ollama")
    if bin_path and os.path.isfile(bin_path) and os.access(bin_path, os.X_OK):
        return bin_path

    # 2. Known common locations across macOS and Linux
    candidates = [
        "/opt/homebrew/bin/ollama",                          # macOS Apple Silicon (M1/M2/M3/M4)
        "/usr/local/bin/ollama",                            # macOS Intel & Linux
        "/usr/bin/ollama",                                  # Linux system
        "/bin/ollama",
        os.path.expanduser("~/.local/bin/ollama"),
        os.path.expanduser("~/bin/ollama"),
        "/Applications/Ollama.app/Contents/Resources/ollama" # macOS Ollama App bundle
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def is_ollama_service_running(base_url="http://127.0.0.1:11434"):
    """Check if Ollama HTTP service is listening and reachable."""
    try:
        res = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=1.5)
        return res.ok
    except Exception:
        return False


def try_start_ollama_service(ollama_bin, base_url="http://127.0.0.1:11434"):
    """If Ollama is installed but daemon is not running, attempt to start it in background."""
    if not ollama_bin or is_ollama_service_running(base_url):
        return True

    # On macOS, if /Applications/Ollama.app exists, try launch
    if sys.platform == "darwin" and os.path.exists("/Applications/Ollama.app"):
        try:
            subprocess.Popen(["open", "-a", "Ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(8):
                time.sleep(0.5)
                if is_ollama_service_running(base_url):
                    return True
        except Exception:
            pass

    # Otherwise run `ollama serve` in detached background session
    try:
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        for _ in range(6):
            time.sleep(0.5)
            if is_ollama_service_running(base_url):
                return True
    except Exception:
        pass

    return False


def is_model_installed(base_url="http://127.0.0.1:11434", model_name=DEFAULT_OLLAMA_MODEL, ollama_bin=None):
    """Check if model is present in Ollama via HTTP API or CLI."""
    target_base = (model_name.split(":")[0] if ":" in model_name else model_name).lower()
    
    # 1. Check HTTP API if service is running
    try:
        res = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=2)
        if res.ok:
            data = res.json()
            for m in data.get("models", []):
                name = (m.get("name") or m.get("model") or "").lower()
                if name == model_name.lower() or name.startswith(f"{target_base}:") or name == target_base:
                    return True
    except Exception:
        pass

    # 2. Check CLI
    bin_path = ollama_bin or find_ollama_binary()
    if bin_path:
        try:
            out = subprocess.check_output([bin_path, "list"], text=True, timeout=5, stderr=subprocess.DEVNULL)
            if target_base in out.lower():
                return True
        except Exception:
            pass

    return False


def pull_ollama_model(model_name=DEFAULT_OLLAMA_MODEL, base_url="http://127.0.0.1:11434", ollama_bin=None, block=True):
    """
    Pulls the model into Ollama via CLI or API.
    Runs automatically if model is not present.
    """
    bin_path = ollama_bin or find_ollama_binary()

    if is_model_installed(base_url, model_name, bin_path):
        return True, f"Model '{model_name}' is already installed."

    # Make sure service is running if binary exists
    if bin_path and not is_ollama_service_running(base_url):
        try_start_ollama_service(bin_path, base_url)

    # Method 1: Ollama CLI
    if bin_path:
        try:
            if block:
                subprocess.check_call([bin_path, "pull", model_name], timeout=600)
                return True, f"Model '{model_name}' pulled successfully via CLI."
            else:
                subprocess.Popen(
                    [bin_path, "pull", model_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                return True, f"Started background download of '{model_name}'."
        except Exception:
            pass

    # Method 2: Ollama HTTP API /api/pull
    try:
        if is_ollama_service_running(base_url):
            if block:
                res = requests.post(
                    f"{base_url.rstrip('/')}/api/pull",
                    json={"name": model_name, "stream": False},
                    timeout=600
                )
                if res.ok:
                    return True, f"Model '{model_name}' pulled successfully via Ollama API."
            else:
                import threading
                def _bg_pull():
                    try:
                        requests.post(
                            f"{base_url.rstrip('/')}/api/pull",
                            json={"name": model_name, "stream": False},
                            timeout=600
                        )
                    except Exception:
                        pass
                t = threading.Thread(target=_bg_pull, daemon=True)
                t.start()
                return True, f"Started background download of '{model_name}' via API."
    except Exception:
        pass

    return False, f"Could not reach Ollama at {base_url} to pull '{model_name}'."


def ensure_ollama_model():
    """
    Frappe hook called after_install and after_migrate.
    Automatically checks and pulls llama3.2:1b if not present.
    Also syncs all website knowledge articles.
    """
    # 1. Sync Website Knowledge
    try:
        from erpnextusa_ai_chatbot.sync_knowledge import sync_all
        sync_all()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Knowledge Sync Error")

    # 2. Check and handle Ollama model
    try:
        cfg = frappe.get_single("Chatbot Settings")
        model = cfg.ollama_model or DEFAULT_OLLAMA_MODEL
        base = cfg.ollama_url or "http://127.0.0.1:11434"

        ollama_bin = find_ollama_binary()
        is_running = is_ollama_service_running(base)

        if not is_running and ollama_bin:
            is_running = try_start_ollama_service(ollama_bin, base)

        if is_running or ollama_bin:
            if not is_model_installed(base, model, ollama_bin):
                print(f"[Ollama] Model '{model}' not found in Ollama. Auto-running: ollama pull {model} ...")
                success, msg = pull_ollama_model(model, base, ollama_bin=ollama_bin, block=False)
                print(f"[Ollama] {msg}")
            else:
                print(f"[Ollama] Model '{model}' is installed and ready.")
        else:
            print("[Ollama] Local Ollama service is not running on this system.")
            print(f"         • The chatbot is ready and will use the built-in Solufy Knowledge Base.")
            print(f"         • To enable local LLM: install from https://ollama.com and run 'ollama pull {model}'.")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Ollama Auto-Install Check Failed")
