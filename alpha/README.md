# α Альфа — Alpha

A local Trello-like kanban app in the Claude-like style of the other apps in this repo (ivory / charcoal,
terracotta accent, serif headings, Russian UI). macOS 11+ Intel x64, built into a `.dmg` by
`.github/workflows/alpha-macos.yml` (self-test included). Everything is stored locally — no account, no sync.

| Area | What it does |
|---|---|
| Boards | Home with starred / all boards and templates (Канбан, Учёба, Спринт, Личные дела, Контент-план), backgrounds (gradients, colours, own picture), copy, close / reopen, board as template |
| Lists | Drag to reorder, rename inline, WIP limit, colour, copy, sort, move all cards, archive all / archive the list |
| Cards | Drag between / within lists (placeholder like Trello), labels (10 Trello colours), members, start / due + done + reminder, Markdown description, checklists (progress, hide checked), attachments (files, links, image covers), colour covers, custom fields (text / number / date / checkbox / list), comments, votes, activity, move / copy (also to another board), card templates, archive |
| Views | Доска, Таблица (sortable), Календарь (drop a card on a day to change the due date), Дашборд (cards per list / label / member / due status) |
| Find | Search and filter by keyword, labels, members, due (overdue / today / week / none), done; «only my cards» |
| Automation | Butler-like: rules (13 triggers → 12 conditions → 19 actions), scheduled commands (daily / weekdays / weekly / monthly), due-date commands (before / after / at due), card buttons, board buttons, one-click ideas for the board, run log. Actions go through the same operations as the user, so they are logged, can trigger further rules (depth-limited) and are undone together with the change that triggered them |
| Other | Due-date notifications and reminders, undo / redo, Trello-like shortcuts (N, F, Q, L, D, C, Space, 1–9, ⌘F), Trello JSON import, export to JSON / CSV / Markdown, zip backup |

## Files

`alpha/model.py` (boards, float positions, undo snapshots, events) · `alpha/automation.py` (rule engine,
Russian rule descriptions) · `alpha/exchange.py` (Trello import, exports, templates) · `alpha/board_view.py`
(kanban + drag and drop) · `alpha/card_dialog.py` · `alpha/views.py` · `alpha/automation_ui.py` · `alpha/ui.py`.

## Run

```bash
cd alpha
pip install -r requirements.txt
python run.py              # the app
python run.py --selftest   # headless checks (rules, schedule, due commands, buttons, undo, Trello import, UI, DnD)
```

## Design

Figma file «Альфа — UI» (team Lotus): `design/figma/01_ui_kit.js`, `design/figma/02_screens.js`.
