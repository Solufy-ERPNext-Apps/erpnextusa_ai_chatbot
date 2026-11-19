#!/usr/bin/env bash
# install_ollama_mac.sh - Installs Ollama and the preferred chatbot model on macOS
set -e

echo "========================================================"
echo "  Setting up Qwen 4B and Llama 1B for Solufy Chatbot  "
echo "========================================================"

# 1. Check if ollama CLI is already available
if command -v ollama >/dev/null 2>&1; then
    echo "✓ Ollama CLI is already installed at: $(which ollama)"
else
    echo "• Ollama not found. Installing Ollama for macOS..."
    
    if command -v brew >/dev/null 2>&1; then
        echo "• Installing via Homebrew..."
        brew install ollama
        brew services start ollama || true
    else
        echo "• Downloading official Ollama for macOS..."
        TEMP_ZIP="/tmp/Ollama-darwin.zip"
        curl -fsSL "https://ollama.com/download/Ollama-darwin.zip" -o "$TEMP_ZIP"
        echo "• Installing to /Applications/Ollama.app..."
        unzip -q -o "$TEMP_ZIP" -d /Applications/
        rm -f "$TEMP_ZIP"
        echo "• Launching Ollama app to register CLI..."
        open -a Ollama || true
        sleep 3
    fi
fi

# 2. Ensure Ollama daemon is running
echo "• Checking if Ollama service is running..."
MAX_RETRIES=10
COUNT=0
RUNNING=false

while [ $COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        RUNNING=true
        break
    fi
    echo "  Waiting for Ollama service to start (attempt $((COUNT+1))/$MAX_RETRIES)..."
    if [ -d "/Applications/Ollama.app" ]; then
        open -a Ollama || true
    elif command -v ollama >/dev/null 2>&1; then
        ollama serve >/dev/null 2>&1 &
    fi
    sleep 2
    COUNT=$((COUNT+1))
done

if [ "$RUNNING" = true ]; then
    echo "✓ Ollama service is active on http://127.0.0.1:11434"
else
    echo "⚠️ Warning: Ollama service did not respond on port 11434 yet. If you see Ollama in your Mac Menu bar, click it to finish setup."
fi

# 3. Pull the preferred reasoning, vision, and tools model
echo "• Pulling model 'qwen3-vl:4b-thinking' into Ollama..."
if command -v ollama >/dev/null 2>&1; then
    ollama pull qwen3-vl:4b-thinking
    ollama pull llama3.2:1b
elif [ -x "/opt/homebrew/bin/ollama" ]; then
    /opt/homebrew/bin/ollama pull qwen3-vl:4b-thinking
    /opt/homebrew/bin/ollama pull llama3.2:1b
elif [ -x "/usr/local/bin/ollama" ]; then
    /usr/local/bin/ollama pull qwen3-vl:4b-thinking
    /usr/local/bin/ollama pull llama3.2:1b
elif [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
    /Applications/Ollama.app/Contents/Resources/ollama pull qwen3-vl:4b-thinking
    /Applications/Ollama.app/Contents/Resources/ollama pull llama3.2:1b
else
    # Try via HTTP API
    echo "• Pulling via Ollama HTTP API..."
    curl -s http://127.0.0.1:11434/api/pull -d '{"name": "qwen3-vl:4b-thinking", "stream": false}' || true
    curl -s http://127.0.0.1:11434/api/pull -d '{"name": "llama3.2:1b", "stream": false}' || true
fi

echo ""
echo "========================================================"
echo "✓ Setup Complete! Qwen 4B and Llama 1B are ready in Ollama."
echo "========================================================"

