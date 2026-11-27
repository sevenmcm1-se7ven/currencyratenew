import requests

BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "-1001234567890"  # သင့် Group ရဲ့ Chat ID
MESSAGE_THREAD_ID = 6  # «အလုပ်အကိုင်များ» topic


def send_photo_to_job_topic(image_path: str, caption: str = ""):
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
  data = {
      "chat_id": CHAT_ID,
      "message_thread_id": MESSAGE_THREAD_ID,
      "caption": caption,
      "parse_mode": "HTML",
  }
  with open(image_path, "rb") as img:
    files = {"photo": img}
    response = requests.post(url, data=data, files=files)
  return response.json()


def send_message_to_job_topic(text: str):
  url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
  payload = {
      "chat_id": CHAT_ID,
      "message_thread_id": MESSAGE_THREAD_ID,
      "text": text,
      "parse_mode": "HTML",
  }
  response = requests.post(url, json=payload)
  return response.json()
