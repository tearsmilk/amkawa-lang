# Figma: Ню — UI

Файл «Ню — UI» в команде **Lotus** (создаётся при первом запуске скриптов; если лимит Figma не даёт — при первой возможности).

> **Правило:** UI-кит и *все* экраны Ню живут в Figma. Любой новый экран, диалог или компонент добавляется
> в эти скрипты в том же изменении, что и код, и выкладывается в Figma.

Скрипты для Figma Plugin API (запускаются через Figma MCP `use_figma`, по порядку):

1. `01_ui_kit.js` — страница **UI Kit**: токены (коллекции «Nu — Light» и «Nu — Dark», зеркало `nu/theme.py`,
   включая цвета подсветки синтаксиса и git), типографика, компоненты: Button, Activity item, Editor tab
   (Active/Inactive/Modified), Tree item (Folder/File/Modified/Untracked/Selected), Status item, Input, Find bar,
   Palette item, Code line, Terminal line, Git change.
2. `02_screens.js` — страница **Screens**:

| Экран | Темы | В приложении |
|---|---|---|
| Main — проводник, вкладки, код, поиск в файле, терминал, строка состояния | Light, Dark | главное окно |
| Command palette | Light | ⇧⌘P / ⌘P |
| Search — поиск по файлам | Dark | ⇧⌘F |
| Source control — git | Light | ⌃⇧G |
| Welcome — начало, недавние | Light | без открытых файлов |
| Settings | Light, Dark | ⌘, |

Скрипты пересоздают свои страницы целиком, их можно запускать повторно.
