# Figma: Дельта — UI

Файл «Дельта — UI» в команде **Lotus**: https://www.figma.com/design/hzTahrQ3AuMuBJcQny5haO (ключ `hzTahrQ3AuMuBJcQny5haO`).

> **Правило:** UI-кит и *все* экраны Дельты живут в Figma. Любой новый экран, диалог или компонент добавляется
> в эти скрипты в том же изменении, что и код, и выкладывается в Figma.

1. `01_ui_kit.js` — страница **UI Kit**: токены (коллекции «Delta — Light» / «Delta — Dark», зеркало `delta/theme.py`),
   иконка δ, компоненты: Tool button, Brush row, Brush slider, Layer row, Keyframe (Ease/Current/Hold), Property row,
   Speech bubble, Manga panel, Screentone, Button.
2. `02_screens.js` — страница **Screens**:

| Экран | Темы | В приложении |
|---|---|---|
| Main — инструменты, страница манги, панели «Цвет», «Кисти», «Слои», таймлайн анимации | Light, Dark | главное окно |
| New document | Light | ⌘N |
| Adjustment (тон / насыщенность) | Light | Фильтры |
| Export | Light | ⌥⌘E |
| Text | Dark | ⇧T / реплика |
