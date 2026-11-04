import os
import shutil
import subprocess
import requests
import frappe

DEFAULT_OLLAMA_MODEL = "llama3.2:1b"


def is_model_installed(base_url="http://127.0.0.1:11434", model_name=DEFAULT_OLLAMA_MODEL):
    """Check if model is present in Ollama via HTTP API or CLI."""
    target_base = (model_name.split(":")[0] if ":" in model_name else model_name).lower()
    
    # 1. Check HTTP API
    try:
        res = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=4)
        if res.ok:
            data = res.json()
            for m in data.get("models", []):
                name = (m.get("name") or m.get("model") or "").lower()
                if name == model_name.lower() or name.startswith(f"{target_base}:") or name == target_base:
                    return True
    except Exception:
        pass

    # 2. Check CLI
    ollama_bin = shutil.which("ollama") or "/usr/local/bin/ollama" or "/usr/bin/ollama"
    if os.path.exists(ollama_bin) if os.path.isabs(ollama_bin) else shutil.which("ollama"):
        try:
            out = subprocess.check_output([ollama_bin, "list"], text=True, timeout=5)
            if target_base in out.lower():
                return True
        except Exception:
            pass

    return False


def pull_ollama_model(model_name=DEFAULT_OLLAMA_MODEL, base_url="http://127.0.0.1:11434", block=True):
    """
    Pulls the model into Ollama via API or CLI.
    Runs automatically if model is not present.
    """
    if is_model_installed(base_url, model_name):
        return True, f"Model '{model_name}' is already installed."

    # Method 1: Ollama HTTP API /api/pull
    try:
        res = requests.post(
            f"{base_url.rstrip('/')}/api/pull",
            json={"name": model_name, "stream": False},
            timeout=400
        )
        if res.ok:
            return True, f"Model '{model_name}' pulled successfully via Ollama API."
    except Exception:
        pass

    # Method 2: Ollama CLI
    ollama_bin = shutil.which("ollama") or "/usr/local/bin/ollama" or "/usr/bin/ollama"
    if os.path.exists(ollama_bin) if os.path.isabs(ollama_bin) else shutil.which("ollama"):
        try:
            if block:
                subprocess.check_call([ollama_bin, "pull", model_name], timeout=400)
                return True, f"Model '{model_name}' pulled successfully via CLI."
            else:
                subprocess.Popen([ollama_bin, "pull", model_name])
                return True, f"Triggered background pull for '{model_name}'."
        except Exception as e:
            return False, f"CLI pull failed: {str(e)}"

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

    # 2. Check and pull Ollama model
    try:
        cfg = frappe.get_single("Chatbot Settings")
        model = cfg.ollama_model or DEFAULT_OLLAMA_MODEL
        base = cfg.ollama_url or "http://127.0.0.1:11434"

        if not is_model_installed(base, model):
            print(f"[Ollama] Model '{model}' not found in Ollama. Auto-running: ollama pull {model} ...")
            success, msg = pull_ollama_model(model, base, block=False)
            print(f"[Ollama] {msg}")
        else:
            print(f"[Ollama] Model '{model}' is already present.")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Ollama Auto-Install Check Failed")

