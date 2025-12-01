# Voice Recognition Personal Assistant — Technical Documentation

This project implements a **fully local, wake‑word‑activated voice assistant** built in Python. It uses **Faster Whisper** for real‑time speech recognition and **RapidFuzz** for high‑accuracy fuzzy matching between transcribed commands and a list of command variants defined in a CSV file.

The system is optimized for low latency, continuous audio streaming, robust wake‑word detection, and modular command handling. A future expansion will add **SSH-based remote execution** on a Raspberry Pi for hardware control and home automation.

---

# System Architecture

```
 ┌──────────────────────────────────────────────────────────┐
 │                         MAIN LOOP                        │
 │  - Audio streaming from microphone                       │
 │  - Wake-word detection ("garmin")                        │
 │  - Command segmentation & buffering                      │
 └───────────────┬──────────────────────────────────────────┘
                 │
                 ▼
       ┌────────────────────┐
       │  Faster Whisper    │
       │  Speech-to-Text    │
       └────────────────────┘
                 │ text
                 ▼
       ┌────────────────────┐
       │  RapidFuzz Matcher │
       │  Command Mapping   │
       └────────────────────┘
                 │ action
                 ▼
       ┌────────────────────┐
       │ Local Execution    │
       │ subprocess.Popen() │
       └────────────────────┘
                 │
                 ▼
       (Future) SSH → Raspberry Pi → Run scripts
```

---

# Audio Processing Pipeline

The audio system is built around:

* `sounddevice.InputStream()` for real-time audio capture
* A **worker thread** that processes audio chunks
* A **rolling buffer** used for wake‑word scanning
* A dedicated **command buffer** used to accumulate speech after activation

### Key Parameters

| Variable                    | Meaning                                     |
| --------------------------- | ------------------------------------------- |
| `SAMPLE_RATE=16000`         | Model‑friendly sample rate                  |
| `CHUNK_DURATION=0.5s`       | Audio chunk size                            |
| `PAUSE_THRESHOLD=1.0s`      | Silence that ends command                   |
| `MIN_COMMAND_DURATION=1.0s` | Minimum speech duration required            |
| `WAKE_WORD="garmin"`        | Activation phrase                           |
| `WAKE_WORD_DELAY=1.2s`      | Delay after wake word until command capture |

---

# 💤 Wake-Word Detection

Wake‑word detection is performed by running Faster Whisper on a rolling 1.5–3 second buffer.

### Steps:

1. Rolling audio buffer updated by `audio_callback`
2. Worker thread calls `detect_wake_word()` asynchronously
3. Segments are transcribed with VAD enabled
4. If wake word is found:

   * Assistant enters **recording mode**
   * Beep sound played
   * Command buffer initialized
   * Debounce applied to avoid double triggers

### Snippet

```python
def detect_wake_word(audio):
    segments, _ = model.transcribe(audio, vad_filter=True)
    text = " ".join(seg.text for seg in segments).lower()
    if WAKE_WORD in text:
        wake_detected = True
```

---

# Command Recognition

Once recording is active:

* All speech is accumulated in `command_buffer`
* Silence is measured using `is_speech()`
* When silence exceeds `PAUSE_THRESHOLD`, the assistant transcribes the full buffer

### Transcription

```python
segments, _ = model.transcribe(audio, beam_size=3, vad_filter=True)
text = " ".join(seg.text for seg in segments).lower()
```

Wake‑word is removed from the command if present:

```python
text = text.replace(WAKE_WORD, "").strip()
```

---

# Command Matching (RapidFuzz)

Commands are defined in `commands.csv` with the following schema:

```
command_key,variants,action
```

Example:

```
turn_on_led,turn on led|activate led|...,echo "LED ON"
```

### Loading Commands

```python
var2act, variants = load_commands("commands.csv")
```

* `var2act` maps each phrase variant → action
* `variants` is a flat list used by RapidFuzz

### Matching

```python
result = process.extractOne(text, variants, score_cutoff=cutoff)
```

* The best matching variant above `cutoff` (default 70%) is selected
* The associated action is executed via `subprocess.Popen()`

---

# Command Execution

When a command is matched:

```python
subprocess.Popen(action, shell=True)
```

This allows executing:

* Shell commands
* Python scripts
* Bash scripts
* External tools

### Examples (from CSV)

| Intent            | Action           |
| ----------------- | ---------------- |
| “turn on led”     | `echo "LED ON"`  |
| “shutdown”        | `shutdown now`   |
| “cpu temperature” | `coolercontrol&` |

---

# File Structure

Suggested repository layout:

```
Voice_Recognition_personal/
├── main.py
├── command_matcher.py
├── commands.csv
├── models/            # whisper model cache
├── utils/             # future modules
└── README.md
```

---

# Running the Project

Install dependencies:

```bash
pip install sounddevice numpy faster-whisper rapidfuzz torch
```

Run assistant:

```bash
python main.py

---

# ✅ MQTT-based Raspberry Pi integration (new)

This repository now supports forwarding recognized voice commands over MQTT to a Raspberry Pi so the Pi can perform real hardware actions (GPIO). Two scripts are included:

- `main_1.0.py` — still performs recognition locally but now publishes a JSON payload to an MQTT topic when a command is matched.
- `pi_mqtt_subscriber.py` — run this on the Raspberry Pi; it subscribes to the topic and runs mapped GPIO actions (uses gpiozero).

How it works:

1. The assistant recognizes a command variant (from `commands.csv`).
2. Instead of — or in addition to — running the local `action` command, it publishes a JSON payload like:

  {
    "command": "turn_on_led",
    "action": "echo \"LED ON\"",
    "score": 93.4
  }

3. The Pi listener receives the message and runs the mapped GPIO behavior.

Quick start (recommended setup):

1. Install Mosquitto on the Raspberry Pi as a broker (or run a broker on the laptop):

  ```bash
  sudo apt update && sudo apt install -y mosquitto mosquitto-clients
  sudo systemctl enable --now mosquitto
  ```

2. On the Raspberry Pi, install the Python requirements and start the subscriber:

  Option A — manual (pip3):

  ```bash
  # ensure pip for python3 is installed, then install requirements
  sudo apt update
  sudo apt install -y python3-pip
  pip3 install -r requirements.txt

  # Run the subscriber (edit PIN_CONFIG in pi_mqtt_subscriber.py first to match your wiring)
  python3 pi_mqtt_subscriber.py
  ```

  Option B — use the provided helper script (recommended):

  ```bash
  chmod +x ./scripts/install_pi_requirements.sh
  ./scripts/install_pi_requirements.sh
  python3 pi_mqtt_subscriber.py
  ```

  Common fixes if you see ModuleNotFoundError (e.g. 'No module named paho'):
  - Make sure you installed system pip for Python 3 (sudo apt install python3-pip)
  - Use `pip3 install -r requirements.txt` on the Pi
  - Or run the included installer script `./scripts/install_pi_requirements.sh`

  - If the broker is remote, set MQTT_BROKER environment variable (e.g. export MQTT_BROKER="192.168.1.42").

3. On your laptop (voice recognition computer) set the broker and optionally topic, then run the assistant

  ```bash
  export MQTT_BROKER=192.168.1.42   # set to Pi's IP or hostname
  export MQTT_PORT=1883
  export MQTT_TOPIC=voice/commands
  python3 main_1.0.py

If your Raspberry Pi is at 192.168.1.139 (as you mentioned), you can use the provided convenience scripts:

On your laptop, run the assistant pre-configured to publish to that Pi:

```bash
./scripts/run_with_pi.sh
```

If you'd rather test only MQTT connectivity first, you can run the included test publisher (defaults to localhost):

```bash
# Publish a test message to a Pi located at 192.168.1.139
python3 ./scripts/test_mqtt_publish.py 192.168.1.139 1883 voice/commands
```

Or with mosquitto_pub:

```bash
mosquitto_pub -h 192.168.1.139 -t voice/commands -m '{"command":"turn_on_led","action":"echo "LED ON""}'
```
  ```

Notes & tips:

- `pi_mqtt_subscriber.py` includes a `PIN_CONFIG` mapping at the top — change those pins to match your wiring.
- The subscriber uses gpiozero and is designed to run on Raspberry Pi OS.
- For debugging you can publish test messages using `mosquitto_pub`:

  ```bash
  mosquitto_pub -h <broker> -t voice/commands -m '{"command":"turn_on_led","action":"echo \"LED ON\""}'
  ```

Security:

- This example uses an unauthenticated broker (local network). For production, secure Mosquitto with TLS and authentication.

```

---

# License

This documentation describes a technical research-oriented project intended for local experimentation and personal automation.
