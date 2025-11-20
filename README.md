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

# Future Enhancement — Raspberry Pi SSH Integration

A planned extension adds remote execution via SSH:

### Planned Flow

```
PC Assistant → SSH → Raspberry Pi → Execute Script
```

### Implementation Outline

* Use `paramiko` or system `ssh`
* Add SSH config file with hostname, key path, credentials
* Extend `command_matcher` to include remote commands
* Build `pi_executor.py` to handle:

  * GPIO control
  * Sensors
  * Robotics
  * System management

### Example

```python
ssh.exec_command("python3 /home/pi/scripts/led_on.py")
```

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
```

---

# License

This documentation describes a technical research-oriented project intended for local experimentation and personal automation.
