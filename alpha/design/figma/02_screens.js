// Альфа (Alpha) — Screens page: Доски, Доска (Light / Dark), Карточка, Автоматизация, Календарь, Дашборд.
// Run after 01_ui_kit.js.
let page = figma.root.children.find(p => p.name === "Screens");
if (!page) { page = figma.createPage(); page.name = "Screens"; }
await figma.setCurrentPageAsync(page);
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const cols = await figma.variables.getLocalVariableCollectionsAsync();
const vars = await figma.variables.getLocalVariablesAsync("COLOR");
const V = {};
for (const mode of ["Light", "Dark"]) {
  const col = cols.find(c => c.name === "Alpha — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Alpha — " + mode + ")");
  V[mode] = {};
  for (const v of vars) if (v.variableCollectionId === col.id) V[mode][v.name.replace("color/", "")] = v;
}
let MODE = "Light";
const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
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

// a card face like alpha/widgets.py CardFace: cover?, labels, title, badges, avatars
function cardFace(o = {}) {
  const c = al("VERTICAL", {name: "Card / " + (o.title || "Карточка"), gap: 6, pad: [o.cover ? 0 : 8, 8, 8, 8], radius: 9, fill: "card", stroke: "border"});
  c.resize(256, 40); c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "FIXED"; c.counterAxisAlignItems = "MIN"; c.clipsContent = true;
  if (o.cover) { const cv = figma.createRectangle(); cv.resize(256, 30); cv.fills = [fill(o.cover)]; cv.layoutAlign = "STRETCH"; c.appendChild(cv); c.paddingTop = 0; }
  if (o.labels) { const lr = al("HORIZONTAL", {name: "Labels", gap: 4}); for (const [t, col] of o.labels) { const l = al("HORIZONTAL", {name: t, pad: [1, 8, 1, 8], radius: 4, fill: col}); l.appendChild(txt(t, {size: 11, style: "Semi Bold", color: "white"})); lr.appendChild(l); } c.appendChild(lr); }
  const t = txt(o.title || "Карточка", {size: 13, w: 238}); t.name = "Title"; c.appendChild(t);
  if (o.due || o.badges || o.avatars) {
    const br = al("HORIZONTAL", {name: "Badges", gap: 6, align: "CENTER"});
    if (o.due) { const d = al("HORIZONTAL", {name: "Due", pad: [2, 6, 2, 6], radius: 4, fill: o.dueFill || null}); d.appendChild(txt("◷ " + o.due, {size: 11, color: o.dueFill ? (o.dueFill === "due-soon" ? "ink" : "white") : "muted"})); br.appendChild(d); }
    for (const b of o.badges || []) br.appendChild(txt(b, {size: 11, color: "muted"}));
    for (const [ini, col] of o.avatars || []) { const a = al("HORIZONTAL", {name: "Avatar " + ini, radius: 11, fill: col, pad: [3, 4, 3, 4]}); a.appendChild(txt(ini, {size: 9, style: "Semi Bold", color: "white"})); br.appendChild(a); }
    c.appendChild(br);
  }
  return c;
}
function listColumn(name, cards, count) {
  const col = al("VERTICAL", {name: "List / " + name, gap: 8, pad: [8, 8, 8, 8], radius: 12, fill: "list"});
  col.resize(272, 40); col.primaryAxisSizingMode = "AUTO"; col.counterAxisSizingMode = "FIXED";
  const h = al("HORIZONTAL", {name: "Header", align: "CENTER"}); h.resize(256, 24); h.primaryAxisSizingMode = "FIXED"; h.primaryAxisAlignItems = "SPACE_BETWEEN";
  h.appendChild(txt(name, {style: "Semi Bold"})); h.appendChild(txt((count ?? cards.length) + "   •••", {size: 11, color: "muted"})); col.appendChild(h);
  for (const c of cards) col.appendChild(cardFace(c));
  col.appendChild(txt("+  Добавить карточку", {color: "muted"}));
  return col;
}

function frame(name, w, h, fillName = "bg") {
  const f = figma.createFrame(); f.name = name; f.resize(w, h); f.fills = [fill(fillName)]; f.clipsContent = true; return f;
}
function btn(t, kind = "default") {
  const b = al("HORIZONTAL", {name: "Button " + t, pad: [5, 12, 5, 12], radius: 7, fill: kind === "accent" ? "accent" : "card", stroke: kind === "default" ? "border" : null});
  b.appendChild(txt(t, {style: kind === "default" ? "Regular" : "Semi Bold", color: kind === "default" ? "text" : "on-accent"})); return b;
}
function sidebar(active) {
  const s = al("VERTICAL", {name: "Sidebar", gap: 4, pad: [18, 12, 14, 12], fill: "sidebar"}); s.resize(220, 820); s.primaryAxisSizingMode = "FIXED"; s.counterAxisSizingMode = "FIXED";
  const brand = al("HORIZONTAL", {name: "Brand", gap: 6, align: "CENTER"}); brand.appendChild(txt("α", {family: SERIF, style: SERIF_I, size: 30, color: "accent"})); brand.appendChild(txt("Альфа", {family: SERIF, size: 17})); s.appendChild(brand);
  for (const [i, t] of ["▦  Доски", "🔔  Уведомления · 2", "⚙  Настройки"].entries()) {
    const b = al("HORIZONTAL", {name: t, pad: [7, 10, 7, 10], radius: 7, fill: i === active ? "selected" : null}); b.resize(196, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); s.appendChild(b);
  }
  s.appendChild(txt("ОТМЕЧЕННЫЕ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const t of ["Запуск сайта"]) { const b = al("HORIZONTAL", {name: t, pad: [7, 10, 7, 10], radius: 7, fill: active === -1 ? "selected" : null}); b.resize(196, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt("▬  " + t)); s.appendChild(b); }
  s.appendChild(txt("ДОСКИ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const t of ["Дом", "Учёба"]) s.appendChild(txt("   ▬  " + t));
  return s;
}
let X = 0;
function place(f) { f.x = X; f.y = 0; X += f.width + 80; page.appendChild(f); }
function boardBar(active) {
  const bar = al("HORIZONTAL", {name: "Board bar", gap: 6, pad: [8, 14, 8, 14], align: "CENTER"}); bar.fills = [{type: "SOLID", color: hex("#141413"), opacity: 0.28}];
  bar.resize(1180, 50); bar.primaryAxisSizingMode = "FIXED";
  bar.appendChild(txt("Запуск сайта", {family: SERIF, size: 20, color: "white"})); bar.appendChild(txt("★", {size: 16, color: "l-yellow"}));
  for (const [k, t] of [["board", "▦ Доска"], ["table", "▤"], ["calendar", "▣"], ["dashboard", "▥"]]) {
    const b = al("HORIZONTAL", {name: k, pad: [5, 10, 5, 10], radius: 7}); b.fills = k === active ? [fill("white")] : [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.16}];
    b.appendChild(txt(t, {color: k === active ? "ink" : "white"})); bar.appendChild(b);
  }
  const sp = figma.createFrame(); sp.resize(10, 10); sp.fills = []; sp.layoutGrow = 1; bar.appendChild(sp);
  const se = al("HORIZONTAL", {name: "Search", pad: [5, 10, 5, 10], radius: 6, fill: "white"}); se.resize(170, 28); se.primaryAxisSizingMode = "FIXED"; se.appendChild(txt("Поиск карточек  ⌘F", {color: "faint"})); bar.appendChild(se);
  for (const t of ["⏷ Фильтр", "▣ Архивировать готовое", "⚡ Автоматизация", "•••"]) { const b = al("HORIZONTAL", {name: t, pad: [5, 10, 5, 10], radius: 7}); b.fills = [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.16}]; b.appendChild(txt(t, {color: "white"})); bar.appendChild(b); }
  return bar;
}
function boardScreen(name, mode) {
  MODE = mode;
  const f = frame(name, 1400, 820); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  f.appendChild(sidebar(-1));
  const main = figma.createFrame(); main.name = "Board"; main.resize(1180, 820); main.layoutMode = "VERTICAL"; main.primaryAxisSizingMode = "FIXED"; main.counterAxisSizingMode = "FIXED";
  main.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [{position: 0, color: {...hex("#D97757"), a: 1}}, {position: 1, color: {...hex("#C6613F"), a: 1}}]}];
  f.appendChild(main);
  main.appendChild(boardBar("board"));
  const lane = al("HORIZONTAL", {name: "Lane", gap: 12, pad: 12}); lane.counterAxisAlignItems = "MIN"; main.appendChild(lane);
  lane.appendChild(listColumn("Идеи", [{title: "Ночная тема", labels: [["Важно", "l-orange"], ["Улучшение", "l-blue"]]}]));
  lane.appendChild(listColumn("Нужно сделать", [{title: "Добро пожаловать в Альфу 👋", badges: ["≡", "☑ 0/3"]}, {title: "Сверстать шапку", labels: [["Срочно", "l-red"]], due: "18 окт, 15:54", dueFill: "due-soon", avatars: [["Я", "accent"], ["МА", "l-green"]]}, {title: "Форма обратной связи", labels: [["Баг", "l-purple"]], due: "17 окт, 10:54", dueFill: "overdue"}]));
  lane.appendChild(listColumn("В работе", [{title: "Новый логотип", cover: "l-blue", avatars: [["АП", "l-blue"]]}, {title: "Тексты для разделов", due: "21 окт, 10:54", badges: ["💬 1", "☑ 1/3"]}]));
  lane.appendChild(listColumn("На проверке", [{title: "Проверить на мобильных", cover: "l-sky", labels: [["Важно", "l-orange"]]}]));
  const add = al("HORIZONTAL", {name: "Add list", pad: [10, 12, 10, 12], radius: 12}); add.fills = [{type: "SOLID", color: hex("#FFFFFF"), opacity: 0.24}]; add.resize(272, 40); add.primaryAxisSizingMode = "FIXED";
  add.appendChild(txt("+  Добавить ещё один список", {style: "Semi Bold", color: "white"})); lane.appendChild(add);
  place(f);
}

// Доски (home)
{
  const f = frame("Доски", 1400, 820); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  f.appendChild(sidebar(0));
  const body = al("VERTICAL", {name: "Page", gap: 12, pad: [28, 36, 28, 36]}); body.layoutGrow = 1; body.layoutAlign = "STRETCH"; f.appendChild(body);
  body.appendChild(txt("Ваши доски", {family: SERIF, size: 28}));
  body.appendChild(txt("Всё хранится на этом Mac. Перетаскивайте карточки, настраивайте автоматизацию — как в Trello, только локально.", {color: "muted"}));
  const row = (title, tiles) => {
    body.appendChild(txt(title, {size: 10, style: "Semi Bold", color: "muted"}));
    const r = al("HORIZONTAL", {name: title, gap: 14});
    for (const [n, c1, sub] of tiles) {
      const t = al("VERTICAL", {name: n, pad: [10, 12, 10, 12], radius: 12, fill: c1 === "create" ? "panel" : null}); t.resize(196, 104); t.primaryAxisSizingMode = "FIXED"; t.counterAxisSizingMode = "FIXED"; t.primaryAxisAlignItems = "SPACE_BETWEEN";
      if (c1 !== "create") t.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [{position: 0, color: {...hex(c1[0]), a: 1}}, {position: 1, color: {...hex(c1[1]), a: 1}}]}];
      t.appendChild(txt(n, {family: c1 === "create" ? SANS : SERIF, size: c1 === "create" ? 13 : 16, color: c1 === "create" ? "text" : "white"})); if (sub) t.appendChild(txt(sub, {size: 11, color: "white"}));
      r.appendChild(t);
    }
    body.appendChild(r);
  };
  row("ОТМЕЧЕННЫЕ", [["Запуск сайта ★", ["#D97757", "#C6613F"], "5 списков · 11 карточек"]]);
  row("ВСЕ ДОСКИ", [["Запуск сайта", ["#D97757", "#C6613F"], "5 списков · 11 карточек"], ["Дом", ["#4E7A50", "#7BA05B"], "5 списков · 2 карточки"], ["Учёба", ["#3B6A8F", "#5B8CC4"], "4 списка · 4 карточки"], ["+  Создать доску", "create", ""]]);
  row("ШАБЛОНЫ", [["Канбан", ["#D97757", "#C6613F"], "Шаблон"], ["Учёба", ["#3B6A8F", "#5B8CC4"], "Шаблон"], ["Спринт", ["#6B4A7A", "#9B7BC4"], "Шаблон"], ["Личные дела", ["#4E7A50", "#7BA05B"], "Шаблон"], ["Контент-план", ["#B5647A", "#D97BA6"], "Шаблон"]]);
  place(f);
}
boardScreen("Доска — Light", "Light");
boardScreen("Доска — Dark", "Dark");
MODE = "Light";

// Карточка
{
  const f = frame("Карточка", 860, 820); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  f.paddingTop = 18; f.paddingLeft = 24; f.paddingRight = 18; f.itemSpacing = 18;
  const main = al("VERTICAL", {name: "Main", gap: 12}); main.layoutGrow = 1; f.appendChild(main);
  main.appendChild(txt("Тексты для разделов", {family: SERIF, size: 22}));
  main.appendChild(txt("в списке «В работе»", {color: "accent"}));
  const chips = al("HORIZONTAL", {name: "Chips", gap: 18});
  const due = al("VERTICAL", {name: "Due", gap: 4}); due.appendChild(txt("СРОК", {size: 10, style: "Semi Bold", color: "muted"})); due.appendChild(btn("☐  21 окт, 10:54")); chips.appendChild(due);
  const mem = al("VERTICAL", {name: "Members", gap: 4}); mem.appendChild(txt("УЧАСТНИКИ", {size: 10, style: "Semi Bold", color: "muted"})); mem.appendChild(txt("(Я) (АП)  +")); chips.appendChild(mem);
  main.appendChild(chips);
  main.appendChild(txt("≡  Описание", {family: SERIF, size: 16}));
  const ph = al("HORIZONTAL", {name: "Description", pad: [14, 12, 14, 12], fill: "panel"}); ph.resize(560, 44); ph.primaryAxisSizingMode = "FIXED"; ph.appendChild(txt("Добавить более подробное описание…", {color: "muted"})); main.appendChild(ph);
  main.appendChild(txt("☑  Разделы", {family: SERIF, size: 16}));
  const pr = figma.createRectangle(); pr.resize(560, 8); pr.cornerRadius = 4; pr.fills = [fill("border")]; main.appendChild(pr);
  for (const [t, d] of [["О нас", true], ["Услуги", false], ["Контакты", false]]) main.appendChild(txt((d ? "☑  " : "☐  ") + t, {color: d ? "muted" : "text"}));
  main.appendChild(txt("💬  Действия", {family: SERIF, size: 16}));
  const cm = al("HORIZONTAL", {name: "Comment box", pad: 10, radius: 8, fill: "card", stroke: "border"}); cm.resize(560, 54); cm.primaryAxisSizingMode = "FIXED"; cm.appendChild(txt("Напишите комментарий…", {color: "faint"})); main.appendChild(cm);
  main.appendChild(txt("Я  ·  18 окт, 10:53\nЧерновик «О нас» готов", {w: 520}));
  const side = al("VERTICAL", {name: "Sidebar", gap: 5}); f.appendChild(side);
  side.appendChild(txt("ДОБАВИТЬ НА КАРТОЧКУ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const t of ["Участники", "Метки", "Чек-лист", "Даты", "Вложение", "Обложка", "Поля"]) { const b = al("HORIZONTAL", {name: t, pad: [6, 10, 6, 10], radius: 6, fill: "panel"}); b.resize(184, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); side.appendChild(b); }
  side.appendChild(txt("КНОПКИ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const t of ["✓ Готово", "+ Добавить кнопку"]) { const b = al("HORIZONTAL", {name: t, pad: [6, 10, 6, 10], radius: 6, fill: "panel"}); b.resize(184, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); side.appendChild(b); }
  side.appendChild(txt("ДЕЙСТВИЯ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const t of ["Переместить", "Копировать", "Голосовать", "Сделать шаблоном", "Как Markdown", "Архивировать"]) { const b = al("HORIZONTAL", {name: t, pad: [6, 10, 6, 10], radius: 6, fill: "panel"}); b.resize(184, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); side.appendChild(b); }
  place(f);
}

// Автоматизация
{
  const f = frame("Автоматизация", 1000, 640); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  const s = al("VERTICAL", {name: "Nav", gap: 6, pad: [18, 12, 12, 12], fill: "sidebar"}); s.resize(220, 640); s.primaryAxisSizingMode = "FIXED"; s.counterAxisSizingMode = "FIXED";
  s.appendChild(txt("⚡ Автоматизация", {family: SERIF, size: 17}));
  for (const [i, t] of ["Правила", "По расписанию", "По срокам", "Кнопки карточек", "Кнопки доски", "Идеи", "Журнал"].entries()) { const b = al("HORIZONTAL", {name: t, pad: [7, 8, 7, 8], radius: 7, fill: i === 0 ? "selected" : null}); b.resize(196, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(t)); s.appendChild(b); }
  f.appendChild(s);
  const body = al("VERTICAL", {name: "Page", gap: 10, pad: [22, 28, 22, 28]}); body.layoutGrow = 1; body.layoutAlign = "STRETCH"; f.appendChild(body);
  const hd = al("HORIZONTAL", {name: "Head", align: "CENTER"}); hd.resize(724, 40); hd.primaryAxisSizingMode = "FIXED"; hd.primaryAxisAlignItems = "SPACE_BETWEEN"; hd.appendChild(txt("Правила", {family: SERIF, size: 28})); hd.appendChild(btn("Создать", "accent")); body.appendChild(hd);
  body.appendChild(txt("Срабатывают на события: карточку переместили, отметили, добавили метку…", {color: "muted"}));
  for (const t of ["Когда карточка перемещена в список «Готово»: отметить выполненной, добавить метку «Готово»", "Когда все пункты чек-листа выполнены: переместить в список «Готово» наверх", "Когда на карточку добавлена метка «Срочно»: переместить в список «В работе» наверх, добавить участника Я"]) {
    const r = al("HORIZONTAL", {name: "Rule", pad: [10, 10, 10, 14], gap: 10, radius: 12, fill: "card", stroke: "border"}); r.resize(724, 40); r.primaryAxisSizingMode = "FIXED";
    r.appendChild(txt("⚡", {color: "accent"})); const c = al("VERTICAL", {name: "Text", gap: 2}); c.layoutGrow = 1; c.appendChild(txt(t, {w: 540})); c.appendChild(txt("Срабатывало: 3", {size: 11, color: "muted"})); r.appendChild(c); r.appendChild(txt("☑ вкл  ✎ ⧉ 🗑", {color: "muted"})); body.appendChild(r);
  }
  place(f);
}

// Редактор правила
{
  const f = frame("Редактор правила", 760, 560);
  const body = al("VERTICAL", {name: "Editor", gap: 10, pad: 20}); body.resize(760, 560); body.primaryAxisSizingMode = "FIXED"; body.counterAxisSizingMode = "FIXED"; f.appendChild(body);
  body.appendChild(txt("Правило", {family: SERIF, size: 28}));
  const sec = t => body.appendChild(txt(t, {size: 10, style: "Semi Bold", color: "muted"}));
  const fieldRow = parts => { const r = al("HORIZONTAL", {name: parts[0], gap: 6}); for (const p of parts) { const fl = al("HORIZONTAL", {name: p, pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); fl.resize(220, 26); fl.primaryAxisSizingMode = "FIXED"; fl.appendChild(txt(p)); r.appendChild(fl); } body.appendChild(r); };
  sec("КОГДА"); fieldRow(["карточка перемещена в список", "Готово", "любой список"]);
  sec("ЕСЛИ КАРТОЧКА (необязательно)"); fieldRow(["с меткой", "Срочно"]);
  sec("СДЕЛАТЬ"); fieldRow(["отметить выполненной"]); fieldRow(["добавить метку", "Готово"]); fieldRow(["написать комментарий", "Готово {date} ✅"]);
  body.appendChild(txt("Когда карточка перемещена в список «Готово», если карточка с меткой «Срочно»: отметить выполненной, добавить метку «Готово», написать комментарий «Готово {date} ✅»", {color: "muted", w: 700}));
  const rr = al("HORIZONTAL", {name: "Buttons", gap: 8}); rr.appendChild(btn("Отмена")); rr.appendChild(btn("Сохранить", "accent")); body.appendChild(rr);
  place(f);
}

// Календарь
{
  const f = frame("Календарь", 1180, 760, "bg");
  const body = al("VERTICAL", {name: "Calendar", gap: 8, pad: 16}); body.resize(1180, 760); body.primaryAxisSizingMode = "FIXED"; body.counterAxisSizingMode = "FIXED"; f.appendChild(body);
  body.appendChild(txt("Октябрь 2026", {family: SERIF, size: 18}));
  const g = al("VERTICAL", {name: "Grid", gap: 0}); body.appendChild(g);
  const head = al("HORIZONTAL", {name: "Days", gap: 0}); for (const d of ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]) { const c = al("HORIZONTAL", {name: d, pad: 6}); c.resize(164, 26); c.primaryAxisSizingMode = "FIXED"; c.primaryAxisAlignItems = "CENTER"; c.appendChild(txt(d, {size: 11, style: "Semi Bold", color: "muted"})); head.appendChild(c); } g.appendChild(head);
  let day = 28;
  for (let w = 0; w < 6; w++) {
    const row = al("HORIZONTAL", {name: "Week " + w, gap: 0});
    for (let d = 0; d < 7; d++) {
      const n = (w === 0 && d < 3) ? 28 + d : (w * 7 + d - 2);
      const other = (w === 0 && d < 3) || n > 31;
      const cell = al("VERTICAL", {name: "Day", gap: 4, pad: 6, fill: other ? "panel" : "card", stroke: "border"}); cell.resize(164, 104); cell.primaryAxisSizingMode = "FIXED"; cell.counterAxisSizingMode = "FIXED";
      cell.appendChild(txt(String(other && n > 31 ? n - 31 : n), {color: other ? "faint" : "text"}));
      if (!other && n === 17) { const e = al("HORIZONTAL", {name: "Card", pad: [2, 6, 2, 6], radius: 4, fill: "overdue"}); e.appendChild(txt("Форма обратной связи", {size: 11, color: "white"})); cell.appendChild(e); }
      if (!other && n === 18) { const e = al("HORIZONTAL", {name: "Card", pad: [2, 6, 2, 6], radius: 4, fill: "due-soon"}); e.appendChild(txt("Сверстать шапку", {size: 11})); cell.appendChild(e); }
      if (!other && n === 21) { const e = al("HORIZONTAL", {name: "Card", pad: [2, 6, 2, 6], radius: 4, fill: "selected"}); e.appendChild(txt("Тексты для разделов", {size: 11})); cell.appendChild(e); }
      row.appendChild(cell);
    }
    g.appendChild(row);
  }
  body.appendChild(txt("Перетащите карточку на другой день, чтобы перенести срок.", {size: 11, color: "muted"}));
  place(f);
}

// Дашборд
{
  const f = frame("Дашборд", 1180, 760, "bg");
  const grid = al("HORIZONTAL", {name: "Charts", gap: 16, pad: 16}); grid.layoutWrap = "WRAP"; grid.resize(1180, 760); grid.primaryAxisSizingMode = "FIXED"; grid.counterAxisSpacing = 16; f.appendChild(grid);
  for (const [title, bars] of [["Карточек в списках", [[1, "accent"], [4, "accent"], [3, "accent"], [1, "accent"], [2, "accent"]]], ["Карточек по меткам", [[1, "l-red"], [2, "l-orange"], [1, "l-purple"], [2, "l-blue"], [0, "l-green"]]],
                               ["Карточек на участника", [[1, "accent"], [2, "l-blue"], [1, "l-green"]]], ["Сроки", [[0, "done"], [1, "due-soon"], [1, "overdue"], [1, "l-blue"], [8, "faint"]]]]) {
    const card = al("VERTICAL", {name: title, gap: 10, pad: 16, radius: 14, fill: "card", stroke: "border"}); card.resize(566, 344); card.primaryAxisSizingMode = "FIXED"; card.counterAxisSizingMode = "FIXED";
    card.appendChild(txt(title, {family: SERIF, size: 16}));
    const bars_ = al("HORIZONTAL", {name: "Bars", gap: 40}); bars_.counterAxisAlignItems = "MAX"; bars_.resize(520, 250); bars_.counterAxisSizingMode = "FIXED";
    for (const [n, c] of bars) { const b = figma.createRectangle(); b.resize(56, Math.max(2, n * 28)); b.cornerRadius = 5; b.fills = [fill(c)]; bars_.appendChild(b); }
    card.appendChild(bars_); grid.appendChild(card);
  }
  place(f);
}
return {screens: page.children.length};
