import os
import sys
import time
import shutil
import zipfile
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
    if is_ollama_service_running(base_url):
        return True

    # On macOS, if /Applications/Ollama.app exists, try launch
    if sys.platform == "darwin" and os.path.exists("/Applications/Ollama.app"):
        try:
            subprocess.Popen(["open", "-a", "Ollama", "--args", "hidden"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(8):
                time.sleep(0.5)
                if is_ollama_service_running(base_url):
                    return True
        except Exception:
            pass

    # Otherwise run `ollama serve` in detached background session
    if ollama_bin:
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


def auto_install_ollama():
    """
    Automatically downloads and installs Ollama on macOS or Linux
    without requiring manual steps.
    """
    system = sys.platform
    print("[Ollama] Ollama not found on this system. Initiating automatic installation...")

    # ------------------ macOS ------------------
    if system == "darwin":
        # 1. Try Homebrew if brew command exists
        brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
        if os.path.exists(brew_bin) if os.path.isabs(brew_bin) else shutil.which("brew"):
            try:
                print("[Ollama] Installing Ollama via Homebrew...")
                subprocess.check_call([brew_bin, "install", "ollama"], timeout=300)
                try:
                    subprocess.Popen([brew_bin, "services", "start", "ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
                time.sleep(2)
                found = find_ollama_binary()
                if found:
                    print(f"[Ollama] Successfully installed Ollama via Homebrew: {found}")
                    return found
            except Exception as e:
                print(f"[Ollama] Homebrew installation skipped ({e}). Downloading official Ollama bundle...")

        # 2. Direct macOS App download (Official Ollama-darwin.zip)
        try:
            print("[Ollama] Downloading official Ollama for macOS (https://ollama.com/download/Ollama-darwin.zip)...")
            temp_zip = "/tmp/Ollama-darwin.zip"
            res = requests.get("https://ollama.com/download/Ollama-darwin.zip", stream=True, timeout=240)
            if res.ok:
                with open(temp_zip, "wb") as f:
                    for chunk in res.iter_content(chunk_size=1024 * 1024):
                        if chunk: f.write(chunk)

                print("[Ollama] Extracting Ollama to /Applications/Ollama.app...")
                app_dest = "/Applications/Ollama.app"
                if os.path.exists(app_dest):
                    try:
                        shutil.rmtree(app_dest, ignore_errors=True)
                    except Exception:
                        pass

                with zipfile.ZipFile(temp_zip, "r") as z:
                    z.extractall("/Applications")

                try:
                    os.remove(temp_zip)
                except Exception:
                    pass

                # Symlink CLI binary into user and system PATH
                cli_bin = "/Applications/Ollama.app/Contents/Resources/ollama"
                if os.path.exists(cli_bin):
                    # Link to ~/.local/bin/ollama
                    user_bin_dir = os.path.expanduser("~/.local/bin")
                    os.makedirs(user_bin_dir, exist_ok=True)
                    user_link = os.path.join(user_bin_dir, "ollama")
                    try:
                        if os.path.islink(user_link) or os.path.exists(user_link):
                            os.remove(user_link)
                        os.symlink(cli_bin, user_link)
                    except Exception:
                        pass

                    # Link to /usr/local/bin/ollama if writable
                    try:
                        if os.access("/usr/local/bin", os.W_OK):
                            sys_link = "/usr/local/bin/ollama"
                            if os.path.islink(sys_link) or os.path.exists(sys_link):
                                os.remove(sys_link)
                            os.symlink(cli_bin, sys_link)
                    except Exception:
                        pass

                # Launch Ollama app
                try:
                    subprocess.Popen(["open", "-a", "Ollama", "--args", "hidden"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

                time.sleep(3)
                found = find_ollama_binary()
                if found:
                    print(f"[Ollama] Successfully installed and launched Ollama: {found}")
                    return found
        except Exception as e:
            print(f"[Ollama] Auto-install failed on macOS: {e}")

    # ------------------ Linux ------------------
    elif system.startswith("linux"):
        try:
            print("[Ollama] Installing Ollama via official installer (curl -fsSL https://ollama.com/install.sh | sh)...")
            subprocess.check_call("curl -fsSL https://ollama.com/install.sh | sh", shell=True, timeout=300)
            time.sleep(2)
            found = find_ollama_binary()
            if found:
                print(f"[Ollama] Successfully installed Ollama on Linux: {found}")
                return found
        except Exception as e:
            print(f"[Ollama] Linux auto-install script failed: {e}")

    return find_ollama_binary()


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


def ensure_node_dependencies():
    """Ensure @hugeicons/react and @hugeicons/core-free-icons are installed."""
    try:
        bench_dir = os.path.abspath(os.path.join(frappe.get_app_path("erpnextusa_ai_chatbot"), "..", "..", ".."))
        solufy_website_dir = os.path.join(bench_dir, "apps", "solufy_website")
        target_dir = solufy_website_dir if os.path.exists(solufy_website_dir) else os.path.join(bench_dir, "apps", "erpnextusa_ai_chatbot")

        hugeicons_pkg = os.path.join(target_dir, "node_modules", "@hugeicons", "react")
        if not os.path.exists(hugeicons_pkg):
            yarn_bin = shutil.which("yarn") or "/usr/local/bin/yarn" or "/opt/homebrew/bin/yarn"
            npm_bin = shutil.which("npm") or "/usr/local/bin/npm" or "/opt/homebrew/bin/npm"

            print("[Dependencies] Installing frontend icon packages (@hugeicons/react, @hugeicons/core-free-icons)...")
            installed = False
            if yarn_bin and (os.path.exists(yarn_bin) if os.path.isabs(yarn_bin) else shutil.which("yarn")):
                try:
                    subprocess.check_call(
                        [yarn_bin, "add", "@hugeicons/react", "@hugeicons/core-free-icons"],
                        cwd=target_dir,
                        timeout=180
                    )
                    installed = True
                    print("[Dependencies] Successfully installed @hugeicons via yarn.")
                except Exception as e:
                    print(f"[Dependencies] yarn install skipped ({e}). Trying npm...")

            if not installed and npm_bin and (os.path.exists(npm_bin) if os.path.isabs(npm_bin) else shutil.which("npm")):
                try:
                    subprocess.check_call(
                        [npm_bin, "install", "--save", "@hugeicons/react", "@hugeicons/core-free-icons"],
                        cwd=target_dir,
                        timeout=180
                    )
                    print("[Dependencies] Successfully installed @hugeicons via npm.")
                except Exception as e:
                    print(f"[Dependencies] npm install error: {e}")
        else:
            print("[Dependencies] @hugeicons packages are installed and ready.")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Frontend Dependencies Install Error")


def ensure_ollama_model():
    """
    Frappe hook called after_install and after_migrate.
    Automatically:
      1. Installs frontend node dependencies (@hugeicons/react, @hugeicons/core-free-icons).
      2. Syncs all website knowledge articles into MariaDB.
      3. Detects if Ollama is installed; if not, automatically installs it!
      4. Starts the Ollama service in background.
      5. Pulls llama3.2:1b model automatically.
    """
    # 1. Install frontend node dependencies
    try:
        ensure_node_dependencies()
    except Exception:
        pass

    # 2. Sync Website Knowledge
    try:
        from erpnextusa_ai_chatbot.sync_knowledge import sync_all
        sync_all()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Knowledge Sync Error")

    # 3. Check and handle Ollama model
    try:
        cfg = frappe.get_single("Chatbot Settings")
        model = cfg.ollama_model or DEFAULT_OLLAMA_MODEL
        base = cfg.ollama_url or "http://127.0.0.1:11434"

        ollama_bin = find_ollama_binary()
        is_running = is_ollama_service_running(base)

        # If Ollama is not installed on the system, auto-install it!
        if not ollama_bin and not is_running:
            ollama_bin = auto_install_ollama()
            is_running = is_ollama_service_running(base)

        if not is_running and ollama_bin:
            is_running = try_start_ollama_service(ollama_bin, base)

        if is_running or ollama_bin:
            if not is_model_installed(base, model, ollama_bin):
                print(f"[Ollama] Model '{model}' not found in Ollama. Auto-downloading: ollama pull {model} ...")
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
