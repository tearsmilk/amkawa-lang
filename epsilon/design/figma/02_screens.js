// Epsilon — Screens page: Main (Light/Dark), Links, Calendar (Light/Dark), Settings, Attachments (note, viewer, files).
// Run after 01_ui_kit.js.
let page = figma.root.children.find(p => p.name === "Screens");
if (!page) { page = figma.createPage(); page.name = "Screens"; }
await figma.setCurrentPageAsync(page);
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const MONO = ["JetBrains Mono", "Roboto Mono", "Source Code Pro", "IBM Plex Mono"].find(f => has(f, "Regular")) || "Inter";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: MONO, style: "Regular"}]) await figma.loadFontAsync(fn);

const cols = await figma.variables.getLocalVariableCollectionsAsync();
const vars = await figma.variables.getLocalVariablesAsync("COLOR");
const V = {};
for (const mode of ["Light", "Dark"]) {
  const col = cols.find(c => c.name === "Epsilon — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection " + mode + ")");
  V[mode] = {};
  for (const v of vars) if (v.variableCollectionId === col.id) V[mode][v.name.replace("color/", "")] = v;
}
let MODE = "Light";
const fill = n => figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][n]);
function txt(chars, o = {}) {
  const t = figma.createText();
  t.fontName = {family: o.family || SANS, style: o.style || "Regular"};
  t.fontSize = o.size || 13; t.characters = chars; t.fills = [fill(o.color || "text")];
  if (o.w) { t.textAutoResize = "HEIGHT"; t.resize(o.w, t.height); }
  return t;
}
function al(dir, o = {}) {
  const f = figma.createAutoLayout(dir, {itemSpacing: o.gap ?? 8});
  f.name = o.name || "Frame";
  f.fills = o.fill ? [fill(o.fill)] : [];
  if (o.pad !== undefined) { const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad, o.pad, o.pad, o.pad]; f.paddingTop = t; f.paddingRight = r; f.paddingBottom = b; f.paddingLeft = l; }
  if (o.radius) f.cornerRadius = o.radius;
  if (o.stroke) { f.strokes = [fill(o.stroke)]; f.strokeWeight = 1; }
  if (o.align) f.counterAxisAlignItems = o.align;
  return f;
}
function add(parent, child, sizing = {}) { parent.appendChild(child); if (sizing.h) child.layoutSizingHorizontal = sizing.h; if (sizing.v) child.layoutSizingVertical = sizing.v; return child; }
function button(label, kind) {
  const b = al("HORIZONTAL", {name: "Button / " + kind, pad: kind === "Accent" ? [7, 14, 7, 14] : [7, 14, 7, 14], radius: 9,
    fill: kind === "Accent" ? "accent" : "card", stroke: kind === "Accent" ? null : "border"});
  b.primaryAxisAlignItems = "CENTER";
  b.appendChild(txt(label, {color: kind === "Accent" ? "on-accent" : "text", style: kind === "Accent" ? "Semi Bold" : "Regular"}));
  return b;
}
function sectionLabel(s) { return txt(s.toUpperCase(), {size: 11, style: "Semi Bold", color: "muted"}); }

function sidebar(selectedNote) {
  const side = al("VERTICAL", {name: "Sidebar", gap: 8, pad: [18, 14, 12, 14], fill: "sidebar"});
  side.strokes = [fill("border")]; side.strokeTopWeight = 0; side.strokeLeftWeight = 0; side.strokeBottomWeight = 0; side.strokeRightWeight = 1;
  side.resize(280, 860); side.primaryAxisSizingMode = "FIXED"; side.counterAxisSizingMode = "FIXED";
  const logo = al("HORIZONTAL", {name: "Logo", gap: 8, align: "CENTER"});
  logo.appendChild(txt("ε", {family: SERIF, size: 30, color: "accent"})); logo.appendChild(txt("Epsilon", {family: SERIF, size: 21}));
  side.appendChild(logo);
  const search = al("HORIZONTAL", {name: "Search", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"});
  add(side, search, {h: "FILL"}); search.appendChild(txt("Поиск  ⇧⌘F", {color: "muted"}));
  const actions = al("HORIZONTAL", {name: "Actions", gap: 6});
  add(side, actions, {h: "FILL"});
  add(actions, button("＋ Заметка", "Accent"), {h: "FILL"}); actions.appendChild(button("Сегодня", "Secondary"));
  for (const [icon, label] of [["☰", "Ссылки"], ["▤", "Файлы"], ["◎", "Граф"], ["⌕", "Поиск"]]) {
    const n = al("HORIZONTAL", {name: "Nav / " + label, gap: 10, pad: [7, 10, 7, 10], radius: 8});
    n.appendChild(txt(icon, {color: "muted"})); n.appendChild(txt(label)); add(side, n, {h: "FILL"});
  }
  const notesHead = al("HORIZONTAL", {name: "Notes header"}); add(side, notesHead, {h: "FILL"});
  notesHead.appendChild(sectionLabel("Заметки"));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); notesHead.appendChild(sp); sp.layoutGrow = 1;
  notesHead.appendChild(txt("＋ папка", {size: 12, color: "muted"}));
  for (const [name, depth] of [["Дневник", 0], ["2026-10-14", 1], ["Добро пожаловать", 0], ["Идеи", 0], ["Проекты", 0], ["Рецепты", 0]]) {
    const item = al("HORIZONTAL", {name: "Tree / " + name, pad: [4, 8, 4, 8 + depth * 14], radius: 6, fill: name === selectedNote ? "selected" : null, gap: 6});
    item.appendChild(txt(depth === 0 && name === "Дневник" ? "▾  " + name : name)); add(side, item, {h: "FILL"});
  }
  const grow = figma.createFrame(); grow.fills = []; grow.resize(10, 10); side.appendChild(grow); grow.layoutGrow = 1;
  side.appendChild(sectionLabel("Теги"));
  for (const [t, n] of [["работа", 4], ["идеи", 2], ["код", 2]]) side.appendChild(txt(`#${t}   ${n}`, {color: "text"}));
  const bottom = al("HORIZONTAL", {name: "Bottom"}); add(side, bottom, {h: "FILL"});
  bottom.appendChild(txt("▣  Epsilon", {size: 12, color: "muted"}));
  const sp2 = figma.createFrame(); sp2.fills = []; sp2.resize(4, 4); bottom.appendChild(sp2); sp2.layoutGrow = 1;
  bottom.appendChild(txt(MODE === "Dark" ? "● Тёмная" : "◐ Системная", {size: 12, color: "muted"}));
  return side;
}
function tabBar(tabs, active) {
  const bar = al("HORIZONTAL", {name: "Tabs", gap: 2, pad: [0, 12, 0, 12], fill: "bg"});
  bar.strokes = [fill("border")]; bar.strokeTopWeight = 0; bar.strokeLeftWeight = 0; bar.strokeRightWeight = 0; bar.strokeBottomWeight = 1;
  for (const t of tabs) {
    const tab = al("HORIZONTAL", {name: "Tab / " + t, gap: 10, pad: [9, 14, 9, 14]});
    if (t === active) { tab.strokes = [fill("accent")]; tab.strokeTopWeight = 0; tab.strokeLeftWeight = 0; tab.strokeRightWeight = 0; tab.strokeBottomWeight = 2; }
    tab.appendChild(txt(t, {color: t === active ? "text" : "muted"})); tab.appendChild(txt("×", {size: 14, color: "muted"}));
    bar.appendChild(tab);
  }
  return bar;
}
function codeBlock(width) {
  const code = al("VERTICAL", {name: "Code block", gap: 8, pad: [8, 14, 12, 14], radius: 10, fill: "code-bg", stroke: "border"});
  code.resize(width, 10); code.counterAxisSizingMode = "FIXED"; code.primaryAxisSizingMode = "AUTO";
  const h = al("HORIZONTAL", {name: "Header"}); add(code, h, {h: "FILL"});
  h.appendChild(txt("JAVASCRIPT", {size: 11, style: "Semi Bold", color: "muted"}));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); h.appendChild(sp); sp.layoutGrow = 1;
  h.appendChild(txt("Копировать", {size: 11, color: "accent"}));
  for (const ln of [[["const ", "syntax-keyword"], ["users = ", "text"], ["await ", "syntax-keyword"], ["fetch", "syntax-func"], ["(", "text"], ["'/api/users'", "syntax-string"], [");", "text"]],
                    [["users", "text"], [".", "text"], ["forEach", "syntax-func"], ["(u => console.", "text"], ["log", "syntax-func"], ["(u.name));", "text"]]]) {
    const row = al("HORIZONTAL", {name: "Line", gap: 0});
    for (const [s, c] of ln) row.appendChild(txt(s, {family: MONO, size: 12, color: c}));
    code.appendChild(row);
  }
  return code;
}
function noteScreen(name, x) {
  const win = al("HORIZONTAL", {name, gap: 0, fill: "bg"});
  win.resize(1360, 860); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = 0;
  win.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  add(win, sidebar("Проекты"), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0, fill: "bg"});
  add(win, center, {h: "FILL", v: "FILL"});
  add(center, tabBar(["Добро пожаловать", "Проекты", "☰ Ссылки"], "Проекты"), {h: "FILL"});
  const header = al("HORIZONTAL", {name: "Note header", pad: [14, 18, 10, 28], align: "CENTER"}); add(center, header, {h: "FILL"});
  const tc = al("VERTICAL", {name: "Title", gap: 2}); header.appendChild(tc);
  tc.appendChild(txt("Проекты", {family: SERIF, size: 22})); tc.appendChild(txt("Epsilon", {size: 12, color: "muted"}));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); header.appendChild(sp); sp.layoutGrow = 1;
  const seg = al("HORIZONTAL", {name: "Segmented", gap: 0, radius: 8, stroke: "border", fill: "card"}); seg.clipsContent = true;
  for (const [i, l] of ["Редактор", "Разделить", "Просмотр"].entries()) { const s = al("HORIZONTAL", {name: l, pad: [5, 12, 5, 12], fill: i === 1 ? "selected" : null}); s.appendChild(txt(l, {size: 12})); seg.appendChild(s); }
  header.appendChild(seg); header.appendChild(txt("  📎", {color: "muted"})); header.appendChild(txt("  ···", {color: "muted"}));
  const split = al("HORIZONTAL", {name: "Split", gap: 0}); add(center, split, {h: "FILL", v: "FILL"});
  // editor
  const ed = al("VERTICAL", {name: "Editor", gap: 6, pad: 28, fill: "editor"}); add(split, ed, {h: "FILL", v: "FILL"});
  ed.strokes = [fill("border")]; ed.strokeTopWeight = 0; ed.strokeLeftWeight = 0; ed.strokeBottomWeight = 0; ed.strokeRightWeight = 1;
  const mdLines = [["# Проекты", "text", 20, "Semi Bold"], ["", "text"], ["Связано с [[Идеи]] и [[Дневник]] #работа", "text"], ["", "text"],
    ["- [x] сделать дизайн в Figma", "muted"], ["- [ ] собрать dmg", "text"], ["", "text"], ["> [!tip] Код", "muted"], ["> Вставьте код — язык определится сам.", "muted"],
    ["", "text"], ["```javascript", "muted", 12, "Regular", MONO], ["const users = await fetch('/api/users');", "text", 12, "Regular", MONO],
    ["users.forEach(u => console.log(u.name));", "text", 12, "Regular", MONO], ["```", "muted", 12, "Regular", MONO]];
  for (const [s, c, size, style, fam] of mdLines) ed.appendChild(txt(s || " ", {color: c, size: size || 14, style: style || "Regular", family: fam || SANS}));
  // reader
  const rd = al("VERTICAL", {name: "Reader", gap: 10, pad: 28, fill: "bg"}); add(split, rd, {h: "FILL", v: "FILL"});
  rd.appendChild(txt("Проекты", {family: SERIF, size: 30}));
  const p = al("HORIZONTAL", {name: "Paragraph", gap: 4, align: "CENTER"}); rd.appendChild(p);
  p.appendChild(txt("Связано с", {size: 15})); p.appendChild(txt("Идеи", {size: 15, color: "accent"})); p.appendChild(txt("и", {size: 15}));
  p.appendChild(txt("Дневник", {size: 15, color: "accent"}));
  const tag = al("HORIZONTAL", {name: "Tag", pad: [2, 6, 2, 6], radius: 5, fill: "tag-bg"}); tag.appendChild(txt("#работа", {size: 14, color: "accent"})); p.appendChild(tag);
  for (const [done, label] of [[true, "сделать дизайн в Figma"], [false, "собрать dmg"]]) {
    const row = al("HORIZONTAL", {name: "Task", gap: 8, align: "CENTER"});
    const box = figma.createRectangle(); box.resize(14, 14); box.cornerRadius = 4;
    box.fills = done ? [fill("accent")] : []; box.strokes = [fill(done ? "accent" : "muted")]; box.strokeWeight = 1.2;
    row.appendChild(box); row.appendChild(txt(label, {size: 15, color: done ? "muted" : "text"})); rd.appendChild(row);
  }
  const callout = al("VERTICAL", {name: "Callout", gap: 4, pad: [10, 14, 10, 14], fill: "callout-bg"});
  callout.strokes = [fill("success")]; callout.strokeTopWeight = 0; callout.strokeRightWeight = 0; callout.strokeBottomWeight = 0; callout.strokeLeftWeight = 3;
  add(rd, callout, {h: "FILL"});
  callout.appendChild(txt("✦  Код", {style: "Semi Bold", color: "success"})); callout.appendChild(txt("Вставьте код — язык определится сам.", {size: 14}));
  add(rd, codeBlock(420), {h: "FILL"});
  // right panel
  const right = al("VERTICAL", {name: "Right panel", gap: 8, pad: [18, 14, 14, 14], fill: "sidebar"});
  right.strokes = [fill("border")]; right.strokeTopWeight = 0; right.strokeRightWeight = 0; right.strokeBottomWeight = 0; right.strokeLeftWeight = 1;
  right.resize(250, 860); right.counterAxisSizingMode = "FIXED"; add(win, right, {v: "FILL"});
  right.appendChild(sectionLabel("Оглавление")); right.appendChild(txt("Проекты"));
  const g1 = figma.createFrame(); g1.fills = []; g1.resize(4, 40); right.appendChild(g1);
  right.appendChild(sectionLabel("Обратные ссылки")); right.appendChild(txt("Идеи")); right.appendChild(txt("Дневник / 2026-10-14"));
  const g2 = figma.createFrame(); g2.fills = []; g2.resize(4, 4); right.appendChild(g2); g2.layoutGrow = 1;
  right.appendChild(sectionLabel("Теги заметки")); right.appendChild(txt("#работа", {color: "muted"}));
  right.appendChild(txt("24 слова · 210 символов", {size: 12, color: "muted"}));
  return win;
}
function linksScreen(x) {
  const win = al("HORIZONTAL", {name: "Links — Light", gap: 0, fill: "bg"});
  win.resize(1360, 860); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = 0;
  add(win, sidebar(null), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0, fill: "bg"}); add(win, center, {h: "FILL", v: "FILL"});
  add(center, tabBar(["Проекты", "☰ Ссылки"], "☰ Ссылки"), {h: "FILL"});
  const body = al("VERTICAL", {name: "Links", gap: 12, pad: [22, 28, 20, 28]}); add(center, body, {h: "FILL", v: "FILL"});
  body.appendChild(txt("Ссылки", {family: SERIF, size: 30}));
  body.appendChild(txt("Закладки хранятся в хранилище (.epsilon/links.json). Двойной щелчок — открыть.", {color: "muted"}));
  const form = al("HORIZONTAL", {name: "Add form", gap: 8}); add(body, form, {h: "FILL"});
  for (const [ph, grow] of [["https://…", 3], ["Название (необязательно)", 2], ["теги через запятую", 2]]) {
    const inp = al("HORIZONTAL", {name: "Input", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"});
    inp.appendChild(txt(ph, {color: "muted"})); add(form, inp, {h: "FILL"});
  }
  form.appendChild(button("Добавить", "Accent"));
  const table = al("VERTICAL", {name: "Table", gap: 0}); add(body, table, {h: "FILL"});
  const rows = [["НАЗВАНИЕ", "АДРЕС", "ТЕГИ", "ДОБАВЛЕНО"], ["Claude", "https://claude.ai", "#ai", "14.10.2026 09:12"],
    ["github.com — tearsmilk", "https://github.com/tearsmilk", "#код", "14.10.2026 09:10"],
    ["Figma — Epsilon UI", "https://figma.com/design/P9vRt9…", "#дизайн", "13.10.2026 22:40"],
    ["Python docs", "https://docs.python.org/3/", "#код #docs", "12.10.2026 18:05"]];
  rows.forEach((vals, r) => {
    const row = al("HORIZONTAL", {name: r ? "Row" : "Header", gap: 16, pad: [9, 10, 9, 10], fill: r ? null : "bg"});
    row.strokes = [fill("border")]; row.strokeTopWeight = 0; row.strokeLeftWeight = 0; row.strokeRightWeight = 0; row.strokeBottomWeight = 1;
    add(table, row, {h: "FILL"});
    [260, 340, 140, 160].forEach((w, i) => row.appendChild(txt(vals[i], {w, size: r ? 13 : 11, style: r ? "Regular" : "Semi Bold", color: !r || i === 1 ? "muted" : (i === 2 ? "accent" : "text")})));
  });
  return win;
}


function calendarScreen(x) {
  const win = al("HORIZONTAL", {name: "Calendar — " + MODE, gap: 0, fill: "bg"});
  win.resize(1440, 900); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = 1000;
  add(win, sidebar(null), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0, fill: "bg"}); add(win, center, {h: "FILL", v: "FILL"});
  add(center, tabBar(["Добро пожаловать", "▦ Календарь"], "▦ Календарь"), {h: "FILL"});
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(center, body, {h: "FILL", v: "FILL"});
  // month + planner
  const left = al("VERTICAL", {name: "Month", gap: 10, pad: [20, 18, 16, 28]}); add(body, left, {h: "FILL", v: "FILL"});
  const head = al("HORIZONTAL", {name: "Header", gap: 8, align: "CENTER"}); add(left, head, {h: "FILL"});
  head.appendChild(txt("Октябрь 2026", {family: SERIF, size: 30}));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); head.appendChild(sp); sp.layoutGrow = 1;
  for (const b of ["‹", "Сегодня", "›"]) head.appendChild(button(b, "Secondary"));
  const grid = al("VERTICAL", {name: "Grid", gap: 0}); add(left, grid, {h: "FILL"});
  const wd = al("HORIZONTAL", {name: "Weekdays", gap: 0}); add(grid, wd, {h: "FILL"});
  for (const d of ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]) {
    const cell = al("HORIZONTAL", {name: d, pad: [6, 0, 6, 0]}); cell.primaryAxisAlignItems = "CENTER";
    cell.appendChild(txt(d, {size: 11, style: "Semi Bold", color: "muted"})); add(wd, cell, {h: "FILL"});
  }
  const tasksOn = {13: [1, true], 15: [2, false], 16: [1, false], 17: [1, false], 20: [1, false]};
  let day = 28;  // Sep 28 … Nov 8
  for (let r = 0; r < 6; r++) {
    const row = al("HORIZONTAL", {name: "Week " + (r + 1), gap: 6}); add(grid, row, {h: "FILL"});
    for (let c = 0; c < 7; c++) {
      const idx = r * 7 + c;
      const inMonth = idx >= 3 && idx < 34;
      const d = inMonth ? idx - 2 : (idx < 3 ? 28 + idx : idx - 33);
      const isToday = inMonth && d === 15;
      const cell = al("VERTICAL", {name: "Day " + d, pad: [5, 6, 6, 6], gap: 8, radius: 10, fill: isToday ? "selected" : null});
      cell.resize(80, 64); cell.counterAxisSizingMode = "FIXED"; cell.primaryAxisSizingMode = "FIXED";
      add(row, cell, {h: "FILL"});
      const num = al("HORIZONTAL", {name: "Number", radius: 14, fill: isToday ? "accent" : null});
      num.resize(28, 28); num.primaryAxisSizingMode = "FIXED"; num.counterAxisSizingMode = "FIXED";
      num.primaryAxisAlignItems = "CENTER"; num.counterAxisAlignItems = "CENTER";
      num.appendChild(txt(String(d), {size: 14, color: isToday ? "on-accent" : (inMonth ? "text" : "muted")}));
      cell.appendChild(num);
      const info = inMonth && tasksOn[d];
      if (info) {
        const dots = al("HORIZONTAL", {name: "Tasks", gap: 3, align: "CENTER"});
        for (let i = 0; i < Math.min(info[0], 3); i++) { const e = figma.createEllipse(); e.resize(6, 6); e.fills = [fill(info[1] ? "warning" : "accent")]; dots.appendChild(e); }
        dots.appendChild(txt(String(info[0]), {size: 11, style: "Semi Bold", color: info[1] ? "warning" : "text"}));
        cell.appendChild(dots);
      }
    }
  }
  left.appendChild(sectionLabel("Планировщик"));
  const groups = [["ПРОСРОЧЕНО", [["13 окт", "⏫ Оплатить интернет", "Дневник"]], "warning"],
                  ["СЕГОДНЯ", [["15 окт  11:00", "🔼 Созвон с командой", "Дневник"], ["15 окт", "Купить молоко", "Дневник"]], "muted"],
                  ["БЛИЖАЙШИЕ 7 ДНЕЙ", [["16 окт  19:30", "Тренировка", "Дневник"], ["17 окт  18:00", "⏫ Сдать макеты в Figma", "Дневник"]], "muted"]];
  for (const [title, items, colr] of groups) {
    left.appendChild(txt(title, {size: 11, style: "Semi Bold", color: colr}));
    for (const [when, label, src] of items) {
      const r = al("HORIZONTAL", {name: "Task", gap: 10, align: "MIN"});
      const box = figma.createRectangle(); box.resize(15, 15); box.cornerRadius = 5; box.fills = [fill("input")]; box.strokes = [fill("muted")]; box.strokeWeight = 1;
      r.appendChild(box);
      const col = al("VERTICAL", {name: "Text", gap: 1});
      col.appendChild(txt(`${when}   ${label}`, {size: 13})); col.appendChild(txt(src, {size: 12, color: "muted"}));
      r.appendChild(col); left.appendChild(r);
    }
  }
  // selected day panel
  const right = al("VERTICAL", {name: "Day plan", gap: 10, pad: [20, 22, 16, 22], fill: "sidebar"});
  right.strokes = [fill("border")]; right.strokeTopWeight = 0; right.strokeRightWeight = 0; right.strokeBottomWeight = 0; right.strokeLeftWeight = 1;
  right.resize(430, 800); right.counterAxisSizingMode = "FIXED"; add(body, right, {v: "FILL"});
  right.appendChild(txt("Четверг, 15 октября · сегодня", {family: SERIF, size: 18}));
  right.appendChild(txt("Задач: 3, осталось: 2", {size: 12, color: "muted"}));
  right.appendChild(txt("Открыть дневник дня", {size: 13, color: "muted"}));
  const inp = al("HORIZONTAL", {name: "New task", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"});
  inp.appendChild(txt("Новая задача…  (Enter — добавить)", {color: "muted"})); add(right, inp, {h: "FILL"});
  const r2 = al("HORIZONTAL", {name: "Options", gap: 8}); add(right, r2, {h: "FILL"});
  const tm = al("HORIZONTAL", {name: "Time", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"}); tm.appendChild(txt("⏰ 14:30", {color: "muted"})); r2.appendChild(tm);
  const pr = al("HORIZONTAL", {name: "Priority", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"}); pr.appendChild(txt("Без приоритета")); add(r2, pr, {h: "FILL"});
  r2.appendChild(button("Добавить", "Accent"));
  for (const [time, label, done] of [["11:00", "🔼 Созвон с командой", false], ["", "Купить молоко", false], ["", "Иконка", true]]) {
    const r = al("HORIZONTAL", {name: "Task", gap: 10, align: "MIN"});
    const box = figma.createRectangle(); box.resize(15, 15); box.cornerRadius = 5;
    box.fills = [fill(done ? "accent" : "input")]; box.strokes = [fill(done ? "accent" : "muted")]; box.strokeWeight = 1; r.appendChild(box);
    const col = al("VERTICAL", {name: "Text", gap: 1});
    col.appendChild(txt(`${time ? time + "   " : ""}${label}`, {size: 13, color: done ? "muted" : "text"}));
    col.appendChild(txt(done ? "Проект Epsilon" : "Дневник", {size: 12, color: "muted"})); r.appendChild(col); right.appendChild(r);
  }
  return win;
}
function settingsScreen(x) {
  const dlg = al("VERTICAL", {name: "Settings — " + MODE, gap: 10, pad: [24, 28, 22, 28], fill: "bg", radius: 12, stroke: "border"});
  dlg.resize(620, 10); dlg.counterAxisSizingMode = "FIXED"; dlg.primaryAxisSizingMode = "AUTO"; dlg.x = x; dlg.y = 1000;
  dlg.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.15}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  dlg.appendChild(txt("Настройки", {family: SERIF, size: 30}));
  dlg.appendChild(sectionLabel("Внешний вид"));
  const row = al("HORIZONTAL", {name: "Appearance", gap: 12}); add(dlg, row, {h: "FILL"});
  for (const [label, val] of [["Тема", "Системная"], ["Шрифт", "14 pt"], ["Новые вкладки", "Разделить"]]) {
    const col = al("VERTICAL", {name: label, gap: 4}); add(row, col, {h: "FILL"});
    col.appendChild(txt(label, {size: 12, color: "muted"}));
    const f = al("HORIZONTAL", {name: "Field", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"}); f.appendChild(txt(val)); add(col, f, {h: "FILL"});
  }
  dlg.appendChild(sectionLabel("Хранилище"));
  dlg.appendChild(txt("~/Documents/Epsilon", {size: 13, color: "muted"}));
  const vr = al("HORIZONTAL", {name: "Vault actions", gap: 8}); dlg.appendChild(vr);
  vr.appendChild(button("Показать в Finder", "Secondary")); vr.appendChild(button("Открыть другое…", "Secondary"));
  dlg.appendChild(sectionLabel("Корзина"));
  dlg.appendChild(txt("В корзине хранилища: 2 · 27 Б", {size: 13, color: "muted"}));
  for (const [name, meta] of [["Черновик.md", "2026-10-15 05:11 · 19 Б"], ["Старый список.md", "2026-10-15 05:11 · 8 Б"]]) {
    const it = al("VERTICAL", {name: "Trash item", gap: 1}); it.appendChild(txt(name)); it.appendChild(txt(meta, {size: 12, color: "muted"})); dlg.appendChild(it);
  }
  const tr = al("HORIZONTAL", {name: "Trash actions", gap: 8}); add(dlg, tr, {h: "FILL"});
  tr.appendChild(button("Восстановить", "Secondary")); tr.appendChild(button("Показать папку", "Secondary"));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); tr.appendChild(sp); sp.layoutGrow = 1;
  tr.appendChild(button("Очистить корзину", "Accent"));
  dlg.appendChild(txt("☐  Удалять сразу в Корзину macOS (минуя корзину хранилища)", {size: 13}));
  dlg.appendChild(txt("«Очистить корзину» перемещает всё удалённое в Корзину macOS — там работает «Вернуть».", {size: 12, color: "muted", w: 560}));
  return dlg;
}

// ---- attachments
function photo(w, h) {  // stand-in for a picture: sunset gradient
  const r = figma.createRectangle(); r.name = "Photo"; r.resize(w, h); r.cornerRadius = 6;
  r.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]],
    gradientStops: [{position: 0, color: {r: 0.98, g: 0.75, b: 0.55, a: 1}}, {position: 0.6, color: {r: 0.83, g: 0.45, b: 0.37, a: 1}},
                    {position: 1, color: {r: 0.2, g: 0.15, b: 0.22, a: 1}}]}];
  return r;
}
function attachmentCard(icon, name, meta, action, width) {
  const c = al("HORIZONTAL", {name: "Attachment card / " + name, gap: 0, fill: "card", stroke: "border", align: "CENTER"});
  c.resize(width, 80); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED";
  const prev = al("HORIZONTAL", {name: "Preview", fill: "tag-bg"});
  prev.resize(64, 80); prev.primaryAxisSizingMode = "FIXED"; prev.counterAxisSizingMode = "FIXED";
  prev.primaryAxisAlignItems = "CENTER"; prev.counterAxisAlignItems = "CENTER";
  prev.appendChild(txt(icon, {size: 26})); c.appendChild(prev);
  const col = al("VERTICAL", {name: "Info", gap: 3, pad: [10, 14, 10, 14]}); c.appendChild(col);
  col.appendChild(txt(name, {size: 14, style: "Semi Bold"})); col.appendChild(txt(meta, {size: 12, color: "muted"}));
  const a = al("HORIZONTAL", {name: "Actions", gap: 12}); col.appendChild(a);
  a.appendChild(txt(action, {size: 12, color: "accent"})); a.appendChild(txt("Показать в Finder", {size: 12, color: "muted"}));
  return c;
}
function attachmentsNoteScreen(x, y) {
  const win = al("HORIZONTAL", {name: "Note with attachments — " + MODE, gap: 0, fill: "bg"});
  win.resize(1360, 860); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = y;
  add(win, sidebar("Поездка"), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0, fill: "bg"}); add(win, center, {h: "FILL", v: "FILL"});
  add(center, tabBar(["Добро пожаловать", "Поездка"], "Поездка"), {h: "FILL"});
  const header = al("HORIZONTAL", {name: "Note header", pad: [14, 18, 10, 28], align: "CENTER"}); add(center, header, {h: "FILL"});
  const tc = al("VERTICAL", {name: "Title", gap: 2}); header.appendChild(tc);
  tc.appendChild(txt("Поездка", {family: SERIF, size: 22})); tc.appendChild(txt("Epsilon", {size: 12, color: "muted"}));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); header.appendChild(sp); sp.layoutGrow = 1;
  const seg = al("HORIZONTAL", {name: "Segmented", gap: 0, radius: 8, stroke: "border", fill: "card"}); seg.clipsContent = true;
  for (const [i, l] of ["Редактор", "Разделить", "Просмотр"].entries()) { const s = al("HORIZONTAL", {name: l, pad: [5, 12, 5, 12], fill: i === 2 ? "selected" : null}); s.appendChild(txt(l, {size: 12})); seg.appendChild(s); }
  header.appendChild(seg);
  const clip = al("HORIZONTAL", {name: "Attach button (⇧⌘A)", pad: [4, 6, 4, 6], radius: 6, fill: "hover"}); clip.appendChild(txt("📎", {color: "accent"}));
  header.appendChild(clip); header.appendChild(txt("  ···", {color: "muted"}));
  const rd = al("VERTICAL", {name: "Reader", gap: 12, pad: [8, 28, 28, 28], fill: "bg"}); add(center, rd, {h: "FILL", v: "FILL"});
  rd.appendChild(txt("Поездка в горы", {family: SERIF, size: 30}));
  rd.appendChild(txt("Фото, видео и документы с выходных.", {size: 15}));
  const media = al("HORIZONTAL", {name: "Photo + GIF", gap: 12, align: "MAX"}); rd.appendChild(media);
  media.appendChild(photo(440, 286));
  const gif = al("VERTICAL", {name: "GIF (animated)", gap: 0, radius: 6, fill: "card", stroke: "border"}); gif.resize(240, 135);
  gif.primaryAxisSizingMode = "FIXED"; gif.counterAxisSizingMode = "FIXED"; gif.primaryAxisAlignItems = "CENTER"; gif.counterAxisAlignItems = "CENTER";
  const dot = figma.createEllipse(); dot.resize(30, 30); dot.fills = [fill("accent")]; gif.appendChild(dot);
  gif.appendChild(txt("GIF", {size: 11, style: "Semi Bold", color: "muted"}));
  media.appendChild(gif);
  for (const [icon, name, meta, action] of [["🎬", "Поездка в горы.mp4", "Видео · MP4 · 419.7 КБ", "▶ Смотреть"],
      ["🎵", "Голосовая заметка.mp3", "Аудио · MP3 · 23.9 КБ", "▶ Слушать"], ["📕", "Договор аренды.pdf", "PDF · 81 Б", "Открыть"]])
    add(rd, attachmentCard(icon, name, meta, action, 840), {h: "FILL"});
  const tail = al("HORIZONTAL", {name: "Inline link", gap: 4}); rd.appendChild(tail);
  tail.appendChild(txt("Ссылка в тексте:", {size: 15})); tail.appendChild(txt("📕 Договор аренды.pdf", {size: 15, color: "accent"}));
  return win;
}
function viewerScreen(x, y, kind) {
  const dlg = al("VERTICAL", {name: "Media viewer / " + kind + " — " + MODE, gap: 12, pad: [16, 20, 18, 20], fill: "bg", radius: 12, stroke: "border"});
  dlg.resize(980, 680); dlg.primaryAxisSizingMode = "FIXED"; dlg.counterAxisSizingMode = "FIXED"; dlg.x = x; dlg.y = y;
  dlg.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.15}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  const head = al("HORIZONTAL", {name: "Header", gap: 8, align: "CENTER"}); add(dlg, head, {h: "FILL"});
  const tc = al("VERTICAL", {name: "Title", gap: 2}); head.appendChild(tc);
  tc.appendChild(txt(kind === "Photo" ? "Закат.jpg" : "Поездка в горы.mp4", {family: SERIF, size: 18}));
  tc.appendChild(txt(kind === "Photo" ? "Фото · JPG · 34.9 КБ   ·   1 из 5" : "Видео · MP4 · 419.7 КБ   ·   3 из 5", {size: 12, color: "muted"}));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); head.appendChild(sp); sp.layoutGrow = 1;
  if (kind === "Photo") {
    const seg = al("HORIZONTAL", {name: "Zoom", gap: 0, radius: 8, stroke: "border", fill: "card"}); seg.clipsContent = true;
    for (const l of ["−", "Вписать", "100%", "+"]) { const s = al("HORIZONTAL", {name: l, pad: [5, 12, 5, 12]}); s.appendChild(txt(l, {size: 12})); seg.appendChild(s); }
    head.appendChild(seg);
  }
  head.appendChild(txt("‹   ›", {size: 15, color: "muted"}));
  head.appendChild(button("Открыть в программе", "Secondary"));
  head.appendChild(txt("Показать в Finder", {color: "muted"}));
  const stage = al("VERTICAL", {name: "Stage", gap: 0, radius: 12, fill: "code-bg", stroke: "border"}); add(dlg, stage, {h: "FILL", v: "FILL"});
  stage.primaryAxisAlignItems = "CENTER"; stage.counterAxisAlignItems = "CENTER";
  if (kind === "Photo") stage.appendChild(photo(860, 560));
  else {
    const video = figma.createRectangle(); video.name = "Video frame"; video.resize(900, 506); video.fills = [{type: "SOLID", color: {r: 0.08, g: 0.08, b: 0.08}}];
    stage.appendChild(video);
    const bar = al("HORIZONTAL", {name: "Player bar", gap: 12, align: "CENTER"}); add(dlg, bar, {h: "FILL"});
    const play = al("HORIZONTAL", {name: "Play", radius: 19, fill: "accent"}); play.resize(38, 38);
    play.primaryAxisSizingMode = "FIXED"; play.counterAxisSizingMode = "FIXED"; play.primaryAxisAlignItems = "CENTER"; play.counterAxisAlignItems = "CENTER";
    play.appendChild(txt("❚❚", {style: "Semi Bold", color: "on-accent"})); bar.appendChild(play);
    const track = al("HORIZONTAL", {name: "Seek", radius: 2, fill: "border"}); track.resize(600, 4);
    track.primaryAxisSizingMode = "FIXED"; track.counterAxisSizingMode = "FIXED";
    const done = figma.createRectangle(); done.resize(220, 4); done.cornerRadius = 2; done.fills = [fill("accent")]; track.appendChild(done);
    bar.appendChild(track); track.layoutGrow = 1;
    bar.appendChild(txt("0:01 / 0:04", {size: 12, color: "muted"})); bar.appendChild(txt("🔈", {size: 12}));
    const vol = figma.createRectangle(); vol.resize(90, 4); vol.cornerRadius = 2; vol.fills = [fill("accent")]; bar.appendChild(vol);
  }
  return dlg;
}
function filesScreen(x, y) {
  const win = al("HORIZONTAL", {name: "Files — " + MODE, gap: 0, fill: "bg"});
  win.resize(1360, 860); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = y;
  add(win, sidebar(null), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0, fill: "bg"}); add(win, center, {h: "FILL", v: "FILL"});
  add(center, tabBar(["Поездка", "▤ Файлы"], "▤ Файлы"), {h: "FILL"});
  const body = al("VERTICAL", {name: "Files", gap: 12, pad: [22, 28, 20, 28]}); add(center, body, {h: "FILL", v: "FILL"});
  body.appendChild(txt("Файлы", {family: SERIF, size: 30}));
  body.appendChild(txt("Вложения хранилища: фото, GIF, видео, аудио, документы. Перетащите файлы сюда или прикрепите к заметке кнопкой 📎.", {color: "muted"}));
  const row = al("HORIZONTAL", {name: "Toolbar", gap: 8, align: "CENTER"}); add(body, row, {h: "FILL"});
  row.appendChild(button("Добавить файлы…", "Accent")); row.appendChild(button("Открыть папку", "Secondary"));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); row.appendChild(sp); sp.layoutGrow = 1;
  const seg = al("HORIZONTAL", {name: "Filter", gap: 0, radius: 8, stroke: "border", fill: "card"}); seg.clipsContent = true;
  for (const [i, l] of ["Все", "Фото", "GIF", "Видео", "Аудио", "Документы", "Другое"].entries()) {
    const s = al("HORIZONTAL", {name: l, pad: [5, 12, 5, 12], fill: i === 0 ? "selected" : null}); s.appendChild(txt(l, {size: 12})); seg.appendChild(s);
  }
  row.appendChild(seg);
  const table = al("VERTICAL", {name: "Table", gap: 0}); add(body, table, {h: "FILL"});
  const rows = [[null, "ИМЯ", "ТИП", "РАЗМЕР", "ИЗМЕНЁН"], ["📕", "Договор аренды.pdf", "PDF", "81 Б", "15.10.2026 15:50"],
    ["gif", "Анимация.gif", "GIF", "5.2 КБ", "15.10.2026 15:50"], ["photo", "Закат.jpg", "Фото", "34.9 КБ", "15.10.2026 15:50"],
    ["🎵", "Голосовая заметка.mp3", "Аудио", "23.9 КБ", "15.10.2026 15:50"], ["🎬", "Поездка в горы.mp4", "Видео", "419.7 КБ", "15.10.2026 15:50"]];
  rows.forEach((vals, r) => {
    const tr = al("HORIZONTAL", {name: r ? "Row" : "Header", gap: 16, pad: [8, 10, 8, 10], align: "CENTER"});
    tr.strokes = [fill("border")]; tr.strokeTopWeight = 0; tr.strokeLeftWeight = 0; tr.strokeRightWeight = 0; tr.strokeBottomWeight = 1;
    add(table, tr, {h: "FILL"});
    if (r) {
      let icon;
      if (vals[0] === "photo") icon = photo(40, 40);
      else {
        icon = al("HORIZONTAL", {name: "Icon", radius: 8, fill: vals[0] === "gif" ? "card" : "tag-bg", stroke: vals[0] === "gif" ? "border" : null});
        icon.resize(40, 40); icon.primaryAxisSizingMode = "FIXED"; icon.counterAxisSizingMode = "FIXED";
        icon.primaryAxisAlignItems = "CENTER"; icon.counterAxisAlignItems = "CENTER";
        if (vals[0] === "gif") { const d = figma.createEllipse(); d.resize(10, 10); d.fills = [fill("accent")]; icon.appendChild(d); }
        else icon.appendChild(txt(vals[0], {size: 20}));
      }
      tr.appendChild(icon);
    }
    [r ? 560 : 616, 90, 90, 140].forEach((w, i) => tr.appendChild(txt(vals[i + 1], {w, size: r ? 13 : 11, style: r ? "Regular" : "Semi Bold", color: r ? "text" : "muted"})));
  });
  return win;
}

const created = [];
MODE = "Light"; created.push(noteScreen("Main — Light", 0).id);
MODE = "Dark"; created.push(noteScreen("Main — Dark", 1440).id);
MODE = "Light"; created.push(linksScreen(2880).id);
MODE = "Light"; created.push(calendarScreen(0).id);
MODE = "Dark"; created.push(calendarScreen(1520).id);
MODE = "Light"; created.push(settingsScreen(3040).id);
MODE = "Light"; created.push(attachmentsNoteScreen(0, 2000).id);
MODE = "Dark"; created.push(attachmentsNoteScreen(1440, 2000).id);
MODE = "Light"; created.push(viewerScreen(2880, 2000, "Photo").id);
MODE = "Dark"; created.push(viewerScreen(2880, 2760, "Video").id);
MODE = "Light"; created.push(filesScreen(0, 2940).id);
const shot = page.children[0];
await shot.screenshot({scale: 0.5});
return {pageId: page.id, createdNodeIds: created};
