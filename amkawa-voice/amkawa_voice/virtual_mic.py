"""Install/remove the virtual microphone that Discord listens to.

Two flavours, whichever is shipped inside the app:
- `drivers/AmkawaVoice.driver` — BlackHole renamed to "Amkawa Voice Mic 2ch" (built on a Mac, see build_driver.sh);
- `drivers/BlackHole2ch.pkg` — the official, signed BlackHole 2ch installer (device "BlackHole 2ch").
"""
import shlex
import subprocess
import sys
from pathlib import Path

from .paths import resource_path

HAL_DIR = Path("/Library/Audio/Plug-Ins/HAL")
CUSTOM_DRIVER = "AmkawaVoice.driver"
CUSTOM_DEVICE = "Amkawa Voice Mic 2ch"
BLACKHOLE_PKG = "BlackHole2ch.pkg"
BLACKHOLE_DRIVER = "BlackHole2ch.driver"
BLACKHOLE_DEVICE = "BlackHole 2ch"


def _find(name):
    candidates = [resource_path("drivers", name)]
    # inside "Amkawa Voice.app": Contents/MacOS/<exe> -> Contents/Resources/drivers
    candidates.append(Path(sys.executable).resolve().parent.parent / "Resources" / "drivers" / name)
    for path in candidates:
        if path.exists():
            return path
    return None


def _flavour():
    if _find(CUSTOM_DRIVER):
        return "custom"
    if _find(BLACKHOLE_PKG):
        return "blackhole"
    return None


def device_name():
    if (HAL_DIR / CUSTOM_DRIVER).exists() or _flavour() == "custom":
        return CUSTOM_DEVICE
    return BLACKHOLE_DEVICE


def is_installed() -> bool:
    return (HAL_DIR / CUSTOM_DRIVER).exists() or (HAL_DIR / BLACKHOLE_DRIVER).exists()


def can_install() -> bool:
    return sys.platform == "darwin" and _flavour() is not None


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
    flavour = _flavour()
    if flavour == "custom":
        src = _find(CUSTOM_DRIVER)
        dst = HAL_DIR / CUSTOM_DRIVER
        q_src, q_dst, q_dir = shlex.quote(str(src)), shlex.quote(str(dst)), shlex.quote(str(HAL_DIR))
        _run_as_admin(
            f"mkdir -p {q_dir} && rm -rf {q_dst} && cp -R {q_src} {q_dst} && "
            f"chown -R root:wheel {q_dst} && chmod -R 755 {q_dst} && "
            f"xattr -dr com.apple.quarantine {q_dst} 2>/dev/null; {_RESTART_AUDIO}")
    elif flavour == "blackhole":
        pkg = shlex.quote(str(_find(BLACKHOLE_PKG)))
        _run_as_admin(f"installer -pkg {pkg} -target / && {_RESTART_AUDIO}")
    else:
        raise RuntimeError("Драйвер не найден внутри приложения")


def uninstall():
    targets = " ".join(shlex.quote(str(HAL_DIR / d)) for d in (CUSTOM_DRIVER, BLACKHOLE_DRIVER))
    _run_as_admin(f"rm -rf {targets}; {_RESTART_AUDIO}")
