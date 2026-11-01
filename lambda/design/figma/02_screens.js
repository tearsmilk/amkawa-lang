// Лямбда (Lambda) — Screens page: Home, Design, Board, Slides, Site (Light / Dark), presenter. Run after 01_ui_kit.js.
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
  const col = cols.find(c => c.name === "Lambda — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Lambda — " + mode + ")");
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

function windowFrame(name, x, y) {
  const win = al("VERTICAL", {name, gap: 0, fill: "bg"});
  win.resize(1440, 900); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = y;
  win.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  return win;
}

function tabs(win, active) {
  const t = al("HORIZONTAL", {name: "Tabs", gap: 0, fill: "panel"}); border(t, {b: 1});
  for (const [i, name] of ["λ  Главная", "◇  Приложение", "▤  Ретро", "▭  Питч", "◎  Студия"].entries()) {
    const tab = al("HORIZONTAL", {name: "Tab", pad: [7, 14, 7, 14], fill: i === active ? "bg" : null}); border(tab, {r: 1});
    tab.appendChild(txt(name, {color: i === active ? "text" : "muted"})); t.appendChild(tab);
  }
  add(win, t, {h: "FILL"});
}
function topBar(win, tools, title, kind, right = []) {
  const b = al("HORIZONTAL", {name: "Top bar", gap: 4, pad: [8, 10, 8, 10], fill: "panel", align: "CENTER"}); border(b, {b: 1});
  for (const [i, g] of tools.entries()) { const tb = al("HORIZONTAL", {name: "Tool", pad: 6, radius: 7, fill: i === 0 ? "accent" : null}); tb.appendChild(txt(g, {size: 15, color: i === 0 ? "on-accent" : "text"})); b.appendChild(tb); }
  spacer(b); b.appendChild(txt(title, {family: SERIF, size: 14})); b.appendChild(txt("·  " + kind, {color: "muted"})); spacer(b);
  for (const r of right) b.appendChild(r);
  b.appendChild(txt("100%", {color: "muted"})); b.appendChild(txt("▶", {color: "accent"}));
  add(win, b, {h: "FILL"});
}
function panel(name, w, side) { const p = al("VERTICAL", {name, gap: 6, pad: [10, 12, 10, 12], fill: "panel"}); p.resize(w, 100); border(p, side); return p; }
function row(parent, items, o = {}) { const r = al("HORIZONTAL", {name: o.name || "Row", gap: o.gap ?? 6, align: "CENTER"}); for (const i of items) r.appendChild(typeof i === "string" ? txt(i, {color: o.color || "text"}) : i); parent.appendChild(r); return r; }
function field(v, w = 80) { const f = al("HORIZONTAL", {name: "Field", pad: [3, 6, 3, 6], radius: 6, fill: "input"}); f.resize(w, f.height); f.primaryAxisSizingMode = "FIXED"; f.appendChild(txt(v)); return f; }
function inspector(parent, title, sections) {
  const p = panel("Inspector", 264, {l: 1}); add(parent, p, {v: "FILL"});
  row(p, [txt("Дизайн", {style: "Medium"}), txt("Прототип", {color: "muted"})], {gap: 18});
  p.appendChild(txt(title, {family: SERIF, size: 16}));
  for (const [s, rows] of sections) { p.appendChild(section(s)); for (const r of rows) row(p, r.map(x => Array.isArray(x) ? field(...x) : x)); }
}
function layers(parent, pages, items) {
  const p = panel("Layers", 240, {r: 1}); add(parent, p, {v: "FILL"});
  p.appendChild(section("Страницы")); for (const [i, pg] of pages.entries()) p.appendChild(txt(pg, {color: i === 0 ? "text" : "muted"}));
  p.appendChild(section("Слои")); for (const [g, n, sel] of items) { const r = al("HORIZONTAL", {name: "Layer", gap: 8, pad: [3, 6, 3, 6], radius: 5, fill: sel ? "selected" : null}); r.appendChild(txt(g, {color: g === "❖" ? "accent" : "muted"})); r.appendChild(txt(n)); add(p, r, {h: "FILL"}); }
}
function canvas(parent, fillName) { const c = figma.createFrame(); c.name = "Canvas"; c.fills = [fill(fillName)]; c.clipsContent = true; c.resize(800, 700); add(parent, c, {h: "FILL", v: "FILL"}); return c; }
function phone(c, x, y) {
  const f = figma.createFrame(); f.name = "Главная"; f.resize(300, 620); f.x = x; f.y = y; f.fills = [fill("bg")]; c.appendChild(f);
  const l = txt("Главная", {size: 11, color: "accent"}); l.x = x; l.y = y - 18; c.appendChild(l);
  const h = txt("Ваши заметки", {family: SERIF, size: 24}); h.x = 18; h.y = 60; f.appendChild(h);
  for (let i = 0; i < 3; i++) { const card = figma.createRectangle(); card.resize(264, 56); card.cornerRadius = 12; card.x = 18; card.y = 110 + i * 68; card.fills = [fill("paper")]; f.appendChild(card); }
  const b = figma.createRectangle(); b.resize(120, 40); b.cornerRadius = 10; b.x = 18; b.y = 320; b.fills = [fill("accent")]; f.appendChild(b);
  const sel = figma.createRectangle(); sel.resize(300, 620); sel.x = x; sel.y = y; sel.fills = []; sel.strokes = [fill("accent")]; sel.strokeWeight = 1; c.appendChild(sel);
}

const SCREENS = [];
function designScreen(mode, x, y) {
  MODE = mode;
  const win = windowFrame("Design — " + mode, x, y); tabs(win, 1);
  topBar(win, ["➤", "✋", "#", "▭", "◯", "╱", "↗", "△", "☆", "✒", "✎", "T", "🖼"], "Приложение", "Дизайн");
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  layers(body, ["Приложение", "Иконки"], [["#", "Профиль"], ["#", "Главная", true], ["❖", "Кнопка / Основная"]]);
  const c = canvas(body, "canvas"); phone(c, 120, 80);
  inspector(body, "Фрейм", [["Фрейм", [[txt("X", {color: "muted"}), ["0", 70], txt("Y", {color: "muted"}), ["0", 70]], [txt("Ш", {color: "muted"}), ["393", 70], txt("В", {color: "muted"}), ["852", 70]]]],
    ["Автолейаут", [["↓  Вертикально", txt("·  20", {color: "muted"})], [txt("Обнять ширину", {color: "muted"})]]],
    ["Заливка", [[txt("■", {color: "bg"}), ["FAF9F5", 90], ["100%", 50]]]], ["Эффекты", []], ["Экспорт", [[["2×", 80], ["PNG", 80]]]]]);
  SCREENS.push(win);
}
function boardScreen(mode, x, y) {
  MODE = mode;
  const win = windowFrame("Board — " + mode, x, y); tabs(win, 2);
  topBar(win, [], "Ретро", "Доска");
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  const c = canvas(body, "board");
  for (let i = 0; i < 40; i++) for (let j = 0; j < 30; j++) { const d = figma.createEllipse(); d.resize(2, 2); d.x = i * 28; d.y = j * 28; d.fills = [fill("dot")]; c.appendChild(d); }
  for (const [i, [name, col]] of [["Что было хорошо", "sticky-green"], ["Что улучшить", "sticky"], ["Действия", "sticky-blue"]].entries()) {
    const s = figma.createFrame(); s.name = name; s.resize(260, 440); s.x = 40 + i * 290; s.y = 60; s.cornerRadius = 16; s.fills = [fill("panel")]; c.appendChild(s);
    const t = txt(name, {family: SERIF, size: 16}); t.x = 16; t.y = 16; s.appendChild(t);
    for (let k = 0; k < 3; k++) { const st = figma.createRectangle(); st.resize(110, 110); st.x = 16 + (k % 2) * 124; st.y = 60 + Math.floor(k / 2) * 124; st.fills = [fill(col)]; s.appendChild(st); }
  }
  const tb = al("HORIZONTAL", {name: "Board toolbar", pad: [6, 10, 6, 10], radius: 14, fill: "card", stroke: "border", gap: 8});
  for (const g of ["➤", "✋", "✎", "▬", "▢", "◆", "↗", "T", "▭", "☺"]) tb.appendChild(txt(g, {size: 18}));
  c.appendChild(tb); tb.x = 300; tb.y = 640;
  inspector(body, "Стикер", [["Стикер", [[txt("●  ●  ●  ●  ●  ●  ●  ●  ○", {color: "accent"})]]], ["Текст", [[["24", 80], ["Влево", 100]]]]]);
  SCREENS.push(win);
}
function slidesScreen(mode, x, y) {
  MODE = mode;
  const win = windowFrame("Slides — " + mode, x, y); tabs(win, 3);
  topBar(win, ["➤", "✋", "▭", "◯", "╱", "↗", "☆", "✒", "T", "🖼"], "Питч", "Презентация");
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  const left = panel("Slides", 200, {r: 1}); add(body, left, {v: "FILL"}); left.appendChild(section("Слайды"));
  for (let i = 0; i < 5; i++) { const s = figma.createRectangle(); s.resize(170, 96); s.cornerRadius = 4; s.fills = [fill(i === 0 ? "text" : "card")]; s.strokes = i === 0 ? [fill("accent")] : [fill("border")]; s.strokeWeight = i === 0 ? 2 : 1; left.appendChild(s); }
  const mid = al("VERTICAL", {name: "Center", gap: 0}); add(body, mid, {h: "FILL", v: "FILL"});
  const c = canvas(mid, "canvas");
  const slide = figma.createFrame(); slide.name = "Слайд"; slide.resize(640, 360); slide.x = 80; slide.y = 120; slide.fills = [fill("text")]; c.appendChild(slide);
  const line = figma.createRectangle(); line.resize(60, 4); line.x = 50; line.y = 120; line.fills = [fill("accent")]; slide.appendChild(line);
  const h = txt("Лямбда", {family: SERIF, size: 54, color: "bg"}); h.x = 50; h.y = 136; slide.appendChild(h);
  const notes = al("HORIZONTAL", {name: "Notes", pad: 12, fill: "card"}); notes.resize(800, 90); border(notes, {t: 1}); notes.appendChild(txt("Заметки докладчика…", {color: "muted"})); add(mid, notes, {h: "FILL"});
  inspector(body, "Тема", [["Тема", [[txt("Аа  Аа  Аа", {family: SERIF, size: 16})], [txt("Аа  Аа  Аа", {family: SERIF, size: 16})]]], ["Слайд", [[["Растворение", 200]]]]]);
  SCREENS.push(win);
}
function siteScreen(mode, x, y) {
  MODE = mode;
  const win = windowFrame("Site — " + mode, x, y); tabs(win, 4);
  const bps = ["Компьютер", "Планшет", "Телефон"].map((t, i) => { const b = al("HORIZONTAL", {name: t, pad: [4, 10, 4, 10], radius: 7, fill: i === 0 ? "accent" : null}); b.appendChild(txt(t, {color: i === 0 ? "on-accent" : "text"})); return b; });
  topBar(win, ["➤", "✋", "#", "▭", "◯", "T", "🖼"], "Студия", "Сайт", bps);
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  layers(body, ["Главная", "О нас"], [["≡", "Навигация"], ["≡", "Обложка", true], ["≡", "Преимущества"], ["≡", "Цены"], ["≡", "Подвал"]]);
  const c = canvas(body, "canvas");
  const pg = al("VERTICAL", {name: "Главная", gap: 24, pad: [24, 48, 48, 48], fill: "bg", align: "CENTER"}); pg.resize(680, 600); pg.primaryAxisSizingMode = "FIXED"; pg.counterAxisSizingMode = "FIXED";
  c.appendChild(pg); pg.x = 60; pg.y = 60;
  const nav = al("HORIZONTAL", {name: "Навигация", gap: 20}); nav.appendChild(txt("λ Студия", {family: SERIF, size: 16})); spacer(nav); nav.appendChild(txt("О нас")); add(pg, nav, {h: "FILL"});
  pg.appendChild(txt("Делаем понятные цифровые продукты", {family: SERIF, size: 34, w: 480}));
  const b = al("HORIZONTAL", {name: "Кнопка", pad: [10, 18, 10, 18], radius: 9, fill: "accent"}); b.appendChild(txt("Начать проект", {style: "Semi Bold", color: "on-accent"})); pg.appendChild(b);
  const img = figma.createRectangle(); img.resize(560, 220); img.cornerRadius = 16; img.fills = [fill("accent")]; pg.appendChild(img);
  inspector(body, "Кнопка", [["Ссылка", [[txt("Нет   Страница   Адрес", {color: "muted"})], [["О нас", 200]]]], ["При наведении", [[txt("Непрозр.", {color: "muted"}), ["85%", 60]]]]]);
  SCREENS.push(win);
}
function homeScreen(mode, x, y) {
  MODE = mode;
  const win = windowFrame("Home — " + mode, x, y); tabs(win, 0);
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  const side = panel("Sidebar", 220, {r: 1}); add(body, side, {v: "FILL"});
  row(side, [txt("λ", {family: SERIF, style: SERIF_I, size: 28, color: "accent"}), txt("Лямбда", {family: SERIF, size: 26})]);
  for (const s of ["Новый: дизайн", "Новый: доска", "Новый: презентация", "Новый: сайт", "Открыть файл…"]) side.appendChild(txt(s));
  const main = al("VERTICAL", {name: "Main", gap: 16, pad: [32, 40, 32, 40]}); add(body, main, {h: "FILL", v: "FILL"});
  main.appendChild(txt("Что создадим?", {family: SERIF, size: 28}));
  const cards = al("HORIZONTAL", {name: "Kinds", gap: 16}); add(main, cards, {h: "FILL"});
  for (const [t, d] of [["Дизайн", "Фреймы, автолейаут, компоненты"], ["Доска", "Стикеры, фигуры, соединители"], ["Презентация", "Темы, макеты, показ"], ["Сайт", "Блоки, адаптивность, HTML"]]) {
    const c = al("VERTICAL", {name: t, gap: 6, pad: 18, radius: 14, fill: "card", stroke: "border"}); c.appendChild(txt("◇", {size: 26, color: "accent"})); c.appendChild(txt(t, {family: SERIF, size: 17})); c.appendChild(txt(d, {color: "muted"})); add(cards, c, {h: "FILL"});
  }
  main.appendChild(txt("Шаблоны", {family: SERIF, size: 21}));
  const tpl = al("HORIZONTAL", {name: "Templates", gap: 16}); main.appendChild(tpl);
  for (const t of ["Мобильное приложение", "Мозговой штурм", "Питч", "Лендинг"]) { const c = al("VERTICAL", {name: t, gap: 8, pad: 10, radius: 14, fill: "card", stroke: "border"}); const r = figma.createRectangle(); r.resize(216, 132); r.cornerRadius = 10; r.fills = [fill("panel")]; c.appendChild(r); c.appendChild(txt(t)); tpl.appendChild(c); }
  SCREENS.push(win);
}

homeScreen("Light", 0, 0); designScreen("Light", 1540, 0); boardScreen("Light", 3080, 0);
slidesScreen("Light", 0, 1000); siteScreen("Light", 1540, 1000);
homeScreen("Dark", 3080, 1000); designScreen("Dark", 0, 2000); slidesScreen("Dark", 1540, 2000); siteScreen("Dark", 3080, 2000);
for (const s of SCREENS) page.appendChild(s);
figma.viewport.scrollAndZoomIntoView(SCREENS);
return {screens: SCREENS.map(s => s.name)};
