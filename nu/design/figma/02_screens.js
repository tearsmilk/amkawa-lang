// Ню (Nu) — Screens page: Main (Light/Dark), Palette, Search, Git, Welcome, Settings. Run after 01_ui_kit.js.
let page = figma.root.children.find(p => p.name === "Screens");
if (!page) { page = figma.createPage(); page.name = "Screens"; }
await figma.setCurrentPageAsync(page);
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
const MONO = ["JetBrains Mono", "Roboto Mono", "Source Code Pro", "IBM Plex Mono"].find(f => has(f, "Regular")) || "Inter";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}, {family: MONO, style: "Regular"}]) await figma.loadFontAsync(fn);

const cols = await figma.variables.getLocalVariableCollectionsAsync();
const vars = await figma.variables.getLocalVariablesAsync("COLOR");
const V = {};
for (const mode of ["Light", "Dark"]) {
  const col = cols.find(c => c.name === "Nu — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Nu — " + mode + ")");
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
function add(parent, child, s = {}) { parent.appendChild(child); if (s.h) child.layoutSizingHorizontal = s.h; if (s.v) child.layoutSizingVertical = s.v; return child; }
function border(f, sides) { f.strokes = [fill("border")]; f.strokeTopWeight = sides.t || 0; f.strokeRightWeight = sides.r || 0; f.strokeBottomWeight = sides.b || 0; f.strokeLeftWeight = sides.l || 0; }
function spacer(parent) { const s = figma.createFrame(); s.fills = []; s.resize(4, 4); parent.appendChild(s); s.layoutGrow = 1; return s; }
function section(s) { return txt(s.toUpperCase(), {size: 11, style: "Semi Bold", color: "muted"}); }

const CODE = [
  [["class ", "syn-keyword"], ["TerminalWidget", "syn-class"], ["(QWidget):", "text"]],
  [["    ", "text"], ["\"\"\"Integrated terminal: the user's shell in a pty.\"\"\"", "syn-string"]],
  [["", "text"]],
  [["    ", "text"], ["def ", "syn-keyword"], ["start", "syn-function"], ["(self):", "text"]],
  [["        shell = self.shell ", "text"], ["or ", "syn-keyword"], ["default_shell", "syn-function"], ["()", "text"]],
  [["        pid, fd = pty.", "text"], ["fork", "syn-function"], ["()", "text"]],
  [["        ", "text"], ["if ", "syn-keyword"], ["pid == ", "text"], ["0", "syn-number"], [":  ", "text"], ["# child", "syn-comment"]],
  [["            os.", "text"], ["execvpe", "syn-function"], ["(shell, [", "text"], ["\"-\" ", "syn-string"], ["+ name], env)", "text"]],
  [["        self.notifier = ", "text"], ["QSocketNotifier", "syn-class"], ["(fd, QSocketNotifier.Read, self)", "text"]],
  [["        self.alive = ", "text"], ["True", "syn-builtin"]],
  [["", "text"]],
  [["    ", "text"], ["def ", "syn-keyword"], ["send", "syn-function"], ["(self, data):", "text"]],
  [["        ", "text"], ["if ", "syn-keyword"], ["isinstance", "syn-builtin"], ["(data, ", "text"], ["str", "syn-builtin"], ["):", "text"]],
  [["            data = data.", "text"], ["encode", "syn-function"], ["(", "text"], ["\"utf-8\"", "syn-string"], [")", "text"]],
  [["        os.", "text"], ["write", "syn-function"], ["(self.fd, data)", "text"]],
];

function activityBar(active) {
  const bar = al("VERTICAL", {name: "Activity bar", gap: 4, pad: [10, 0, 10, 0], fill: "activity", align: "CENTER"});
  border(bar, {r: 1}); bar.resize(52, 10); bar.counterAxisSizingMode = "FIXED";
  bar.appendChild(txt("ν", {family: SERIF, style: SERIF_I, size: 26, color: "accent"}));
  for (const [k, g] of [["files", "⧉"], ["search", "⌕"], ["git", "⑂"]]) {
    const b = al("HORIZONTAL", {name: k, pad: [10, 14, 10, 14], fill: k === active ? "sidebar" : null});
    if (k === active) { b.strokes = [fill("accent")]; b.strokeTopWeight = 0; b.strokeRightWeight = 0; b.strokeBottomWeight = 0; b.strokeLeftWeight = 2; }
    b.appendChild(txt(g, {size: 20, color: "muted"})); bar.appendChild(b);
  }
  spacer(bar);
  for (const g of ["▷", "⌨", "⚙"]) bar.appendChild(txt(g, {size: 18, color: g === "▷" ? "accent" : "muted"}));
  return bar;
}
function explorer() {
  const side = al("VERTICAL", {name: "Explorer", gap: 2, pad: [12, 8, 8, 8], fill: "sidebar"});
  border(side, {r: 1}); side.resize(260, 10); side.counterAxisSizingMode = "FIXED";
  const h = al("HORIZONTAL", {name: "Header", pad: [0, 6, 6, 6]}); add(side, h, {h: "FILL"});
  h.appendChild(section("Проводник")); spacer(h); h.appendChild(txt("＋  ⟳  ⊟", {size: 12, color: "muted"}));
  side.appendChild(txt("  NU", {size: 11, style: "Semi Bold", color: "muted"}));
  const rows = [["▸", "assets", 0, "text", false], ["▸", "design", 0, "text", false], ["▾", "nu", 0, "git-modified", false],
    ["py", "editor.py", 1, "text", false], ["py", "highlighter.py", 1, "text", false], ["py", "terminal.py", 1, "text", true],
    ["py", "ui.py", 1, "git-modified", false], ["py", "theme.py", 1, "text", false], ["▸", "packaging", 0, "text", false],
    ["M↓", "README.md", 0, "git-added", false], ["py", "run.py", 0, "text", false]];
  for (const [icon, name, depth, color, sel] of rows) {
    const r = al("HORIZONTAL", {name: "Tree item / " + name, gap: 8, pad: [4, 8, 4, 8 + depth * 14], radius: 5, fill: sel ? "selected" : null});
    add(side, r, {h: "FILL"});
    r.appendChild(txt(icon, {size: 10, style: "Semi Bold", color: icon === "▸" || icon === "▾" ? "muted" : "syn-function"}));
    r.appendChild(txt(name, {color}));
  }
  return side;
}
function editorArea(withFind) {
  const area = al("VERTICAL", {name: "Editor group", gap: 0, fill: "editor"});
  const tabs = al("HORIZONTAL", {name: "Tabs", gap: 0, fill: "tab-inactive"}); add(area, tabs, {h: "FILL"});
  for (const [name, active, mod] of [["terminal.py", true, false], ["ui.py", false, true], ["README.md", false, false]]) {
    const t = al("HORIZONTAL", {name: "Tab / " + name, gap: 8, pad: [8, 10, 8, 14], fill: active ? "editor" : "tab-inactive"});
    t.strokes = [fill(active ? "accent" : "border")]; t.strokeTopWeight = active ? 2 : 0; t.strokeLeftWeight = 0; t.strokeBottomWeight = 0; t.strokeRightWeight = 1;
    t.appendChild(txt(name.endsWith(".md") ? "M↓" : "py", {size: 10, style: "Semi Bold", color: "syn-function"}));
    t.appendChild(txt((mod ? "● " : "") + name, {color: active ? "text" : "muted"})); t.appendChild(txt("×", {color: "muted"}));
    tabs.appendChild(t);
  }
  const crumbs = al("HORIZONTAL", {name: "Breadcrumbs", pad: [4, 14, 4, 14]}); border(crumbs, {b: 1}); add(area, crumbs, {h: "FILL"});
  crumbs.appendChild(txt("nu  ›  terminal.py", {size: 12, color: "muted"}));
  const body = al("VERTICAL", {name: "Code", gap: 2, pad: [8, 0, 8, 0]}); add(area, body, {h: "FILL", v: "FILL"});
  CODE.forEach((line, i) => {
    const row = al("HORIZONTAL", {name: "Line " + (i + 96), gap: 0, fill: i === 9 ? "current-line" : null}); add(body, row, {h: "FILL"});
    const n = txt(String(i + 96), {family: MONO, color: i === 9 ? "text" : "line-no"}); n.textAlignHorizontal = "RIGHT"; n.textAutoResize = "HEIGHT"; n.resize(44, n.height);
    row.appendChild(n); const g = figma.createFrame(); g.fills = []; g.resize(22, 4); row.appendChild(g);
    for (const [s, c] of line) row.appendChild(txt(s || " ", {family: MONO, color: c}));
  });
  if (withFind) {
    const fb = al("HORIZONTAL", {name: "Find bar", pad: [6, 8, 6, 8], gap: 6, radius: 9, fill: "card", stroke: "border", align: "CENTER"});
    fb.layoutPositioning = "AUTO"; area.appendChild(fb); fb.layoutPositioning = "ABSOLUTE"; fb.x = 520; fb.y = 70;
    const q = al("HORIZONTAL", {name: "Query", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "accent"}); q.appendChild(txt("self")); fb.appendChild(q);
    for (const s of ["Aa", "ab", ".*", "3 из 44", "⌃", "⌄", "×"]) fb.appendChild(txt(s, {size: 12, color: "muted"}));
  }
  return area;
}
function terminalPanel() {
  const p = al("VERTICAL", {name: "Panel / Terminal", gap: 0, fill: "terminal"}); border(p, {t: 1});
  const tabs = al("HORIZONTAL", {name: "Panel tabs", pad: [6, 12, 0, 12], gap: 12}); add(p, tabs, {h: "FILL"});
  const t = al("HORIZONTAL", {name: "zsh", pad: [0, 0, 6, 0]}); t.strokes = [fill("accent")]; t.strokeTopWeight = 0; t.strokeLeftWeight = 0; t.strokeRightWeight = 0; t.strokeBottomWeight = 2;
  t.appendChild(txt("ZSH", {size: 11, style: "Semi Bold"})); tabs.appendChild(t);
  tabs.appendChild(txt("ZSH 2", {size: 11, style: "Semi Bold", color: "muted"})); spacer(tabs); tabs.appendChild(txt("＋   🗑   ×", {size: 12, color: "muted"}));
  const body = al("VERTICAL", {name: "Output", gap: 2, pad: [8, 12, 8, 12]}); add(p, body, {h: "FILL", v: "FILL"});
  for (const line of [[["~/amkawa-lang/nu ", "syn-function"], ["% ", "muted"], ["python3 run.py --selftest", "text"]],
                      [["selftest ok", "git-added"]],
                      [["~/amkawa-lang/nu ", "syn-function"], ["% ", "muted"], ["git status -s", "text"]],
                      [[" M ", "git-modified"], ["nu/ui.py", "text"]],
                      [["~/amkawa-lang/nu ", "syn-function"], ["% ", "muted"]]]) {
    const r = al("HORIZONTAL", {name: "Line", gap: 0}); for (const [s, c] of line) r.appendChild(txt(s, {family: MONO, size: 12, color: c})); body.appendChild(r);
  }
  return p;
}
function statusBar() {
  const s = al("HORIZONTAL", {name: "Status bar", gap: 14, pad: [4, 12, 4, 12], fill: "activity", align: "CENTER"}); border(s, {t: 1});
  s.appendChild(txt("⑂ main", {size: 12})); spacer(s);
  for (const v of ["Стр 105, стлб 25", "Пробелы: 4", "UTF-8", "LF", "Python"]) s.appendChild(txt(v, {size: 12, color: "muted"}));
  return s;
}
function windowFrame(name, x, y) {
  const win = al("VERTICAL", {name, gap: 0, fill: "bg"});
  win.resize(1440, 900); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = y;
  win.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  const row = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, row, {h: "FILL", v: "FILL"});
  return [win, row];
}
function mainScreen(name, x, y, side = "files", find = false) {
  const [win, row] = windowFrame(name, x, y);
  add(row, activityBar(side), {v: "FILL"});
  add(row, side === "files" ? explorer() : side === "search" ? searchSide() : gitSide(), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0}); add(row, center, {h: "FILL", v: "FILL"});
  add(center, editorArea(find), {h: "FILL", v: "FILL"});
  const term = terminalPanel(); add(center, term, {h: "FILL"}); term.resize(term.width, 240); term.layoutSizingVertical = "FIXED";
  add(win, statusBar(), {h: "FILL"});
  return win;
}
function searchSide() {
  const side = al("VERTICAL", {name: "Search", gap: 6, pad: [12, 12, 8, 12], fill: "sidebar"}); border(side, {r: 1});
  side.resize(260, 10); side.counterAxisSizingMode = "FIXED";
  side.appendChild(section("Поиск"));
  for (const [ph, val] of [["Найти", "def "], ["Заменить", ""], ["Включить файлы, напр. *.py", "nu/*"], ["Исключить", ""]]) {
    const i = al("HORIZONTAL", {name: "Input / " + ph, pad: [5, 8, 5, 8], radius: 7, fill: "input", stroke: val === "def " ? "accent" : "border"});
    i.appendChild(txt(val || ph, {color: val ? "text" : "muted"})); add(side, i, {h: "FILL"});
  }
  side.appendChild(txt("88 совпадений в 11 файлах", {size: 12, color: "muted"}));
  for (const [file, hits] of [["nu/terminal.py", ["31: def __init__(self, columns, …", "91: def start(self):", "167: def _reply(self, data):"]],
                              ["nu/editor.py", ["78: def __init__(self, colors, …", "214: def toggle_comment(self):"]]]) {
    side.appendChild(txt("py  " + file, {style: "Medium"}));
    for (const h of hits) side.appendChild(txt("    " + h, {size: 12, color: "muted"}));
  }
  return side;
}
function gitSide() {
  const side = al("VERTICAL", {name: "Source control", gap: 8, pad: [12, 12, 8, 12], fill: "sidebar"}); border(side, {r: 1});
  side.resize(260, 10); side.counterAxisSizingMode = "FIXED";
  side.appendChild(section("Система контроля версий"));
  side.appendChild(txt("Ветка: main", {size: 12, color: "muted"}));
  const m = al("HORIZONTAL", {name: "Commit message", pad: [6, 8, 30, 8], radius: 7, fill: "input", stroke: "border"});
  m.appendChild(txt("Ню: терминал и палитра команд", {})); add(side, m, {h: "FILL"});
  const b = al("HORIZONTAL", {name: "Commit", pad: [7, 14, 7, 14], radius: 8, fill: "accent"}); b.primaryAxisAlignItems = "CENTER";
  b.appendChild(txt("✓  Зафиксировать всё", {style: "Semi Bold", color: "on-accent"})); add(side, b, {h: "FILL"});
  side.appendChild(section("Изменения  3"));
  for (const [f, l, c] of [["nu/ui.py", "M", "git-modified"], ["nu/palette.py", "M", "git-modified"], ["README.md", "?", "git-added"]]) {
    const r = al("HORIZONTAL", {name: "Change / " + f, gap: 8, pad: [4, 6, 4, 6]}); add(side, r, {h: "FILL"});
    r.appendChild(txt(f.endsWith(".md") ? "M↓" : "py", {size: 10, style: "Semi Bold", color: "syn-function"}));
    const t = txt(f, {color: c}); r.appendChild(t); spacer(r); r.appendChild(txt(l, {style: "Semi Bold", color: c}));
  }
  return side;
}
function paletteOverlay(x, y) {
  const win = mainScreen("Command palette — " + MODE, x, y);
  const pal = al("VERTICAL", {name: "Palette", gap: 0, pad: [0, 0, 6, 0], radius: 12, fill: "card", stroke: "border"});
  pal.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.18}, offset: {x: 0, y: 12}, radius: 36, spread: 0, visible: true, blendMode: "NORMAL"}];
  win.appendChild(pal); pal.layoutPositioning = "ABSOLUTE"; pal.resize(640, 10); pal.counterAxisSizingMode = "FIXED"; pal.x = 400; pal.y = 70;
  const q = al("HORIZONTAL", {name: "Query", pad: [10, 12, 10, 12]}); border(q, {b: 1}); add(pal, q, {h: "FILL"});
  q.appendChild(txt(">разд", {size: 14}));
  for (const [i, [t, k]] of [["Вид: Разделить редактор", "⌘\\"], ["Вид: Показать/скрыть боковую панель", "⌘B"],
                             ["Перейти: Следующая группа редакторов", "⌘K"], ["Вид: Перенос строк", "⌥Z"]].entries()) {
    const r = al("HORIZONTAL", {name: "Item", gap: 10, pad: [6, 12, 6, 12], radius: 6, fill: i === 0 ? "selected" : null}); add(pal, r, {h: "FILL"});
    r.appendChild(txt(t)); spacer(r); r.appendChild(txt(k, {size: 12, color: "muted"}));
  }
  return win;
}
function welcomeScreen(x, y) {
  const [win, row] = windowFrame("Welcome — " + MODE, x, y);
  add(row, activityBar("files"), {v: "FILL"});
  add(row, explorer(), {v: "FILL"});
  const c = al("VERTICAL", {name: "Welcome", gap: 14, pad: [120, 80, 40, 120], fill: "editor"}); add(row, c, {h: "FILL", v: "FILL"});
  const head = al("HORIZONTAL", {name: "Logo", gap: 18, align: "CENTER"}); c.appendChild(head);
  head.appendChild(txt("ν", {family: SERIF, style: SERIF_I, size: 110, color: "accent"}));
  const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
  hc.appendChild(txt("Ню", {family: SERIF, size: 34})); hc.appendChild(txt("Редактор кода · версия 1.0.0", {color: "muted"}));
  const cols2 = al("HORIZONTAL", {name: "Columns", gap: 80}); c.appendChild(cols2);
  const a = al("VERTICAL", {name: "Start", gap: 6}); cols2.appendChild(a); a.appendChild(section("Начало"));
  for (const s of ["Открыть папку…", "Открыть файл…", "Новый файл", "Новый терминал", "Палитра команд"]) a.appendChild(txt(s, {color: "accent"}));
  const b = al("VERTICAL", {name: "Recent", gap: 6}); cols2.appendChild(b); b.appendChild(section("Недавние"));
  for (const s of ["amkawa-lang    ~/code", "nu    ~/code/amkawa-lang", "site    ~/Documents"]) b.appendChild(txt(s, {color: "accent"}));
  c.appendChild(section("Горячие клавиши"));
  for (const [k, w] of [["⌘P", "быстрое открытие файла"], ["⇧⌘P", "палитра команд"], ["⌃`", "терминал"], ["F5", "запустить файл"]]) {
    const r = al("HORIZONTAL", {name: k, gap: 14}); r.appendChild(txt(k, {family: MONO, color: "muted"})); r.appendChild(txt(w, {color: "muted"})); c.appendChild(r);
  }
  add(win, statusBar(), {h: "FILL"});
  return win;
}
function settingsScreen(x, y) {
  const d = al("VERTICAL", {name: "Settings — " + MODE, gap: 10, pad: [22, 26, 20, 26], radius: 12, fill: "bg", stroke: "border"});
  d.resize(480, 10); d.counterAxisSizingMode = "FIXED"; d.x = x; d.y = y;
  d.appendChild(txt("Настройки", {family: SERIF, size: 30}));
  for (const [k, v] of [["Тема", "Системная"], ["Шрифт", "SF Mono"], ["Размер шрифта", "13"], ["Шрифт терминала", "12"], ["Ширина табуляции", "4"], ["Терминал", "Оболочка по умолчанию"]]) {
    const r = al("HORIZONTAL", {name: k, gap: 12, align: "CENTER"}); add(d, r, {h: "FILL"});
    const l = txt(k, {w: 150}); r.appendChild(l);
    const f = al("HORIZONTAL", {name: "Field", pad: [5, 8, 5, 8], radius: 7, fill: "input", stroke: "border"}); f.appendChild(txt(v)); add(r, f, {h: "FILL"});
  }
  for (const [on, s] of [[true, "Пробелы вместо табуляции"], [false, "Перенос строк"], [true, "Направляющие отступов"], [true, "Автозакрытие скобок и кавычек"],
                         [true, "Автодополнение слов"], [false, "Автосохранение"]]) {
    const r = al("HORIZONTAL", {name: s, gap: 8, align: "CENTER"}); d.appendChild(r);
    const box = figma.createRectangle(); box.resize(15, 15); box.cornerRadius = 4; box.fills = on ? [fill("accent")] : [fill("input")];
    box.strokes = [fill(on ? "accent" : "muted")]; box.strokeWeight = 1; r.appendChild(box); r.appendChild(txt(s));
  }
  const btns = al("HORIZONTAL", {name: "Buttons", gap: 8}); add(d, btns, {h: "FILL"}); spacer(btns);
  const c1 = al("HORIZONTAL", {name: "Cancel", pad: [6, 14, 6, 14], radius: 8, fill: "card", stroke: "border"}); c1.appendChild(txt("Отмена")); btns.appendChild(c1);
  const c2 = al("HORIZONTAL", {name: "Save", pad: [6, 14, 6, 14], radius: 8, fill: "accent"}); c2.appendChild(txt("Сохранить", {style: "Semi Bold", color: "on-accent"})); btns.appendChild(c2);
  return d;
}

const created = [];
MODE = "Light"; created.push(mainScreen("Main — Light", 0, 0, "files", true).id);
MODE = "Dark"; created.push(mainScreen("Main — Dark", 1520, 0, "files").id);
MODE = "Light"; created.push(paletteOverlay(0, 1000).id);
MODE = "Dark"; created.push(mainScreen("Search — Dark", 1520, 1000, "search").id);
MODE = "Light"; created.push(mainScreen("Source control — Light", 0, 2000, "git").id);
MODE = "Light"; created.push(welcomeScreen(1520, 2000).id);
MODE = "Light"; created.push(settingsScreen(3040, 0).id);
MODE = "Dark"; created.push(settingsScreen(3040, 700).id);
await page.children[0].screenshot({scale: 0.5});
return {pageId: page.id, createdNodeIds: created};
