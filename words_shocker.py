

import speech_recognition as sr
import requests
import time, random
from pythonosc import udp_client, dispatcher, osc_server
import re
import os
import threading

"""
--packages--
PyAudio
python-osc
requests
SpeechRecognition

"""

# Select API: 'pishock' or 'openshock'
SHOCK_API = 'openshock'  #'openshock' or 'pishock'
WORD_CHOICE = 'common'  # 'common' or 'target'
CHAT_BOX = True  # Set to True to enable chat box updates

INTENSITY = 10  # Shock intensity (1-100)
MUTE = False  # Global mute parameter

# Interval (in minutes) to pick a new random word
WORD_REFRESH_INTERVAL_MINUTES = 25  # Change as needed

# PiShock API credentials
API_KEY = ""
USER_KEY = ""
DEVICE_NAME = ""
CODE = ""

# OpenShock API credentials 
OPENSHOCK_URL = "https://api.openshock.app/2/shockers/control"
OPENSHOCK_TOKEN = ""
OPENSHOCK_DEVICE_ID = ""



def load_shock_counter(filename="shock_counter.txt"):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return int(f.read().strip())
        except Exception:
            return 0
    return 0

def save_shock_counter(counter, filename="shock_counter.txt"):
    try:
        with open(filename, "w") as f:
            f.write(str(counter))
    except Exception:
        pass

def pick_target_word(word_choice, common_words, target_words):
    if word_choice == 'common':
        word = random.choice(common_words)
        return {word}
    return set(target_words)

def format_current_text(token, shocks, intensity, text):
    return f'Trigger word: "{token}"  \nShocks: {shocks} | intensity: {intensity}\n\n {text}'

def main():
    global INTENSITY, MUTE, SHOCK_API, CHAT_BOX
    shock_counter = load_shock_counter()
    shock_ctu = 0
    text = ""
    target_words = {"banana", "apple", "crack", "love", "good bye"}
    common_words = [
        "the", "be", "to", "of", "and", "in", "that", "have", "if", "a", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at", "princess", "bark"
    ]
    current_words = pick_target_word(WORD_CHOICE, common_words, target_words)
    current_text = format_current_text(list(current_words)[0], shock_counter, INTENSITY, text)

    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    errorCTU = 0
    base_shock = 15
    growth_factor = 5

    osc_client = None
    if CHAT_BOX:
        osc_client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

    # OSC server to listen for mute parameter
    def mute_handler(address, *args):
        global MUTE
        if args and args[0]:
            MUTE = bool(args[0])
            print(f"Mute set to: {MUTE}")

    osc_dispatcher = dispatcher.Dispatcher()
    osc_dispatcher.map("/avatar/parameters/MuteSelf", mute_handler)
    osc_server_instance = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9001), osc_dispatcher)
    osc_thread = threading.Thread(target=osc_server_instance.serve_forever)
    osc_thread.daemon = True
    osc_thread.start()

    print("Listening for words:", current_words)
    if CHAT_BOX:
        osc_client.send_message("/chatbox/input", [current_text, True])
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        last_word_refresh = time.time()
        while True:
            if WORD_CHOICE == 'common' and time.time() - last_word_refresh > WORD_REFRESH_INTERVAL_MINUTES * 60:
                current_words = pick_target_word(WORD_CHOICE, common_words, target_words)
                print(f"New target word: {list(current_words)[0]}")
                last_word_refresh = time.time()
                shock_ctu = 0
            audio = recognizer.listen(source)
            try:
                text = recognizer.recognize_google(audio).lower()
                print("You said:", text)
                detected = False
                for word in current_words:
                    if re.search(rf"\b{re.escape(word)}\b", text):
                        print(f"Detected word: {word}")
                        detected = True
                        break
                if detected:
                    if MUTE:
                        shock_counter += 1
                        send_shock()
                        save_shock_counter(shock_counter)
                        shock_ctu += 1
                        INTENSITY = base_shock + (growth_factor * shock_ctu)
                        print(f"-----------\nTotal shocks sent: {shock_counter} intensity: {INTENSITY}")
                    else:
                        print("Mute is enabled. No shock sent.")
                current_text = format_current_text(list(current_words)[0], shock_counter, INTENSITY, text)
                if CHAT_BOX:
                    osc_client.send_message("/chatbox/input", [current_text, True])
            except sr.UnknownValueError:
                errorCTU += 1
            except sr.RequestError:
                continue
            if errorCTU > 15:
                print("Too many errors, resetting recognizer...")
                recognizer.adjust_for_ambient_noise(source)
                errorCTU = 0
    if CHAT_BOX:
        osc_client.send_message("/chatbox/input", ["", True])

def send_shock_pishock():
    url = "https://do.pishock.com/api/apioperate/"
    payload = {
        "Username": USER_KEY,
        "Name": DEVICE_NAME,
        "Apikey": API_KEY,
        "Code": CODE,
        "Op": 0,  # 0 = shock, 1 = vibrate, 2 = beep
        "Duration": 1,  # seconds
        "Intensity": INTENSITY  # 1-100
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Shock sent via PiShock!")
    else:
        print("Failed to send shock (PiShock):", response.text)

def send_shock_openshock():
    url = OPENSHOCK_URL
    headers={
      "Content-Type": "application/json",
      "OpenShockToken": OPENSHOCK_TOKEN
    }
    payload={
      "shocks": [
        {
          "id": OPENSHOCK_DEVICE_ID,
          "type": "shock",
          "intensity": INTENSITY,
          "duration": 300,
          "exclusive": True
        }
      ],
      "customName": None
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print("Shock sent via OpenShock!")
    else:
        print("Failed to send shock (OpenShock):", response.text)

def send_shock():
    if SHOCK_API == 'pishock':
        send_shock_pishock()
    elif SHOCK_API == 'openshock':
        send_shock_openshock()
    else:
        print("Unknown SHOCK_API value.")

if __name__ == "__main__":
    main()

