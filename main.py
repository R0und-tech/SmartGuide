"""
main.py
-------
Main loop:
  • every 5 seconds checks MotionDetector
  • on motion → take photo (OpenCV)
  • send photo to GigaChat-Pro
  • speak the description with Yandex SpeechKit
"""

import cv2
import time
import subprocess
from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import HumanMessage
from motion_detector import MotionDetector
from speechkit_tts import say_it, set_speechkit_key

# --------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------- #
GIGACHAT_CREDENTIALS = "ваш_ключ_здесь"          
SPEECHKIT_API_KEY = "ваш_api_ключ_здесь"        
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
# Text-to-Speech (Yandex SpeechKit)
# --------------------------------------------------------------------- #
set_speechkit_key(SPEECHKIT_API_KEY)

SPEECHKIT_VOICE = "oksana"         # oksana, jane, alena, filipp, ermil
SPEECHKIT_SPEED = "1.0"            # "0.1".."3.0"
SPEECHKIT_FMT = "lpcm"             # 'lpcm' (WAV) или 'oggopus'/'mp3'
SPEECHKIT_SR = 48000               # sample rate для lpcm

# --------------------------------------------------------------------- #
# Camera initialization
# --------------------------------------------------------------------- #
print("Initializing camera...")
cap = cv2.VideoCapture(CAMERA_INDEX)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1024)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 768)

time.sleep(2)

if not cap.isOpened():
    raise RuntimeError("FATAL: Cannot open camera! Check connection.")
print("Camera ready")

# Check first frame
ret, _ = cap.read()
if not ret:
    cap.release()
    raise RuntimeError("FATAL: Camera is opened but cannot grab frame")
print("First frame OK")

# --------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------- #
def take_photo() -> str:
    """Capture photo from camera and save to disk"""
    ret, frame = cap.read()
    if not ret:
        print("WARNING: Failed to grab frame")
        return None
    cv2.imwrite(PHOTO_PATH, frame)
    print("Photo saved →", PHOTO_PATH)
    return PHOTO_PATH


def ask_gigachat(photo_path: str) -> str:
    """
    Upload image to GigaChat and ask for description.
    Uses upload_file method (without base64).
    """
    try:
        # Открываем файл и загружаем в GigaChat
        with open(photo_path, "rb") as f:
            file_obj = llm.upload_file(f)
        
        # Запрос с прикреплённым файлом
        response = llm.invoke([
            HumanMessage(
                content=(
                    "Что ты видишь на этом фото? Начинай свой ответ так: Перед нами... "
                    "Не используй в своём ответе такие слова как снимок, фотография, изображение и подобные! "
                    "Это не фотография! Ты описываешь мне то, что ты реально видишь перед собой!"
                ),
                additional_kwargs={"attachments": [file_obj.id_]}
            )
        ])
        return response.content.strip()
    except Exception as e:
        print(f"GigaChat error: {e}")
        return "Не удалось распознать изображение."


def speak(text: str):
    """Speak text using Yandex SpeechKit"""
    print("Speaking:", text)
    try:
        audio_path = say_it(
            text,
            voice=SPEECHKIT_VOICE,
            speed=SPEECHKIT_SPEED,
            fmt=SPEECHKIT_FMT,
            sample_rate=SPEECHKIT_SR,
        )
        print("Audio saved:", audio_path)
    except Exception as e:
        print("TTS error:", e)


# --------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------- #
def main():
    detector = MotionDetector()
    time.sleep(1)
    print(f"\n✅ Ready! Checking every {CHECK_INTERVAL}s\n")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(CHECK_INTERVAL)
            
            if detector.is_moving():
                print("\n🚨 Motion detected!")
                path = take_photo()
                
                if path:
                    # Получаем описание от GigaChat
                    desc = ask_gigachat(path)
                    print(f"💬 GigaChat: {desc}")
                    
                    # Озвучиваем
                    speak(desc)
                    
                    # Удаляем фото после обработки
                    subprocess.run(["rm", PHOTO_PATH])
                else:
                    speak("Не удалось сделать снимок.")
            else:
                print(".", end="", flush=True)  # индикатор работы
                
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        cap.release()
        print("Camera released")

if __name__ == "__main__":
    main()
