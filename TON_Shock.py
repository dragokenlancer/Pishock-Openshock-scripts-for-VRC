import requests
from pythonosc.dispatcher import Dispatcher
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

# Select API: 'pishock' or 'openshock'
SHOCK_API = 'openshock'  #'openshock' or 'pishock'
# PiShock API credentials
API_KEY = ""
USER_KEY = ""
DEVICE_NAME = ""
CODE = ""

# OpenShock API credentials 
OPENSHOCK_URL = "https://api.openshock.app/2/shockers/control"
OPENSHOCK_TOKEN = ""
OPENSHOCK_DEVICE_ID = ""


def send_shock_pishock(op):
    url = "https://do.pishock.com/api/apioperate/"
    payload = {
        "Username": USER_KEY,
        "Name": DEVICE_NAME,
        "Apikey": API_KEY,
        "Code": CODE,
        "Op": op,  # 0 = shock, 1 = vibrate, 2 = beep
        "Duration": 1,  # seconds
        "Intensity": 20  # 1-100
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Shock sent via PiShock!")
    else:
        print("Failed to send shock (PiShock):", response.text)

def send_shock_openshock(op):
    url = OPENSHOCK_URL
    headers={
      "Content-Type": "application/json",
      "OpenShockToken": OPENSHOCK_TOKEN
    }
    payload={
      "shocks": [
        {
          "id": OPENSHOCK_DEVICE_ID,
          "type": op,
          "intensity": 20,
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

def send_shock(op):
    if SHOCK_API == 'pishock':
        if op == "shock":
            op = 0
        elif op == "vibrate":
            op = 1
        send_shock_pishock(op)
    elif SHOCK_API == 'openshock':
        if op == "shock":
            op = "shock"
        elif op == "vibrate":
            op = "vibrate"
        send_shock_openshock(op)
    else:
        print("Unknown SHOCK_API value.")

def value_handler(address, *args):
    #print(f"Value changed at {address}: {list(args)[0]}")
    if address == "/avatar/parameters/ToN_Damaged":
        last_damage = 0
        damage = list({args})[0]
        if damage[0] != 255:
            if damage[0] > last_damage:
                send_shock("vibrate")
        
    if address == "/avatar/parameters/ToN_DeathID":
        if list({args})[0][0] == 1:
            send_shock("shock")


dispatcher = Dispatcher()
dispatcher.set_default_handler(value_handler)

ip = "127.0.0.1"
port = 9000

server = BlockingOSCUDPServer((ip, port), dispatcher)
print(f"Listening for OSC messages on {ip}:{port}...")
server.serve_forever()