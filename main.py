"""
main.py
-------
Main loop:
  • every 5 seconds checks MotionDetector
  • on motion → take photo (OpenCV)
  • send photo to GigaChat-Pro
  • speak the description with pyttsx3 (Russian voice)
"""

import cv2
import time
import subprocess
#import pyttsx3
from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import HumanMessage
from motion_detector import MotionDetector
from speechkit_tts import say_it, set_speechkit_key

# --------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------- #
GIGACHAT_CREDENTIALS = ""
CAMERA_INDEX = 0                   # 0 = default Raspberry Pi camera
PHOTO_PATH = "/tmp/image.jpg"
CHECK_INTERVAL = 5                 # seconds between motion checks

# --------------------------------------------------------------------- #
# GigaChat client
# --------------------------------------------------------------------- #
llm = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    temperature=0.1,
    verify_ssl_certs=False,
    model="GigaChat-Pro"
)

# --------------------------------------------------------------------- #
# Text-to-Speech (Russian)
# --------------------------------------------------------------------- #
# SpeechKit TTS настройки

set_speechkit_key("")

SPEECHKIT_VOICE = "oksana"   # популярные: oksana, jane, alena, filipp, ermil
SPEECHKIT_SPEED = "1.0"      # "0.1".."3.0"
SPEECHKIT_FMT   = "lpcm"     # 'lpcm' (WAV) или 'oggopus'/'mp3'
SPEECHKIT_SR    = 48000      # sample rate для lpcm

#tts = pyttsx3.init()
# Try to select a Russian voice (fallback to any available)
#voices = tts.getProperty('voices')
#for v in voices:
#    if 'ru' in v.id.lower() or 'russian' in v.name.lower():
#        tts.setProperty('voice', v.id)
#        break
#tts.setProperty('rate', 150)   # speech speed

# --- CAMERA ---
print("Initializing camera...")
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1024)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 768)
#cap.set(cv2.CAP_PROP_FPS, 30)

time.sleep(2)
if not cap.isOpened():
    raise RuntimeError("FATAL: Cannot open camera! Check connection.")
print("Camera ready")

# --- Check first frame ---
ret, _ = cap.read()
if not ret:
    cap.release()
    raise RuntimeError("FATAL: Camera is opened but cannot grab frame")
print("First frame OK")

# --------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------- #
def take_photo() -> str:
    ret, frame = cap.read()
    if not ret:
        print("WARNING: Failed to grab frame")
        return None
    cv2.imwrite(PHOTO_PATH, frame)
    print("Photo saved →", PHOTO_PATH)
    return PHOTO_PATH


def ask_gigachat(photo_path: str) -> str:
    """Upload image and ask GigaChat what is on it."""
    try:
        file_obj = llm.upload_file(open(photo_path, "rb"))
        response = llm.invoke([
            HumanMessage(
                content="Что ты видишь на этом фото? Начинай свой ответ так: Перед нами... Не используй в своем ответе такие слова как снимок, фотография, изображение и подобные! Это не фотография! Ты описываешь мне то, что ты реально видишь перед собой!",
                additional_kwargs={"attachments": [file_obj.id_]}
            )
        ])
        return response.content.strip()
    except Exception as e:
        return f"GigaChat error: {e}"


def speak(text: str):
    #tts.say(text)
    #tts.runAndWait()
    """Speak the text (blocking) via Yandex SpeechKit (REST)."""
    print("Speaking:", text)
    try:
        path = say_it(
            text,
            voice=SPEECHKIT_VOICE,
            speed=SPEECHKIT_SPEED,
            fmt=SPEECHKIT_FMT,
            sample_rate=SPEECHKIT_SR,
            # save_to="/tmp/tts.wav"  # можно задать явный путь
        )
        print("Audio saved:", path)
    except Exception as e:
        print("TTS error:", e)

# --------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------- #
def main():
    detector = MotionDetector()
    time.sleep(1)
    print(f"\nReady! Checking every {CHECK_INTERVAL}s\n")

    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            if detector.is_moving():
                print("Motion → capturing...")
                path = take_photo()
                if path:
                    desc = ask_gigachat(path)
                    print("GigaChat:", desc)
                    speak(desc)
                    subprocess.run(["rm", PHOTO_PATH])
                else:
                    speak("Camera error.")
            else:
                print("No motion")
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cap.release()
        print("Camera released")

if __name__ == "__main__":
    main()
