"""Install/remove the "Amkawa Voice Mic" virtual audio device (a renamed BlackHole HAL driver).

The app plays the converted voice into this device; Discord (or any app) then picks
"Amkawa Voice Mic" as its microphone.
"""
import shlex
import subprocess
import sys
from pathlib import Path

from .paths import resource_path

DRIVER_BUNDLE = "AmkawaVoice.driver"
DEVICE_NAME = "Amkawa Voice Mic"
HAL_DIR = Path("/Library/Audio/Plug-Ins/HAL")


def bundled_driver() -> Path:
    candidates = [resource_path("drivers", DRIVER_BUNDLE)]
    if getattr(sys, "frozen", False):  # AmkawaVoice.app/Contents/Resources/drivers
        candidates.append(Path(sys.executable).resolve().parent.parent / "Resources" / "drivers" / DRIVER_BUNDLE)
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def is_installed() -> bool:
    return (HAL_DIR / DRIVER_BUNDLE).exists()


def can_install() -> bool:
    return sys.platform == "darwin" and bundled_driver().exists()


def _run_as_admin(shell: str):
    escaped = shell.replace("\\", "\\\\").replace('"', '\\"')
    script = f'do shell script "{escaped}" with administrator privileges'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        err = result.stderr.strip()
        if "-128" in err:
            raise RuntimeError("Установка отменена")
        raise RuntimeError(err or "Не удалось выполнить команду")


_RESTART_AUDIO = ("(launchctl kickstart -kp system/com.apple.audio.coreaudiod "
                  "|| killall coreaudiod || true)")


def install():
    src = bundled_driver()
    if not src.exists():
        raise RuntimeError("Драйвер не найден внутри приложения")
    dst = HAL_DIR / DRIVER_BUNDLE
    q_src, q_dst, q_dir = shlex.quote(str(src)), shlex.quote(str(dst)), shlex.quote(str(HAL_DIR))
    _run_as_admin(
        f"mkdir -p {q_dir} && rm -rf {q_dst} && cp -R {q_src} {q_dst} && "
        f"chown -R root:wheel {q_dst} && chmod -R 755 {q_dst} && "
        f"xattr -dr com.apple.quarantine {q_dst} 2>/dev/null; {_RESTART_AUDIO}")


def uninstall():
    dst = shlex.quote(str(HAL_DIR / DRIVER_BUNDLE))
    _run_as_admin(f"rm -rf {dst}; {_RESTART_AUDIO}")
