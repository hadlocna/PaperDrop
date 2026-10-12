#!/bin/bash
# Apply only the tested recording changes; do not publish firmware or enable OTA.
set -euo pipefail
stage=${1:-/tmp/paperdrop-recording-timer}
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.'; exit 1; }
release=$(readlink -f /opt/paperdrop/current)
backup=/var/lib/paperdrop/maintenance/recording-timer-$(date +%Y%m%d-%H%M%S)
python="$release/venv/bin/python"
files=(controller.py store.py languages.py media.py pi_media.py cousin_mail.py)
"$python" - "$stage" <<'PY'
import pathlib, sys, urllib.request, json
p = pathlib.Path(sys.argv[1])
if len(list((p/'speech').glob('*.wav'))) != 10:
    raise SystemExit('The ten validated spoken prompts are required.')
with urllib.request.urlopen('http://127.0.0.1:8766/state', timeout=5) as response:
    state = json.load(response)
if state['mode'] not in ('home', 'personal'):
    raise SystemExit('Return the Stream Deck to Home before installing.')
PY
mkdir -p "$backup/code"
chmod 700 "$backup"
for file in "${files[@]}"; do
    cp -p "$release/streamdeck/$file" "$backup/code/$file"
done
printf '%s\n' "$release" > "$backup/release-path"
rollback() {
    trap - ERR
    for file in "${files[@]}"; do
        cp -p "$backup/code/$file" "$release/streamdeck/$file"
    done
    systemctl restart paperdrop-runtime.service
    echo "Restored original code from $backup"
}
trap rollback ERR
systemctl stop paperdrop-runtime.service
for file in "${files[@]}"; do
    install -m 644 "$stage/agent/streamdeck/$file" "$release/streamdeck/$file"
done
for clip in "$stage"/speech/*.wav; do
    install -m 644 "$clip" "$release/streamdeck/speech/$(basename "$clip")"
done
"$python" -m compileall -q "$release/streamdeck"
systemctl start paperdrop-runtime.service
for attempt in {1..30}; do
    if curl -fsS http://127.0.0.1:8766/state > "$backup/post-install-state.json"; then
        systemctl is-active --quiet paperdrop-runtime.service
        trap - ERR
        echo "Recording timer installed. Original code retained at $backup"
        echo 'Automatic update settings were not changed.'
        exit 0
    fi
    sleep 1
done
false
