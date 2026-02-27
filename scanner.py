import os
import requests

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

def send_test():
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": "🚀 Scanner is LIVE and connected successfully!"
    }
    requests.post(url, json=payload)

if __name__ == "__main__":
    send_test()
