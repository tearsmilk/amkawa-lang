# Figma: Epsilon — UI

Файл: https://www.figma.com/design/P9vRt9ShTejyOkC7fYqWU4 (команда Lotus).

Скрипты для Figma Plugin API (запускаются через Figma MCP `use_figma`, по порядку):

1. `01_ui_kit.js` — страница **UI Kit**: цветовые токены (коллекции «Epsilon — Light» и «Epsilon — Dark»,
   на Starter-плане доступен только 1 режим на коллекцию), типографика и компоненты:
   Button (Primary/Accent/Secondary/Ghost/Link), Input, Nav item, Tree item, Tab, Segmented, Tag, Task,
   Code block, Callout (Tip/Note/Warning), Section label, Table row, Card.
2. `02_screens.js` — страница **Screens**: главный экран (светлый и тёмный) и экран «Ссылки».

Скрипт 1 полностью пересоздаёт страницу UI Kit, его можно запускать повторно.
