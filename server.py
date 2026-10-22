"""
خادم صغير: يقدّم صفحة التطبيق + يولّد أصواتاً عصبية (Microsoft Neural) مجاناً.
الصوت يُرسَل مباشرة أثناء توليده (Streaming) فيبدأ النطق بسرعة.
التشغيل:  pip install -r requirements.txt  ثم  python server.py
"""
import asyncio
import os
from collections import OrderedDict

import edge_tts
from flask import Flask, Response, abort, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=None)

# ✏️ غيّر الأصوات من هنا
VOICES = {
    "zh": "zh-CN-YunyangNeural",    # صيني فصيح بصوت رجل واضح. بدائل رجالية: zh-CN-YunjianNeural (قوي), zh-CN-YunxiNeural (شاب)
    "ar": "ar-SA-HamedNeural",      # عربي فصيح (ذكر). بديل: ar-SA-ZariyahNeural (أنثى), ar-EG-SalmaNeural
}

# ✏️ مستوى الصوت: من -50% إلى +100% (الأعلى قد يشوّه الصوت قليلاً)
VOLUME = "+50%"

_cache = OrderedDict()
CACHE_MAX = 60


def audio_stream(text: str, voice: str):
    """يُنتج أجزاء الصوت واحداً تلو الآخر بمجرد وصولها من Microsoft."""
    loop = asyncio.new_event_loop()
    agen = edge_tts.Communicate(text, voice, volume=VOLUME).stream()
    try:
        while True:
            try:
                chunk = loop.run_until_complete(agen.__anext__())
            except StopAsyncIteration:
                break
            if chunk["type"] == "audio":
                yield chunk["data"]
    finally:
        try:
            loop.run_until_complete(agen.aclose())
        except Exception:  # noqa: BLE001
            pass
        loop.close()


@app.after_request
def add_cors(resp):
    # للسماح للصفحة المستضافة في مكان آخر (GitHub Pages) بطلب الصوت
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.get("/health")
def health():
    return "ok"


@app.get("/")
def index():
    return send_from_directory(HERE, "index.html")


@app.get("/tts")
def tts():
    text = (request.args.get("text") or "").strip()[:1500]
    lang = request.args.get("lang", "zh")
    if not text or lang not in VOICES:
        abort(400)

    headers = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
    key = (lang, text)

    if key in _cache:
        _cache.move_to_end(key)
        return Response(_cache[key], mimetype="audio/mpeg", headers=headers)

    gen = audio_stream(text, VOICES[lang])
    try:
        first = next(gen)          # ننتظر أول جزء فقط؛ إن فشل نرجع خطأ ليعمل الصوت الاحتياطي
    except Exception as e:  # noqa: BLE001
        print("TTS error:", e)
        abort(502)

    def body():
        parts = [first]
        yield first
        for chunk in gen:
            parts.append(chunk)
            yield chunk
        _cache[key] = b"".join(parts)
        if len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)

    return Response(body(), mimetype="audio/mpeg", headers=headers)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
