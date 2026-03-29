import os
import base64
import time

import pyautogui
from groq import Groq
from api_key import TOKEN, API_KEY

client = Groq(api_key=API_KEY)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def zaira_olha():
    img_path = "zaira_eye.jpg"
    try:
        # Print em 720p (leve e nítido pro Llama 4)
        screenshot = pyautogui.screenshot()
        screenshot = screenshot.resize((1280, 720))
        screenshot = screenshot.convert("RGB")
        screenshot.save(img_path, "JPEG", quality=50)

        with open(img_path, "rb") as f:
            base64_img = base64.b64encode(f.read()).decode('utf-8')

        # Llama 4 Scout - O mestre da visão de 2026
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "O que tem na tela? Seja curto, grosso e técnico (dialeto dev)."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                ]
            }],
            max_tokens=60
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Erro na visão, naitchizin: {e}"
    finally:
        if os.path.exists(img_path): os.remove(img_path)