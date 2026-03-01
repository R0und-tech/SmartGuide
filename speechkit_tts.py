# speechkit_tts.py
"""
Лёгкий офлайн-клиент под Raspberry Pi Zero для Яндекс SpeechKit TTS (без SDK).
- Никаких grpcio/protobuf: только requests из std. репозитория.
- По умолчанию просит формат lpcm и упаковывает в WAV (играет даже aplay).
- Если есть PulseAudio/paplay — можно включить oggopus/MP3 ради меньшего размера.

Использование:
    from speechkit_tts import say_it, set_speechkit_key
    set_speechkit_key("YA...API_KEY...")
    say_it("Привет, это тест!")

Либо:
    say_it("...", api_key="YA...", voice="oksana")
"""

import os
import io
import wave
import shutil
import tempfile
import subprocess
from typing import Optional

try:
    import requests
except ImportError as e:
    raise SystemExit("Требуется пакет requests. Установи: sudo apt install -y python3-requests") from e

_SPEECHKIT_API_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
_API_KEY_ENV = ""

_default_config = {
    "voice": "oksana",        # jane | alena | oksana | filipp | ermil ...
    "lang":  "ru-RU",
    "speed": "1.0",           # 0.1..3.0 (строка по требованиям API)
    "format": "lpcm",         # lpcm | oggopus | mp3
    "sample_rate": 48000,     # обязателен для lpcm
}

def set_speechkit_key(api_key: str) -> None:
    """Задай ключ через код (иначе возьмётся из env YANDEX_SPEECHKIT_API_KEY)."""
    os.environ[_API_KEY_ENV] = api_key

def _get_api_key(explicit_key: Optional[str]) -> str:
    key = explicit_key or os.getenv(_API_KEY_ENV)
    if not key:
        raise RuntimeError(
            "Не задан API-ключ SpeechKit. Передай api_key=... в say_it() "
            "или вызови set_speechkit_key('YA...'), или установи переменную окружения "
            f"{_API_KEY_ENV}."
        )
    return key

def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def _lpcm_to_wav_bytes(lpcm_data: bytes, sample_rate: int = 48000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Упаковать raw 16-bit LE PCM в WAV."""
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)  # 16-бит = 2 байта
        wf.setframerate(sample_rate)
        wf.writeframes(lpcm_data)
    return bio.getvalue()

def _play_file(path: str) -> None:
    """
    Проиграть файл «чем есть».
    Предпочтения:
      1) paplay (PulseAudio)
      2) aplay (ALSA, WAV/PCM)
      3) ffplay (если установлен)
    Иначе просто оставим файл на диске.
    """
    if _have("paplay"):
        subprocess.run(["paplay", path], check=False)
    elif _have("aplay"):
        subprocess.run(["aplay", path], check=False)
    elif _have("ffplay"):
        subprocess.run(["ffplay", "-nodisp", "-autoexit", path], check=False)
    else:
        print(f"Файл сохранён: {path} (нечем воспроизвести автоматически)")

def say_it(
    text: str,
    *,
    api_key: Optional[str] = None,
    voice: str = _default_config["voice"],
    lang: str = _default_config["lang"],
    speed: str = _default_config["speed"],
    fmt: str = _default_config["format"],      # 'lpcm' | 'oggopus' | 'mp3'
    sample_rate: int = _default_config["sample_rate"],
    save_to: Optional[str] = None,             # путь для сохранения (опционально)
) -> str:
    """
    Синтезировать и воспроизвести речь. Возвращает путь к сохранённому файлу.
    - На Pi Zero безопаснее fmt='lpcm' (запишем WAV и проиграем aplay/paplay).
    - Если у тебя PulseAudio и хочется компактности — передай fmt='oggopus' (тогда нужен paplay/ffplay).
    """
    key = _get_api_key(api_key)

    headers = {"Authorization": f"Api-Key {key}"}
    data = {"text": text, "lang": lang, "voice": voice, "speed": speed, "format": fmt}

    if fmt == "lpcm":
        data["sampleRateHertz"] = str(sample_rate)

    resp = requests.post(_SPEECHKIT_API_URL, headers=headers, data=data, timeout=90)
    if resp.status_code != 200:
        # Попробуем вытащить текст ошибки
        raise RuntimeError(f"SpeechKit TTS HTTP {resp.status_code}: {resp.text[:500]}")

    # Подготовим байты для проигрывания/сохранения
    if fmt == "lpcm":
        audio_bytes = _lpcm_to_wav_bytes(resp.content, sample_rate=sample_rate)
        ext = "wav"
    elif fmt == "oggopus":
        audio_bytes = resp.content
        ext = "ogg"
    elif fmt == "mp3":
        audio_bytes = resp.content
        ext = "mp3"
    else:
        raise ValueError("Неверный fmt: используй 'lpcm', 'oggopus' или 'mp3'.")

    # Куда сохраняем
    if save_to is None:
        tmpdir = tempfile.gettempdir()
        save_to = os.path.join(tmpdir, f"speechkit_tts_out.{ext}")

    with open(save_to, "wb") as f:
        f.write(audio_bytes)

    # Воспроизведение
    _play_file(save_to)
    return save_to


# --- Пример прямого запуска файла ---
if __name__ == "__main__":
    # 1) задайте ключ через env:  export YANDEX_SPEECHKIT_API_KEY=YA...
    #    или ниже через set_speechkit_key("YA...")
    # set_speechkit_key("YA...")

    path = say_it("Привет! Проверка связи с Raspberry Pi Zero.",
                  fmt="lpcm",   # или "oggopus" если есть paplay
                  voice="oksana",
                  speed="1.0")
    print("Сохранено:", path)

