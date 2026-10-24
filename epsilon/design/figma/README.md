# Figma: Epsilon — UI

Файл: https://www.figma.com/design/P9vRt9ShTejyOkC7fYqWU4 (команда Lotus).

> **Правило:** UI-кит и *все* экраны приложения живут в Figma. Любой новый экран, диалог или
> компонент Epsilon добавляется в эти скрипты в том же изменении, что и код, и выкладывается
> в Figma (при лимите Figma — при первой возможности).

Скрипты для Figma Plugin API (запускаются через Figma MCP `use_figma`, по порядку):

1. `01_ui_kit.js` — страница **UI Kit**: цветовые токены (коллекции «Epsilon — Light» и «Epsilon — Dark»;
   на Starter-плане доступен только 1 режим на коллекцию), типографика и компоненты:
   Button (Primary/Accent/Secondary/Ghost/Link), Input, Nav item, Tree item, Tab, Segmented, Tag, Task,
   Code block, Callout (Tip/Note/Warning), Section label, Table row, Card,
   Calendar day (Default/Today/Selected/Other month), Task row (Todo/Done),
   Attachment card (Video/Audio/PDF/File), Player bar.
2. `02_screens.js` — страница **Screens**:

| Экран | Темы | В приложении |
|---|---|---|
| Main — заметка (редактор + просмотр, боковая и правая панели) | Light, Dark | главное окно |
| Links — закладки | Light | «☰ Ссылки» |
| Calendar — месяц, планировщик, план дня | Light, Dark | «▦ Календарь» |
| Settings — внешний вид, хранилище, корзина | Light | ⚙ / ⌘, |
| Note with attachments — фото, GIF, карточки видео/аудио/PDF, кнопка 📎 | Light, Dark | заметка в режиме «Просмотр» |
| Media viewer — фото (масштаб), видео (плеер) | Light (фото), Dark (видео) | щелчок по вложению |
| Files — вложения с превью и фильтром по типу | Light | «▤ Файлы» |

Скрипты пересоздают свои страницы целиком, их можно запускать повторно.
