

import speech_recognition as sr
import requests
import time, random
from pythonosc import udp_client, dispatcher, osc_server
import re
import os
import threading
import json
import sys

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
base_shock = INTENSITY  # Base shock intensity for calculations
MUTE = True  # Global mute parameter
PAUSED = False  # Global pause flag
SHUTDOWN = False  # Global shutdown flag
CURRENT_TRIGGER_WORD = ""  # Current trigger word shown in control GUI

# Globals for OSC server so GUI can shut it down
OSC_SERVER_INSTANCE = None
OSC_THREAD = None

# Interval (in minutes) to pick a new random word
WORD_REFRESH_INTERVAL_MINUTES = 15  # Change as needed

# PiShock API credentials
API_KEY = ""
USER_KEY = ""
DEVICE_NAME = ""
CODE = ""

common_words = [
        "the", "be", "to", "of", "and", "in", "that", "have", "if", "a", "i",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at", "princess", "bark"
    ]

# Configuration file stored next to the script/executable
CONFIG_FILE = "words_shocker_config.json"

def _get_config_path():
    # When bundled by PyInstaller the executable path is used; otherwise use script path
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, CONFIG_FILE)

def load_config():
    """Load credentials and settings from the JSON config file (if present)."""
    global API_KEY, USER_KEY, DEVICE_NAME, CODE, base_shock, common_words
    global OPENSHOCK_URL, OPENSHOCK_TOKEN, OPENSHOCK_DEVICE_ID, SHOCK_API
    path = _get_config_path()
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        API_KEY = data.get('API_KEY', API_KEY)
        USER_KEY = data.get('USER_KEY', USER_KEY)
        DEVICE_NAME = data.get('DEVICE_NAME', DEVICE_NAME)
        CODE = data.get('CODE', CODE)
        SHOCK_API = data.get('SHOCK_API', SHOCK_API)
        OPENSHOCK_URL = data.get('OPENSHOCK_URL', globals().get('OPENSHOCK_URL', ''))
        OPENSHOCK_TOKEN = data.get('OPENSHOCK_TOKEN', globals().get('OPENSHOCK_TOKEN', ''))
        OPENSHOCK_DEVICE_ID = data.get('OPENSHOCK_DEVICE_ID', globals().get('OPENSHOCK_DEVICE_ID', ''))
        base_shock = data.get('INTENSITY', base_shock)
        WORD_REFRESH_INTERVAL_MINUTES = data.get('WORD_REFRESH_INTERVAL_MINUTES', WORD_REFRESH_INTERVAL_MINUTES)
        common_words = data.get('Word_list', common_words)
    except Exception:
        # ignore errors and continue with defaults
        pass

def save_config():
    global base_shock, WORD_REFRESH_INTERVAL_MINUTES, common_words
    """Save credentials and settings to the JSON config file next to the exe/script."""
    path = _get_config_path()
    data = {
        'SHOCK_API': SHOCK_API,
        'API_KEY': API_KEY,
        'USER_KEY': USER_KEY,
        'DEVICE_NAME': DEVICE_NAME,
        'CODE': CODE,
        'OPENSHOCK_URL': globals().get('OPENSHOCK_URL', ''),
        'OPENSHOCK_TOKEN': globals().get('OPENSHOCK_TOKEN', ''),
        'OPENSHOCK_DEVICE_ID': globals().get('OPENSHOCK_DEVICE_ID', ''),
        'INTENSITY': base_shock,
        'WORD_REFRESH_INTERVAL_MINUTES': WORD_REFRESH_INTERVAL_MINUTES,
        'Word_list': common_words,

    }
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# --- GUI: Allow runtime configuration of API keys and SHOCK_API ---
def show_config_gui():
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        print("tkinter not available; skipping GUI config")
        return

    def on_submit():
        global API_KEY, USER_KEY, DEVICE_NAME, CODE, SHOCK_API, DURATION
        global OPENSHOCK_URL, OPENSHOCK_TOKEN, OPENSHOCK_DEVICE_ID
        SHOCK_API = shock_api_var.get()
        if SHOCK_API == 'pishock':
            API_KEY = api_key_var.get().strip()
            USER_KEY = user_key_var.get().strip()
            DEVICE_NAME = device_name_var.get().strip()
            CODE = code_var.get().strip()
            DURATION = 1
        else:  # openshock
            OPENSHOCK_URL = openshock_url_var.get().strip()
            OPENSHOCK_TOKEN = openshock_token_var.get().strip()
            OPENSHOCK_DEVICE_ID = openshock_device_id_var.get().strip()
            DURATION = 300
        # persist to disk
        save_config()
        root.destroy()

    root = tk.Tk()
    root.title('Words Shocker - Configuration')

    frm = ttk.Frame(root, padding=12)
    frm.grid()

    ttk.Label(frm, text='SHOCK API:').grid(column=0, row=0, sticky='w')
    shock_api_var = tk.StringVar(value=SHOCK_API)
    shock_api_combo = ttk.Combobox(frm, textvariable=shock_api_var, values=['openshock', 'pishock'], state='readonly')
    shock_api_combo.grid(column=1, row=0)

    # PiShock fields
    ttk.Label(frm, text='API_KEY:').grid(column=0, row=1, sticky='w')
    # initialize variables from loaded config
    api_key_var = tk.StringVar(value=API_KEY)
    api_key_entry = ttk.Entry(frm, textvariable=api_key_var, width=40)
    api_key_entry.grid(column=1, row=1)

    ttk.Label(frm, text='USER_KEY:').grid(column=0, row=2, sticky='w')
    user_key_var = tk.StringVar(value=USER_KEY)
    user_key_entry = ttk.Entry(frm, textvariable=user_key_var, width=40)
    user_key_entry.grid(column=1, row=2)

    ttk.Label(frm, text='DEVICE_NAME:').grid(column=0, row=3, sticky='w')
    device_name_var = tk.StringVar(value=DEVICE_NAME)
    device_name_entry = ttk.Entry(frm, textvariable=device_name_var, width=40)
    device_name_entry.grid(column=1, row=3)

    ttk.Label(frm, text='CODE:').grid(column=0, row=4, sticky='w')
    code_var = tk.StringVar(value=CODE)
    code_entry = ttk.Entry(frm, textvariable=code_var, width=40)
    code_entry.grid(column=1, row=4)

    # OpenShock fields (start hidden if not selected)
    openshock_row = 6
    ttk.Label(frm, text='OPENSHOCK_URL:').grid(column=0, row=openshock_row, sticky='w')
    openshock_url_var = tk.StringVar(value=globals().get('OPENSHOCK_URL', ''))
    openshock_url_entry = ttk.Entry(frm, textvariable=openshock_url_var, width=40)
    openshock_url_entry.grid(column=1, row=openshock_row)

    ttk.Label(frm, text='OPENSHOCK_TOKEN:').grid(column=0, row=openshock_row+1, sticky='w')
    openshock_token_var = tk.StringVar(value=globals().get('OPENSHOCK_TOKEN', ''))
    openshock_token_entry = ttk.Entry(frm, textvariable=openshock_token_var, width=40)
    openshock_token_entry.grid(column=1, row=openshock_row+1)

    ttk.Label(frm, text='OPENSHOCK_DEVICE_ID:').grid(column=0, row=openshock_row+2, sticky='w')
    openshock_device_id_var = tk.StringVar(value=globals().get('OPENSHOCK_DEVICE_ID', ''))
    openshock_device_id_entry = ttk.Entry(frm, textvariable=openshock_device_id_var, width=40)
    openshock_device_id_entry.grid(column=1, row=openshock_row+2)

    # Function to toggle visibility based on selected API
    def update_visibility(event=None):
        api = shock_api_var.get()
        if api == 'openshock':
            # hide pishock entries
            api_key_entry.grid_remove()
            user_key_entry.grid_remove()
            device_name_entry.grid_remove()
            code_entry.grid_remove()
            # show openshock
            openshock_url_entry.grid()
            openshock_token_entry.grid()
            openshock_device_id_entry.grid()
        else:
            # show pishock entries
            api_key_entry.grid()
            user_key_entry.grid()
            device_name_entry.grid()
            code_entry.grid()
            # hide openshock
            openshock_url_entry.grid_remove()
            openshock_token_entry.grid_remove()
            openshock_device_id_entry.grid_remove()

    shock_api_combo.bind('<<ComboboxSelected>>', update_visibility)
    # Set initial visibility
    root.after(10, update_visibility)

    submit_btn = ttk.Button(frm, text='Apply and Close', command=on_submit)
    submit_btn.grid(column=0, row=5, columnspan=2, pady=(8,0))

    # center window and run
    root.eval('tk::PlaceWindow %s center' % root.winfo_toplevel())
    root.mainloop()


def start_control_gui():
    global PAUSED, SHUTDOWN, CURRENT_TRIGGER_WORD
    """Start a small tkinter GUI in a separate thread to control Pause/Resume and Quit.
    The GUI runs in a background daemon thread and polls `CURRENT_TRIGGER_WORD` to
    display the active trigger word.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        print("tkinter not available; skipping control GUI")
        return

    def gui_thread():
        def on_pause():
            global PAUSED
            PAUSED = True
            status_var.set('Paused')

        def on_resume():
            global PAUSED
            PAUSED = False
            status_var.set('Running')

        def on_quit():
            global SHUTDOWN
            SHUTDOWN = True
            try:
                root.destroy()
            except Exception:
                pass
            # try to gracefully stop OSC server if it's running
            try:
                if OSC_SERVER_INSTANCE is not None:
                    try:
                        OSC_SERVER_INSTANCE.shutdown()
                    except Exception:
                        pass
                    try:
                        OSC_SERVER_INSTANCE.server_close()
                    except Exception:
                        pass
                # join the osc thread briefly
                try:
                    if OSC_THREAD is not None and OSC_THREAD.is_alive():
                        OSC_THREAD.join(timeout=1.0)
                except Exception:
                    pass
            except Exception:
                pass
            # still ensure process exits if threads keep running
            try:
                os._exit(0)
            except Exception:
                pass

        root = tk.Tk()
        root.title('Words Shocker - Controls')

        frm = ttk.Frame(root, padding=8)
        frm.grid()

        status_var = tk.StringVar(value='Running')
        ttk.Label(frm, text='Status:').grid(column=0, row=0, sticky='w')
        ttk.Label(frm, textvariable=status_var).grid(column=1, row=0, sticky='w')

        # Current trigger word display
        ttk.Label(frm, text='Trigger Word:').grid(column=0, row=1, sticky='w')
        trigger_var = tk.StringVar(value=CURRENT_TRIGGER_WORD)
        trigger_label = ttk.Label(frm, textvariable=trigger_var, foreground='blue')
        trigger_label.grid(column=1, row=1, sticky='w')

        pause_btn = ttk.Button(frm, text='Pause', command=on_pause)
        pause_btn.grid(column=0, row=2, pady=(6,0))
        resume_btn = ttk.Button(frm, text='Resume', command=on_resume)
        resume_btn.grid(column=1, row=2, pady=(6,0))
        quit_btn = ttk.Button(frm, text='Quit', command=on_quit)
        quit_btn.grid(column=0, row=3, columnspan=2, pady=(8,0))

        # Keep this window small and on top
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass

        # Periodically refresh the trigger word from the global
        def refresh_trigger():
            try:
                trigger_var.set(CURRENT_TRIGGER_WORD or '')
            except Exception:
                pass
            root.after(500, refresh_trigger)

        root.after(500, refresh_trigger)
        try:
            root.eval('tk::PlaceWindow %s center' % root.winfo_toplevel())
        except Exception:
            pass
        root.mainloop()

    t = threading.Thread(target=gui_thread, daemon=True)
    t.start()
    #main()


# OpenShock API credentials 
OPENSHOCK_URL = "https://api.openshock.app/2/shockers/control"
OPENSHOCK_TOKEN = ""
OPENSHOCK_DEVICE_ID = ""


if SHOCK_API == 'openshock':
    DURATION = 300  # Duration in milliseconds for OpenShock
elif SHOCK_API == 'pishock':
    DURATION = 1  # Duration in seconds for PiShock

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
    global INTENSITY, MUTE, SHOCK_API, CHAT_BOX, CURRENT_TRIGGER_WORD
    shock_counter = load_shock_counter()
    shock_ctu = 0
    text = ""
    target_words = {"banana", "apple", "crack", "love", "good bye"}

    current_words = pick_target_word(WORD_CHOICE, common_words, target_words)
    current_text = format_current_text(list(current_words)[0], shock_counter, INTENSITY, text)
    CURRENT_TRIGGER_WORD = list(current_words)[0]

    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    errorCTU = 0
    base_shock = 10
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

    global OSC_SERVER_INSTANCE, OSC_THREAD
    osc_dispatcher = dispatcher.Dispatcher()
    osc_dispatcher.map("/avatar/parameters/MuteSelf", mute_handler)
    OSC_SERVER_INSTANCE = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 9001), osc_dispatcher)
    OSC_THREAD = threading.Thread(target=OSC_SERVER_INSTANCE.serve_forever)
    OSC_THREAD.daemon = True
    OSC_THREAD.start()

    print("Listening for words:", current_words)
    global PAUSED, SHUTDOWN, DURATION
    if CHAT_BOX:
        osc_client.send_message("/chatbox/input", [current_text, True])
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        last_word_refresh = time.time()
        while True:
            if SHUTDOWN:
                print('Shutdown requested, exiting main loop')
                break
            if WORD_CHOICE == 'common' and time.time() - last_word_refresh > WORD_REFRESH_INTERVAL_MINUTES * 60:
                current_words = pick_target_word(WORD_CHOICE, common_words, target_words)
                print(f"New target word: {list(current_words)[0]}")
                last_word_refresh = time.time()
                shock_ctu = 0
                CURRENT_TRIGGER_WORD = list(current_words)[0]
                if SHOCK_API == 'openshock':
                    DURATION = 300  # Duration in milliseconds for OpenShock
                elif SHOCK_API == 'pishock':
                    DURATION = 1  # Duration in seconds for PiShock
            audio = recognizer.listen(source, phrase_time_limit = 5)
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
                        print(f"Shock CTU: {shock_ctu}")
                        INTENSITY = base_shock + (growth_factor * shock_ctu)
                        print(f"-----------\nTotal shocks sent: {shock_counter} intensity: {INTENSITY}  DurationL: {DURATION}")
                    else:
                        print("Mute is enabled. No shock sent.")
                current_text = format_current_text(list(current_words)[0], shock_counter, INTENSITY, text)
                if not MUTE:
                    current_text = format_current_text(list(current_words)[0], shock_counter, INTENSITY, "MUTED CURRENTLY!!")
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
        "Duration": DURATION,# seconds
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
          "duration": DURATION,
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
    global INTENSITY, DURATION
    if SHOCK_API == 'pishock':
        if INTENSITY > 100:
            INTENSITY = 100
            DURATION += 1
        send_shock_pishock()
    elif SHOCK_API == 'openshock':
        if INTENSITY > 100:
            INTENSITY = 100
            DURATION += 100
        send_shock_openshock()
    else:
        print("Unknown SHOCK_API value.")

if __name__ == "__main__":
    # load previously saved config (if any) before showing GUIs
    try:
        load_config()
    except Exception:
        pass
    show_config_gui()
    start_control_gui()
    main()
    

