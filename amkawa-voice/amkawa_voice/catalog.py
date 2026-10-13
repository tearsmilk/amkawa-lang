"""Voice model catalog: built-in voices + user-imported RVC models."""
import json
import re
import shutil
import ssl
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .paths import cache_dir, models_dir


@dataclass
class VoiceModel:
    id: str
    name: str
    kind: str  # "builtin" | "rvc"
    description: str = ""
    params: dict = field(default_factory=dict)
    path: str = ""
    info: str = ""


BUILTIN = [
    VoiceModel("kawaii", "Kawaii", "builtin", "Милый высокий голос — классика аниме-героини.",
               dict(pitch=12, formant=1.25, brightness=3.0, breath=0.05)),
    VoiceModel("tsundere", "Tsundere", "builtin", "Звонкий и немного резкий.",
               dict(pitch=10, formant=1.20, brightness=2.0, breath=0.0)),
    VoiceModel("onee-san", "Onee-san", "builtin", "Взрослый мягкий женский голос.",
               dict(pitch=7, formant=1.15, brightness=1.0, breath=0.08)),
    VoiceModel("genki", "Genki", "builtin", "Энергичный, яркий, очень высокий.",
               dict(pitch=13, formant=1.30, brightness=4.0, breath=0.02)),
    VoiceModel("kuudere", "Kuudere", "builtin", "Спокойный, тихий, с придыханием.",
               dict(pitch=9, formant=1.18, brightness=0.0, breath=0.25)),
    VoiceModel("idol", "Idol", "builtin", "Сияющий «айдол»-тембр с яркими верхами.",
               dict(pitch=11, formant=1.22, brightness=5.0, breath=0.04)),
    VoiceModel("chibi", "Chibi", "builtin", "Крошечный мультяшный голосок.",
               dict(pitch=15, formant=1.38, brightness=4.0, breath=0.03)),
    VoiceModel("yandere", "Yandere", "builtin", "Ниже и мрачнее, с шёпотом.",
               dict(pitch=8, formant=1.12, brightness=-1.0, breath=0.15)),
]

CONTENTVEC_FILE = "contentvec.bin"


def contentvec_path() -> Path:
    return cache_dir() / CONTENTVEC_FILE


def contentvec_ready() -> bool:
    from .voices.hubert import CONTENTVEC_SIZE

    path = contentvec_path()
    return path.exists() and path.stat().st_size == CONTENTVEC_SIZE


def _slug(text):
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-").lower()
    return slug or "model"


def list_rvc_models():
    models = []
    for meta_file in sorted(models_dir().glob("*/meta.json")):
        try:
            meta = json.loads(meta_file.read_text("utf-8"))
        except Exception:
            continue
        pth = meta_file.parent / "model.pth"
        if not pth.exists():
            continue
        info = f"RVC {meta.get('version', '?')} · {meta.get('sr', 0) // 1000}k"
        models.append(VoiceModel(
            id="rvc:" + meta_file.parent.name, name=meta.get("name", meta_file.parent.name), kind="rvc",
            description=meta.get("description", "Нейросетевая RVC-модель."),
            params=dict(pitch=meta.get("pitch", 12)), path=str(pth), info=info))
    return models


def all_models():
    return list(BUILTIN) + list_rvc_models()


def remove_model(model: VoiceModel):
    if model.kind == "rvc":
        shutil.rmtree(Path(model.path).parent, ignore_errors=True)


# --------------------------------------------------------------------- import
def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def download(url, dest: Path, progress=None, expected_size=None):
    """Download `url` to `dest` atomically. progress(done_bytes, total_bytes)."""
    req = urllib.request.Request(url, headers={"User-Agent": "AmkawaVoice/1.0"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, context=_ssl_context(), timeout=60) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0) or (expected_size or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if expected_size and tmp.stat().st_size != expected_size:
        tmp.unlink(missing_ok=True)
        raise IOError("Файл скачался не полностью, попробуйте ещё раз")
    tmp.replace(dest)
    return dest


def ensure_contentvec(progress=None):
    from .voices.hubert import CONTENTVEC_SIZE, CONTENTVEC_URL

    if not contentvec_ready():
        download(CONTENTVEC_URL, contentvec_path(), progress, CONTENTVEC_SIZE)
    return contentvec_path()


def _resolve_hf_url(url):
    """Turn a Hugging Face repo/page link into a direct download link of a .pth or .zip."""
    parsed = urllib.parse.urlparse(url)
    if "huggingface.co" not in parsed.netloc:
        return url
    parts = [p for p in parsed.path.split("/") if p]
    if "blob" in parts:
        i = parts.index("blob")
        parts[i] = "resolve"
        return urllib.parse.urlunparse(parsed._replace(path="/" + "/".join(parts), query="download=true"))
    if "resolve" in parts:
        return url
    if len(parts) >= 2:  # repo page: pick the best file via the API
        repo = "/".join(parts[:2])
        api = f"https://huggingface.co/api/models/{repo}"
        req = urllib.request.Request(api, headers={"User-Agent": "AmkawaVoice/1.0"})
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=30) as resp:
            files = [s["rfilename"] for s in json.load(resp).get("siblings", [])]
        candidates = [f for f in files if f.lower().endswith(".pth") and not _is_training_ckpt(f)]
        candidates += [f for f in files if f.lower().endswith(".zip")]
        if not candidates:
            raise ValueError("В репозитории нет .pth или .zip файла модели")
        return f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(candidates[0])}"
    return url


def _is_training_ckpt(name):
    base = Path(name).name
    return base.startswith(("G_", "D_")) or base.startswith("f0G") or base.startswith("f0D")


def import_model(source: str, name: str = "", pitch: float = 12, progress=None) -> VoiceModel:
    """Import an RVC model from a local .pth/.zip file or a URL."""
    from .voices.rvc import describe_checkpoint

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if re.match(r"^https?://", source.strip()):
            url = _resolve_hf_url(source.strip())
            fname = Path(urllib.parse.urlparse(url).path).name or "model.pth"
            local = download(url, tmp / fname, progress)
        else:
            local = Path(source).expanduser()
        if local.suffix.lower() == ".zip":
            with zipfile.ZipFile(local) as zf:
                pths = [n for n in zf.namelist() if n.lower().endswith(".pth") and not _is_training_ckpt(n)
                        and not n.startswith("__MACOSX")]
                if not pths:
                    raise ValueError("В архиве нет .pth модели")
                best = max(pths, key=lambda n: zf.getinfo(n).file_size if zf.getinfo(n).file_size < 300e6 else 0)
                extracted = tmp / "extracted.pth"
                with zf.open(best) as src, open(extracted, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                default_name = Path(best).stem
                local = extracted
        else:
            default_name = local.stem
        meta = describe_checkpoint(local)
        name = (name or default_name).strip() or "RVC model"
        folder = models_dir() / _slug(name)
        n = 2
        while folder.exists():
            folder = models_dir() / f"{_slug(name)}-{n}"
            n += 1
        folder.mkdir(parents=True)
        shutil.copyfile(local, folder / "model.pth")
        meta.update(name=name, pitch=pitch, source=source)
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    return next(m for m in list_rvc_models() if m.id == "rvc:" + folder.name)
