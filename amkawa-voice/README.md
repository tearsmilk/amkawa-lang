# Amkawa Voice

Аниме-войсчейнджер в реальном времени для **macOS 11 Big Sur+ (Intel x64)**.
Интерфейс в стиле Claude, минимум анимаций.

- Берёт голос с выбранного микрофона и превращает его в женский аниме-голос.
- Вывод в **виртуальный микрофон «Amkawa Voice Mic»** — его можно выбрать в Discord как устройство ввода.
- **Слушать себя** — вывод ещё и в наушники, с отдельной громкостью.
- **Много голосов** с выбором в боковой панели:
  - 8 встроенных (Kawaii, Tsundere, Onee-san, Genki, Kuudere, Idol, Chibi, Yandere) — без интернета,
    задержка ~60 мс, лёгкие для процессора. Высота, тембр (форманты), яркость, придыхание настраиваются.
  - Любые **RVC v1/v2** модели (`.pth`, `.zip` или ссылка на Hugging Face) — нейросеть, звучит естественнее,
    но на Intel CPU задержка ~0.6–1 с.
- Шумодав, усиление, индикаторы уровня, светлая/тёмная тема.

## Скачать / собрать

**Без Mac** (так собран готовый dmg): `python3 packaging/build_dmg_portable.py --dmg-tool <libdmg-hfsplus/dmg>` —
собирает .app из готового portable-Python для macOS x86_64 и macOS-колёс зависимостей, ничего не компилируя,
проверяет, что все бинарники x86_64 и требуют macOS ≤ 11.0, и упаковывает в .dmg (нужны xorriso, Pillow, macholib).
Виртуальный микрофон в такой сборке — официальный подписанный BlackHole 2ch.

**На Mac / в GitHub Actions** (включите Actions в настройках репозитория):

Готовый `.dmg` собирается в GitHub Actions (workflow *Amkawa Voice (macOS Intel .dmg)*) на Intel-раннере macOS.
Скачать: вкладка **Actions** → последний успешный запуск → артефакт `AmkawaVoice-macOS-x64`.
Для релиза поставьте тег `voice-v1.0.0` — dmg появится в **Releases**.

Установка и настройка Discord — в [`packaging/README-dmg.txt`](packaging/README-dmg.txt) (этот же файл лежит в dmg).

## Где брать RVC-модели

Ищите на Hugging Face: «RVC v2 female», «RVC anime». Например, коллекции
[reddrumm/RVCModels](https://huggingface.co/reddrumm/RVCModels),
[TASTomusan/RVC_Models_Collection_Series](https://huggingface.co/TASTomusan/RVC_Models_Collection_Series).
Вставьте ссылку на репозиторий или на файл в окне «Добавить RVC-модель». Большинство таких моделей —
фанатские копии голосов персонажей/актёров: смотрите лицензию и не выдавайте себя за реальных людей.

## Как устроено

| Файл | Что делает |
|---|---|
| `amkawa_voice/engine.py` | аудио-потоки (sounddevice/CoreAudio): микрофон → голос → виртуальный микрофон + наушники |
| `amkawa_voice/voices/dsp.py` | встроенные голоса: фазовый вокодер со сдвигом высоты и формант |
| `amkawa_voice/voices/rvc.py` | RVC в реальном времени (ContentVec + YIN-питч + синтезатор RVC + SOLA) |
| `amkawa_voice/voices/hubert.py` | компактный ContentVec/HuBERT без fairseq/transformers |
| `amkawa_voice/virtual_mic.py` | установка драйвера «Amkawa Voice Mic» (BlackHole, переименованный при сборке) |
| `amkawa_voice/ui.py`, `theme.py` | интерфейс (PySide6) |
| `packaging/` | PyInstaller, сборка драйвера, проверка совместимости с macOS 11, dmg |

Запуск из исходников: `pip install -r requirements.txt && python run.py`.
Сборка на Intel Mac: `pip install -r requirements-build.txt && packaging/build_macos.sh`.

Лицензии: BlackHole — GPL-3.0, код RVC (`voices/rvc_pack`) — MIT.
