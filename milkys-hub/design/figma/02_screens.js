// Milkys Hub — Screens page: main window (Light + Dark) and "Links" (Light). Run after 01_ui_kit.js.
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
  const col = cols.find(c => c.name === "Milkys Hub — " + mode);
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
  logo.appendChild(txt("✻", {size: 22, color: "accent"})); logo.appendChild(txt("Milkys Hub", {family: SERIF, size: 21}));
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
  bottom.appendChild(txt("▣  Milkys Hub", {size: 12, color: "muted"}));
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
  tc.appendChild(txt("Проекты", {family: SERIF, size: 22})); tc.appendChild(txt("Milkys Hub", {size: 12, color: "muted"}));
  const sp = figma.createFrame(); sp.fills = []; sp.resize(4, 4); header.appendChild(sp); sp.layoutGrow = 1;
  const seg = al("HORIZONTAL", {name: "Segmented", gap: 0, radius: 8, stroke: "border", fill: "card"}); seg.clipsContent = true;
  for (const [i, l] of ["Редактор", "Разделить", "Просмотр"].entries()) { const s = al("HORIZONTAL", {name: l, pad: [5, 12, 5, 12], fill: i === 1 ? "selected" : null}); s.appendChild(txt(l, {size: 12})); seg.appendChild(s); }
  header.appendChild(seg); header.appendChild(txt("  ···", {color: "muted"}));
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
  body.appendChild(txt("Закладки хранятся в хранилище (.milkys/links.json). Двойной щелчок — открыть.", {color: "muted"}));
  const form = al("HORIZONTAL", {name: "Add form", gap: 8}); add(body, form, {h: "FILL"});
  for (const [ph, grow] of [["https://…", 3], ["Название (необязательно)", 2], ["теги через запятую", 2]]) {
    const inp = al("HORIZONTAL", {name: "Input", pad: [7, 10, 7, 10], radius: 8, fill: "input", stroke: "border"});
    inp.appendChild(txt(ph, {color: "muted"})); add(form, inp, {h: "FILL"});
  }
  form.appendChild(button("Добавить", "Accent"));
  const table = al("VERTICAL", {name: "Table", gap: 0}); add(body, table, {h: "FILL"});
  const rows = [["НАЗВАНИЕ", "АДРЕС", "ТЕГИ", "ДОБАВЛЕНО"], ["Claude", "https://claude.ai", "#ai", "14.10.2026 09:12"],
    ["github.com — tearsmilk", "https://github.com/tearsmilk", "#код", "14.10.2026 09:10"],
    ["Figma — Milkys Hub UI", "https://figma.com/design/P9vRt9…", "#дизайн", "13.10.2026 22:40"],
    ["Python docs", "https://docs.python.org/3/", "#код #docs", "12.10.2026 18:05"]];
  rows.forEach((vals, r) => {
    const row = al("HORIZONTAL", {name: r ? "Row" : "Header", gap: 16, pad: [9, 10, 9, 10], fill: r ? null : "bg"});
    row.strokes = [fill("border")]; row.strokeTopWeight = 0; row.strokeLeftWeight = 0; row.strokeRightWeight = 0; row.strokeBottomWeight = 1;
    add(table, row, {h: "FILL"});
    [260, 340, 140, 160].forEach((w, i) => row.appendChild(txt(vals[i], {w, size: r ? 13 : 11, style: r ? "Regular" : "Semi Bold", color: !r || i === 1 ? "muted" : (i === 2 ? "accent" : "text")})));
  });
  return win;
}

const created = [];
MODE = "Light"; created.push(noteScreen("Main — Light", 0).id);
MODE = "Dark"; created.push(noteScreen("Main — Dark", 1440).id);
MODE = "Light"; created.push(linksScreen(2880).id);
const shot = page.children[0];
await shot.screenshot({scale: 0.5});
return {pageId: page.id, createdNodeIds: created};
