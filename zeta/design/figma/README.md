# Figma: Дзета — UI

Файл «Дзета — UI» в команде **Lotus** (создаётся при первом запуске скриптов; если лимит Figma не даёт — при первой возможности).

> **Правило:** UI-кит и *все* экраны Дзеты живут в Figma. Любой новый экран, диалог или компонент добавляется
> в эти скрипты в том же изменении, что и код, и выкладывается в Figma.

1. `01_ui_kit.js` — страница **UI Kit**: токены (коллекции «Zeta — Light» / «Zeta — Dark», зеркало `zeta/theme.py`),
   пиксельная иконка ζ, компоненты: Tool button, Colour swatches, Palette cell, Timeline cel (Filled/Empty/Current),
   Layer row (Visible/Hidden/Selected/Locked), Tag, Context option, Button.
2. `02_screens.js` — страница **Screens**:

| Экран | Темы | В приложении |
|---|---|---|
| Main — инструменты, параметры, холст, таймлайн, цвет и палитра, предпросмотр | Light, Dark | главное окно |
| Welcome | Light | без открытых спрайтов |
| New sprite | Light | ⌘N |
| Export | Light | ⇧⌘E |
| Layer properties | Dark | двойной щелчок по слою |
