#!/bin/bash
# Prepares a Claude Code on the web session to run the pipeline: ffmpeg, the
# Python dependencies, and the TLS fix edge-tts needs behind the agent proxy.
set -euo pipefail

# Local machines already have their own setup; only the remote container needs this.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "🔧 Preparing AutoShorts AI environment..."

# 1. ffmpeg — the whole composer is built on it.
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "   Installing ffmpeg..."
  sudo apt-get update -qq >/dev/null 2>&1 || apt-get update -qq >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive sudo apt-get install -y -qq ffmpeg >/dev/null 2>&1 \
    || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null 2>&1
fi
command -v ffmpeg >/dev/null 2>&1 && echo "   ✅ $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

# 2. Python dependencies.
echo "   Installing Python dependencies..."
pip install -q -r "${CLAUDE_PROJECT_DIR:-.}/requirements.txt" 2>&1 | grep -v "^WARNING: Running pip" || true

# Debian ships cryptography and blinker without pip metadata, so pip cannot
# replace them in place: google-genai and flask both fail to import until they
# are installed alongside rather than over.
pip install -q --ignore-installed cffi cryptography blinker 2>&1 | grep -v "^WARNING: Running pip" || true

# 3. edge-tts pins certifi's bundle explicitly, so the agent proxy's CA has to be
# appended there — SSL_CERT_FILE alone does not reach it, and without this every
# voiceover fails TLS verification.
CA_BUNDLE=/root/.ccr/ca-bundle.crt
if [ -f "$CA_BUNDLE" ]; then
  CERTIFI_PEM="$(python3 -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  if [ -n "$CERTIFI_PEM" ] && [ -f "$CERTIFI_PEM" ]; then
    if ! grep -q "AGENT-PROXY-BUNDLE-ADDED" "$CERTIFI_PEM"; then
      echo "# AGENT-PROXY-BUNDLE-ADDED" >> "$CERTIFI_PEM"
      cat "$CA_BUNDLE" >> "$CERTIFI_PEM"
      echo "   ✅ Proxy CA appended to certifi (edge-tts TLS)"
    fi
  fi
  echo "export SSL_CERT_FILE=$CA_BUNDLE" >> "${CLAUDE_ENV_FILE:-/dev/null}"
  echo "export REQUESTS_CA_BUNDLE=$CA_BUNDLE" >> "${CLAUDE_ENV_FILE:-/dev/null}"
fi

# 4. Report what is still missing rather than failing: the keys come from the
# environment config, and a session is still useful without them.
for key in GEMINI_API_KEY PEXELS_API_KEY; do
  if [ -z "${!key:-}" ] && ! grep -qs "^${key}=." "${CLAUDE_PROJECT_DIR:-.}/.env" 2>/dev/null; then
    echo "   ⚠️ $key not set — add it to the environment config or .env before generating."
  fi
done

echo "✨ Ready. Run: python main.py --check"
