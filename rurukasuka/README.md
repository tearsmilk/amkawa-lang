# rurukaSuka

Клиентский Fabric-мод под **Minecraft 1.21.11** в духе Essential: гардероб с косметикой из Blockbench-моделей,
валюта «руры», друзья и чат, Discord Rich Presence, кнопки в главном меню и в меню паузы.
Авторы: ruruka, Sakyu, nakuZen · package `ruruka.suka.rurukasuka` · **Mojang mappings** · лицензия ARR.

Бэкенд — сайт сообщества **mc-ru.org** (`RurukaSuka.SITE_URL`): аккаунт, ник, скин, руры, каталог
косметики, покупки, надетое, варианты-цвета, друзья и сообщения. Старый сайт onii.ink больше не используется.

## Сборка
Нужен **JDK 21**; Gradle тянуть не надо — в проекте wrapper (9.5.1).

```
cd rurukasuka && ./gradlew build
```

Результат: `build/libs/rurukasuka-0.1.0.jar` (+ `rurukasuka-mod.json` — метаданные для лаунчера).
В `mods/` рядом нужен Fabric API.

Версии (`gradle.properties`): loader 0.18.5 (на maven есть 0.20.1 — поднимать можно), loom
`1.17-SNAPSHOT` (плагин `net.fabricmc.fabric-loom-remap`), fabric-api `0.141.6+1.21.11`, Java 21.
Актуальные — https://fabricmc.net/develop.

## Лаунчер Эта
Эта ставит мод как **системный**: для Fabric/Quilt-сборок с подходящей версией MC кладёт в `mods/` свежий
jar и Fabric API (тумблер «Косметика rurukaSuka» в настройках лаунчера). Для аккаунта mc-ru.org перед
запуском лаунчер пишет `config/rurukasuka_launcher.json`:

```json
{"token": "<JWT mc-ru.org>", "site": "https://mc-ru.org", "nick": "Steve"}
```

Токен из этого файла важнее сохранённой сессии (`config/rurukasuka_session.txt`), `site` переопределяет
адрес сайта. Пустой токен — обычное поведение (вход из экрана «Аккаунт»). «Выйти» в моде удаляет оба файла.
Файл `cutiemi_session.txt` старой версии мигрируется в `rurukasuka_session.txt` автоматически.

Метаданные `mod.json` (копируется в `build/libs/rurukasuka-mod.json` при сборке): версия, поддерживаемые
версии MC и загрузчики, зависимости (`fabric-api` с Modrinth). Лаунчер читает его из релиза.

## Релизы
Workflow `.github/workflows/rurukasuka-mod.yml` собирает мод на каждый push в `rurukasuka/`.
Релиз: тег `rurukasuka-v<версия>` или ручной запуск workflow с полем `release_version` — jar и
`rurukasuka-mod.json` прикрепляются к GitHub Release `rurukasuka-v<версия>`.

## Код (`src/main/java/ruruka/suka/rurukasuka/`)
- `RurukaSukaClient` — точка входа: восстанавливает сессию, опрашивает каталог, Discord-статус, слой
  косметики на модели игрока, кнопки главного меню и «Гардероб» в меню ESC.
- `RurukaSuka` — `MOD_ID`, логгер, `SITE_URL`, `abs()`. `Currency` — склонение «рур/рура/руров».
- `net/SiteApi` — HTTP-клиент к API сайта (`/api/login`, `/api/me`, `/api/cosmetics`, `/api/purchase`,
  `/api/equip`, `/api/variant`, `/api/equipped/{nick}`, `/api/friends*`, `/api/messages`).
- `account/` — `RurukaAccount` (баланс, купленное, надетое, варианты), `SessionStore` (сессия + файл лаунчера).
- `discord/DiscordPresence` — Rich Presence без библиотек.
- `cosmetic/`, `render/`, `render/gui/`, `mixin/` — Blockbench-модели, слой на игроке, PIP-рендер в GUI.
- `ui/` — `WardrobeScreen`, `FriendsScreen`, `AccountScreen`, `McGui`, `McButton`, `PixelIcons`, `Palette`,
  `Hud`, `PlayerPreview` — экраны в стиле инвентаря Minecraft.

## Что ещё не сделано
- Кнопки Host / Pictures / Settings в главном меню пока только логируются.
- Discord Application ID (`1548766637686001734`) можно переопределить файлом в `config/`.
