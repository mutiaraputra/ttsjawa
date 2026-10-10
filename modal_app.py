"""Backend inferensi TTS Bahasa Indonesia / Jawa / Sunda di Modal.com.

Frontend statisnya di-deploy terpisah ke Vercel dan memanggil endpoint ini lewat
HTTPS. Alasannya: torch + coqui-tts + checkpoint 330 MB terlalu besar dan terlalu
lambat cold start-nya untuk Vercel Functions.

Deploy ke Modal:
    modal secret create ttsjawa TTS_ACCESS_TOKEN=<kode-rahasia>
    modal deploy modal_app.py

Endpoint yang dihasilkan:
    https://mutiarakom--ttsjawa.modal.run

Uji di mesin lokal tanpa Modal (untuk pengembangan frontend):
    python modal_app.py --lokal
"""

import io
import json
import os

import modal

# Path di dalam image Modal. Harus absolut bergaya POSIX karena dipakai oleh
# image.add_local_dir(). Untuk menjalankan berkas ini di mesin lokal, pakai
# environment variable TTSJAWA_* (lihat kelas MesinTTS).
ASSETS = "/root/assets"
MODEL_NAME = "checkpoint_1260000-inference.pth"
MODEL_URL = f"https://github.com/Wikidepia/indonesian-tts/releases/download/v1.2/{MODEL_NAME}"

# torch di-pin 2.6: mulai 2.9 coqui-tts mewajibkan torchcodec untuk audio IO.
# transformers di-pin <5: coqui-tts 0.27.5 masih mengimpor isin_mps_friendly yang
# sudah dihapus di transformers 5.x.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ca-certificates", "wget", "libsndfile1")
    .pip_install(
        ["torch==2.6.0+cpu", "torchaudio==2.6.0+cpu"],
        extra_index_url="https://download.pytorch.org/whl/cpu",
    )
    .pip_install([
        "coqui-tts==0.27.5",
        "transformers>=4.57,<5",
        "librosa<1.0",
        "onnxruntime",
        "nltk",
        "sacremoses",
        "fastapi",
    ])
    .run_commands(f"mkdir -p {ASSETS} && wget -q -O {ASSETS}/{MODEL_NAME} {MODEL_URL}")
    .env({"PYTHONPATH": ASSETS})
    .add_local_dir("g2p_id", remote_path=f"{ASSETS}/g2p_id")
)

app = modal.App("ttsjawa")

# Pembicara yang benar-benar tersedia di checkpoint v1.2. Kolom `bahasa`
# menentukan teks mana yang pelafalannya cocok, karena model ini tidak punya
# embedding bahasa — aksennya melekat pada pembicara.
SPEAKERS = [
    {"id": "wibowo", "nama": "Wibowo", "deskripsi": "Suara jantan berwibawa", "bahasa": "id"},
    {"id": "ardi", "nama": "Ardi", "deskripsi": "Suara lembut dan hangat", "bahasa": "id"},
    {"id": "gadis", "nama": "Gadis", "deskripsi": "Suara perempuan yang merdu", "bahasa": "id"},
    {"id": "JV-00264", "nama": "Juminten", "deskripsi": "Suara perempuan Jawa", "bahasa": "jv"},
    {"id": "SU-00060", "nama": "Asep", "deskripsi": "Suara lelaki Sunda", "bahasa": "su"},
]

BAHASA = {"id": "Indonesia", "jv": "Jawa", "su": "Sunda"}

MAX_TEKS = 1000
KECEPATAN_MIN = 0.1
KECEPATAN_MAX = 1.99


class MesinTTS:
    """Pipeline normalisasi teks -> G2P -> VITS, menghasilkan berkas WAV."""

    def __init__(self):
        # Di dalam image Modal semuanya berada di bawah ASSETS. Di mesin lokal
        # path-nya berbeda, jadi semuanya bisa ditimpa lewat TTSJAWA_*.
        assets = os.environ.get("TTSJAWA_ASSETS", ASSETS)
        self.model_file = os.environ.get("TTSJAWA_MODEL", f"{assets}/{MODEL_NAME}")
        self.config_src = f"{assets}/g2p_id/data/config.json"
        self.speakers_file = f"{assets}/g2p_id/data/speakers.pth"
        self.config_file = os.environ.get("TTSJAWA_CONFIG", "/tmp/tts-config.json")

        self.syn = None
        self.g2p = None
        self.sample_rate = None

    def muat(self):
        from TTS.utils.synthesizer import Synthesizer

        from g2p_id import G2P
        from g2p_id.scripts.normalize import text_normalization

        self.text_normalization = text_normalization
        self.g2p = G2P()
        self._tulis_config()
        self.syn = Synthesizer(
            tts_checkpoint=self.model_file,
            tts_config_path=self.config_file,
            use_cuda=False,
        )
        self.sample_rate = self.syn.output_sample_rate

    def _tulis_config(self):
        """Checkpoint lama menyimpan path speakers.pth relatif terhadap mesin
        pembuatnya, dan Synthesizer hanya membaca path itu dari config. Jadi
        config ditulis ulang ke lokasi yang bisa ditulis."""
        with open(self.config_src, encoding="utf8") as f:
            config = json.load(f)
        config["speakers_file"] = self.speakers_file
        config.setdefault("model_args", {})["speakers_file"] = self.speakers_file
        with open(self.config_file, "w", encoding="utf8") as f:
            json.dump(config, f)

    def sintesis(self, teks: str, pembicara: str, kecepatan: float) -> bytes:
        if pembicara not in {s["id"] for s in SPEAKERS}:
            raise ValueError(f"Pembicara tidak dikenal: {pembicara}")

        # VITS mengatur durasi lewat length_scale: makin besar makin lambat.
        self.syn.tts_model.length_scale = 1.0 / kecepatan

        fonem = self.g2p(self.text_normalization(teks))
        samples = self.syn.tts(fonem, speaker_name=pembicara)

        # Synthesizer.save_wav menerima list maupun tensor dan menormalkannya
        # ke int16, persis seperti yang dilakukan CLI tts_drat.
        buf = io.BytesIO()
        self.syn.save_wav(samples, buf)
        return buf.getvalue()


def buat_web(mesin: MesinTTS):
    """Bangun aplikasi FastAPI yang dilayani sebagai web endpoint Modal."""
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response
    from pydantic import BaseModel, Field

    token_valid = os.environ.get("TTS_ACCESS_TOKEN", "")

    class Permintaan(BaseModel):
        teks: str = Field(min_length=1, max_length=MAX_TEKS)
        pembicara: str = "ardi"
        kecepatan: float = Field(default=1.0, ge=KECEPATAN_MIN, le=KECEPATAN_MAX)

    def cek_token(diterima):
        if token_valid and diterima != token_valid:
            raise HTTPException(status_code=401, detail="Kode akses tidak cocok.")

    web = FastAPI(title="TTS Jawa Backend", docs_url=None, redoc_url=None)
    web.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @web.get("/healthz")
    def healthz():
        return {
            "status": "siap",
            "sample_rate": mesin.sample_rate,
            "pembicara": [s["id"] for s in SPEAKERS],
            "auth_aktif": bool(token_valid),
        }

    @web.get("/speakers")
    def speakers(x_access_token: str | None = Header(default=None)):
        cek_token(x_access_token)
        return {
            "bahasa": BAHASA,
            "pembicara": SPEAKERS,
            "maks_teks": MAX_TEKS,
            "kecepatan": {
                "min": KECEPATAN_MIN,
                "max": KECEPATAN_MAX,
                "default": 1.0,
            },
        }

    @web.post("/synthesize")
    def synthesize(
        req: Permintaan,
        x_access_token: str | None = Header(default=None),
    ):
        cek_token(x_access_token)
        try:
            wav = mesin.sintesis(req.teks, req.pembicara, req.kecepatan)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=wav,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'inline; filename="ttsjawa.wav"',
                "Cache-Control": "no-store",
            },
        )

    @web.exception_handler(Exception)
    def kesalahan(request, exc):
        return JSONResponse(
            status_code=500,
            content={"detail": f"Terjadi kesalahan pada backend: {exc}"},
        )

    return web


@app.cls(
    image=image,
    cpu=2.0,
    memory=4096,
    scaledown_window=600,
    secrets=[modal.Secret.from_name("ttsjawa", required_keys=["TTS_ACCESS_TOKEN"])],
)
class Backend:
    @modal.enter()
    def muat_model(self):
        self.mesin = MesinTTS()
        self.mesin.muat()

    @modal.asgi_app(label="ttsjawa")
    def api(self):
        return buat_web(self.mesin)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lokal",
        action="store_true",
        help="jalankan server di mesin ini untuk uji frontend, tanpa Modal",
    )
    parser.add_argument("--port", type=int, default=8000)
    arg = parser.parse_args()

    if arg.lokal:
        import uvicorn

        mesin = MesinTTS()
        mesin.muat()
        print(f"Model siap. Sample rate {mesin.sample_rate} Hz.")
        uvicorn.run(buat_web(mesin), host="127.0.0.1", port=arg.port)
    else:
        parser.print_help()
