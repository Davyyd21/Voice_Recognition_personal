#librarii
import sounddevice as sd
import numpy as np
import queue
import threading
import time
import subprocess
from faster_whisper import WhisperModel
from collections import deque
from command_matcher import load_commands, find_best_match
#import os
import sys
import torch
import paho.mqtt.client as mqtt

#variabile globale
WAKE_WORD = "garmin"
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5
PAUSE_THRESHOLD = 1.0
MIN_COMMAND_DURATION = 1.0
DEVICE_INDEX = None
WAKE_WORD_DELAY = 1.2
WAKE_DEBOUNCE = 2.0

COMMANDS_CSV = "commands.csv"

audio_queue = queue.Queue()
rolling_buffer = deque(maxlen=int(3 * SAMPLE_RATE))
command_buffer = []
recording = False
wake_detected = False
last_speech_time = time.time()
command_start_delay = 0.0
buffer_lock = threading.Lock()
last_wake_time = 0
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

#beep la wake word
def play_beep():
    duration = 0.2
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = 0.3 * np.sin(2 * np.pi * 1000 * t)
    sd.play(tone, samplerate=SAMPLE_RATE)
    sd.wait()

#recunoaste daca un array este vorbit sau doar noise
def is_speech(chunk, threshold=0.01):
    return np.mean(np.abs(chunk)) > threshold

#reseteaza variabilele pentru recording
def reset_recording():
    global command_buffer, wake_detected, recording
    command_buffer = []
    wake_detected = False
    recording = False

#incarcare model whisper
print("Loading Whisper...")
try:
    print("Is cuda avalable: ",torch.cuda.is_available(),"version",torch.version.cuda)
    device_1 = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type_1 = "float16" if device_1 == "cuda" else "int8"
    print("Using device: ", device_1)
    model = WhisperModel("tiny.en", device=device_1, compute_type=compute_type_1)

    print("Whisper model loaded successfully.")
except Exception as e:
    print("Error loading model:", e)
    sys.exit(1)

#incarcare comenzi
var2act, var_vec = load_commands(COMMANDS_CSV)
if not var_vec:
    print("No data loaded. Exiting.")
    sys.exit(1)
else:
    print(f"Loaded {len(var_vec)} variants from {COMMANDS_CSV}")

#functie detectie wake word
def detect_wake_word(audio):
    global wake_detected, recording, command_start_delay, last_wake_time
    now = time.time()
    if wake_detected or now - last_wake_time < WAKE_DEBOUNCE:
        return
    try:
        segments, _ = model.transcribe(
            np.array(audio, dtype=np.float32),
            language="en",
            beam_size=1,
            vad_filter=True
        )
        text = " ".join([seg.text for seg in segments if hasattr(seg, "text")]).lower()
        if WAKE_WORD in text:
            wake_detected = True
            recording = True
            command_start_delay = time.time() + WAKE_WORD_DELAY
            command_buffer.extend(audio[-SAMPLE_RATE:])
            last_wake_time = now
            print(f"\n[WAKE WORD DETECTED: {WAKE_WORD.upper()}]")
            threading.Thread(target=play_beep, daemon=True).start()
            with buffer_lock:
                rolling_buffer.clear()
            with audio_queue.mutex:
                audio_queue.queue.clear()
    except Exception as e:
        print("Wake-word error:", e)

#callback adaugare audio in coada
def audio_callback(indata, frames, time_info, status):
    if status:
        print("Audio status:", status)
    chunk = indata.copy().flatten().astype(np.float32)
    audio_queue.put(chunk)

#transcribe command+afisare best match
def transcribe_command():
    if not command_buffer:
        return
    audio = np.array(command_buffer, dtype=np.float32)
    print("Transcribing command...")
    try:
        segments, _ = model.transcribe(
            audio,
            language="en",
            beam_size=3,
            vad_filter=True
        )
        text = " ".join([seg.text for seg in segments if hasattr(seg, "text")]).lower()
        text = text.replace(WAKE_WORD, "").strip()
        if not text:
            print("Empty command")
            reset_recording()
            return
        print(f"Command: '{text}'")
        result = find_best_match(text, var2act,var_vec, cutoff=70)
        if result:
            client.connect(host="192.168.1.139")
            action, score = result
            print(f"Match '{action}' (score: {score:.1f}%)")
            device, state = action.split(" ")
            client.publish(f"gpio/{device}", f"{state}")
            try:
                subprocess.Popen(action, shell=True)
            except Exception as e:
                print("Execution error:", e)
        else:
            print("No matching command found.")
    except Exception as e:
        print("Transcription error:", e)
    reset_recording()

#worker-thread care integreaza si uneste toate functiile de transcribe
def worker():
    global last_speech_time
    print(f"Say '{WAKE_WORD}' to activate the assistant...\n")
    while True:
        chunk = audio_queue.get()
        if chunk is None:
            break
        with buffer_lock:
            rolling_buffer.extend(chunk)
        if not wake_detected and len(rolling_buffer) >= SAMPLE_RATE*0.5:
            threading.Thread(target=detect_wake_word, args=(list(rolling_buffer),), daemon=True).start()
        if wake_detected:
            current_time = time.time()
            if current_time < command_start_delay:
                command_buffer.extend(chunk)
                last_speech_time = current_time
                continue
            command_buffer.extend(chunk)
            if is_speech(chunk):
                last_speech_time = current_time
            elif current_time - last_speech_time > PAUSE_THRESHOLD:
                if len(command_buffer) > SAMPLE_RATE*MIN_COMMAND_DURATION:
                    transcribe_command()
                reset_recording()
            if len(command_buffer) > SAMPLE_RATE*15:
                transcribe_command()
                reset_recording()

#functia main a programului
def main():
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
            callback=audio_callback,
            blocksize=int(CHUNK_DURATION * SAMPLE_RATE),
            device=DEVICE_INDEX
        )
        with stream:
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            print("System active. Waiting for commands...\n")
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting...")
        audio_queue.put(None)
    except Exception as e:
        print("Stream error:", e)
        audio_queue.put(None)

if __name__ == "__main__":
    main()
