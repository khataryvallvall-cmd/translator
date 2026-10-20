"""
خادم صغير: يقدّم صفحة التطبيق + يولّد أصواتاً عصبية (Microsoft Neural) مجاناً.
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


async def synth(text: str, voice: str) -> bytes:
    comm = edge_tts.Communicate(text, voice, volume=VOLUME)
    buf = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    return bytes(buf)


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
    key = (lang, text)
    if key in _cache:
        _cache.move_to_end(key)
        data = _cache[key]
    else:
        try:
            data = asyncio.run(synth(text, VOICES[lang]))
        except Exception as e:  # noqa: BLE001
            print("TTS error:", e)
            abort(502)
        if not data:
            abort(502)
        _cache[key] = data
        if len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)
    return Response(data, mimetype="audio/mpeg", headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
