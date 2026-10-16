// Мю (Mu) — Screens page: Home, Нарезка, Риг (Light / Dark), Физика, Студия, Эфир, Гайдбук. Run after 01_ui_kit.js.
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
  const col = cols.find(c => c.name === "Mu — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Mu — " + mode + ")");
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
function btn(label, accent = false) { const b = al("HORIZONTAL", {name: "Button", pad: [5, 12, 5, 12], radius: 7, fill: accent ? "accent" : "card", stroke: accent ? null : "border"}); b.appendChild(txt(label, {style: accent ? "Semi Bold" : "Regular", color: accent ? "on-accent" : "text"})); return b; }

function windowFrame(name, x, y) {
  const win = al("VERTICAL", {name, gap: 0, fill: "bg"});
  win.resize(1440, 900); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = y;
  win.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  return win;
}
function topBar(win, active) {
  const b = al("HORIZONTAL", {name: "Top bar", gap: 14, pad: [6, 12, 6, 12], fill: "panel", align: "CENTER"}); border(b, {b: 1});
  b.appendChild(txt("μ", {family: SERIF, style: SERIF_I, size: 22, color: "accent"}));
  b.appendChild(txt("mika • ", {family: SERIF, size: 15}));
  for (const name of ["Нарезка", "Риг", "Физика", "Студия", "Эфир", "Гайдбук"]) {
    const t = al("VERTICAL", {name: "Tab", gap: 4, pad: [4, 6, 0, 6], align: "CENTER"});
    t.appendChild(txt(name, {color: name === active ? "text" : "muted"}));
    const u = figma.createRectangle(); u.resize(48, 2); u.fills = name === active ? [fill("accent")] : []; t.appendChild(u); b.appendChild(t);
  }
  spacer(b); for (const g of ["↶", "↷", "▣", "⇪"]) b.appendChild(txt(g, {size: 16}));
  add(win, b, {h: "FILL"});
}
function panel(name, w, side) { const p = al("VERTICAL", {name, gap: 6, pad: [10, 10, 10, 10], fill: "panel"}); p.resize(w, 100); border(p, side); return p; }
function body(win) { const b = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, b, {h: "FILL", v: "FILL"}); return b; }
function canvas(parent, o = {}) {
  const c = al("VERTICAL", {name: "Canvas", gap: 0, fill: o.fill || "canvas", align: "CENTER"}); add(parent, c, {h: "FILL", v: "FILL"});
  c.primaryAxisAlignItems = "CENTER";
  const paper = figma.createFrame(); paper.name = "Model"; paper.resize(o.w || 300, o.h || 560); paper.fills = [fill(o.paper || "checker-a")];
  paper.strokes = [fill("border")]; paper.strokeWeight = 1; c.appendChild(paper);
  // a simple character silhouette
  const hair = figma.createEllipse(); hair.resize(150, 170); hair.x = (paper.width - 150) / 2; hair.y = 40; hair.fills = [fill("hair")]; paper.appendChild(hair);
  const face = figma.createEllipse(); face.resize(110, 120); face.x = (paper.width - 110) / 2; face.y = 85; face.fills = [fill("skin")]; paper.appendChild(face);
  const bodyR = figma.createRectangle(); bodyR.resize(120, 220); bodyR.cornerRadius = 30; bodyR.x = (paper.width - 120) / 2; bodyR.y = 215; bodyR.fills = [fill("ink")]; bodyR.opacity = 0.75; paper.appendChild(bodyR);
  return {c, paper};
}
function tree(parent) {
  const p = panel("Parts", 240, {r: 1}); add(parent, p, {v: "FILL"}); p.appendChild(section("Части"));
  for (const [d, g, n, sel] of [[0, "↻", "Тело: наклон"], [1, "▦", "Тело: поворот и дыхание"], [2, "↻", "Голова: наклон"], [3, "▦", "Голова: лицо"],
                                  [4, "▦", "Голова: черты лица"], [5, "▣", "Левый глаз: белок", true], [5, "▣", "Левый глаз: радужка"], [4, "▣", "Лицо"],
                                  [3, "▦", "Чёлка"], [3, "▦", "Волосы сзади"], [2, "↻", "Левая рука: плечо"], [1, "▣", "Тело"]]) {
    const r = al("HORIZONTAL", {name: "Row", gap: 6, pad: [3, 6, 3, 6 + d * 12], radius: 5, fill: sel ? "selected" : null, align: "CENTER"});
    const cb = figma.createRectangle(); cb.resize(12, 12); cb.cornerRadius = 4; cb.fills = [fill("accent")]; r.appendChild(cb);
    r.appendChild(txt(g, {color: "muted"})); r.appendChild(txt(n)); add(p, r, {h: "FILL"});
  }
  return p;
}
function params(parent, withKeys = true) {
  parent.appendChild(section("Параметры"));
  for (const [g, rows] of [["Голова", [["Поворот головы X", "20", true], ["Поворот головы Y", "0"], ["Наклон головы", "0"]]],
                           ["Глаза", [["Левый глаз открыт", "1"], ["Правый глаз открыт", "1"], ["Взгляд X", "0"]]], ["Рот", [["Рот открыт", "0"], ["Форма рта", "0"]]]]) {
    parent.appendChild(txt(g, {family: SERIF, style: SERIF_I, color: "muted"}));
    for (const [n, v, act] of rows) {
      const r = al("HORIZONTAL", {name: "Param", gap: 6, align: "CENTER"}); add(parent, r, {h: "FILL"});
      r.appendChild(txt(n, {color: act ? "accent" : "text", style: act ? "Semi Bold" : "Regular"})); spacer(r);
      r.appendChild(txt(v, {color: "muted"})); if (withKeys) r.appendChild(txt(act ? "◆" : "◇", {color: act ? "accent" : "muted"}));
      const s = figma.createRectangle(); s.resize(250, 4); s.cornerRadius = 2; s.fills = [fill("border")]; parent.appendChild(s);
    }
  }
}
function contextBar(parent, items) {
  const b = al("HORIZONTAL", {name: "Context bar", gap: 8, pad: [6, 10, 6, 10], fill: "bg", align: "CENTER"}); border(b, {b: 1});
  for (const i of items) b.appendChild(typeof i === "string" ? txt(i, {size: 15}) : i); add(parent, b, {h: "FILL"}); return b;
}

// ---------------------------------------------------------------- Home
let x = 0;
for (const mode of ["Light", "Dark"]) {
  MODE = mode;
  const w = windowFrame(`Home — ${mode}`, x, 0); x += 1520;
  const b = body(w);
  const side = panel("Home side", 230, {r: 1}); add(b, side, {v: "FILL"});
  const logo = al("HORIZONTAL", {name: "Logo", gap: 8, align: "CENTER"}); logo.appendChild(txt("μ", {family: SERIF, style: SERIF_I, size: 26, color: "accent"})); logo.appendChild(txt("Мю", {family: SERIF, size: 28})); side.appendChild(logo);
  for (const t of ["▣  Модель из PSD", "✂  Модель из картинки", "▭  Открыть проект", "⇪  Импорт Inochi2D"]) side.appendChild(txt(t));
  spacer(side); side.appendChild(txt("▯  Гайдбук"));
  const main = al("VERTICAL", {name: "Main", gap: 14, pad: [40, 48, 40, 48]}); add(b, main, {h: "FILL", v: "FILL"});
  main.appendChild(txt("Что оживим сегодня?", {family: SERIF, size: 28}));
  main.appendChild(txt("Возьмите 2D-иллюстрацию — PSD со слоями или одну картинку — и превратите её в модель для витубинга.", {color: "muted"}));
  const g = al("HORIZONTAL", {name: "Cards", gap: 14}); g.layoutWrap = "WRAP"; g.counterAxisSpacing = 14; add(main, g, {h: "FILL"});
  for (const [ic, t, d] of [["▣", "Модель из PSD", "Слои PSD становятся частями модели"], ["✂", "Модель из картинки", "Нарежьте одну иллюстрацию на части"],
                            ["▭", "Открыть проект", "Файл .mu со всем ригом, позами и сценами"], ["⇪", "Импорт Inochi2D", "Готовая модель .inp"]]) {
    const c = al("VERTICAL", {name: "Card", gap: 6, pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border"}); c.resize(540, 110); c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "FIXED";
    c.appendChild(txt(ic, {size: 24, color: "accent"})); c.appendChild(txt(t, {family: SERIF, size: 17})); c.appendChild(txt(d, {color: "muted"})); g.appendChild(c);
  }
  main.appendChild(section("Недавние"));
}

// ---------------------------------------------------------------- Нарезка
MODE = "Light";
{
  const w = windowFrame("Нарезка — Light", 0, 1000); topBar(w, "Нарезка"); const b = body(w); tree(b);
  const mid = al("VERTICAL", {name: "Middle", gap: 0}); add(b, mid, {h: "FILL", v: "FILL"});
  contextBar(mid, ["➤", "⌇", "⬠", "✎", "✦", txt("Shift — добавить · Alt — вычесть · Esc — снять", {color: "muted"})]);
  const {paper} = canvas(mid);
  const sel = figma.createEllipse(); sel.resize(110, 60); sel.x = 95; sel.y = 120; sel.fills = [{type: "SOLID", color: {r: 0.85, g: 0.47, b: 0.34}, opacity: 0.43}];
  sel.strokes = [fill("accent")]; sel.dashPattern = [6, 4]; sel.strokeWeight = 1.5; paper.appendChild(sel);
  const r = panel("Actions", 300, {l: 1}); add(b, r, {v: "FILL"});
  r.appendChild(section("Выделение")); r.appendChild(txt("Выделено 16 952 пикс.", {color: "muted"}));
  add(r, btn("Вырезать в новый слой", true), {h: "FILL"}); add(r, btn("Копировать в новый слой"), {h: "FILL"});
  r.appendChild(txt("☑ Закрашивать дыру")); r.appendChild(txt("Роль нового слоя: Левый глаз: белок", {color: "muted"}));
  r.appendChild(section("Слой")); for (const t of ["Отразить копию", "Объединить с нижним", "Импорт картинки как слоя…", "Удалить слой"]) add(r, btn(t), {h: "FILL"});
}

// ---------------------------------------------------------------- Риг (Light / Dark)
x = 1520;
for (const mode of ["Light", "Dark"]) {
  MODE = mode;
  const w = windowFrame(`Риг — ${mode}`, x, 1000); x += 1520; topBar(w, "Риг"); const b = body(w); tree(b);
  const mid = al("VERTICAL", {name: "Middle", gap: 0}); add(b, mid, {h: "FILL", v: "FILL"});
  contextBar(mid, ["✥", "◬", "▦", "↻", txt("Сетка", {color: "muted"}), "◬", btn("★  Авто-риг", true)]);
  const {paper} = canvas(mid);
  const wv = figma.createVector(); let d = "";
  for (let i = 0; i <= 4; i++) { d += `M 60 ${60 + i * 45} C 120 ${52 + i * 45} 180 ${52 + i * 45} 240 ${60 + i * 45} `; d += `M ${60 + i * 45} 60 L ${60 + i * 45} 240 `; }
  wv.vectorPaths = [{windingRule: "NONE", data: d}]; wv.strokes = [fill("accent")]; wv.strokeWeight = 1.2; paper.appendChild(wv);
  const kb = al("HORIZONTAL", {name: "Key bar", pad: [4, 10, 4, 10]}); kb.appendChild(txt("Активный параметр: Поворот головы X = 20   ·   правка попадёт в ключ ◆ 20", {color: "muted"})); add(mid, kb, {h: "FILL"});
  const r = panel("Right", 340, {l: 1}); add(b, r, {v: "FILL"});
  r.appendChild(section("Деформер-сетка"));
  for (const [k, v] of [["Имя", "Голова: лицо"], ["Деления", "5 × 5"], ["Родитель", "Голова: наклон"]]) { const row = al("HORIZONTAL", {name: "Row", gap: 8}); row.appendChild(txt(k, {color: "muted"})); row.appendChild(txt(v)); r.appendChild(row); }
  r.appendChild(section("Ключи")); r.appendChild(txt("Поворот головы X: −30, 0, 30\nПоворот головы Y: −30, 0, 30", {color: "muted"}));
  params(r);
}

// ---------------------------------------------------------------- Физика
MODE = "Light";
{
  const w = windowFrame("Физика — Light", 0, 2000); topBar(w, "Физика"); const b = body(w);
  const mid = al("VERTICAL", {name: "Middle", gap: 0}); add(b, mid, {h: "FILL", v: "FILL"});
  contextBar(mid, [btn("▶  Проверка"), btn("Качать головой")]); canvas(mid);
  const r = panel("Physics", 330, {l: 1}); add(b, r, {v: "FILL"});
  r.appendChild(section("Группы физики")); for (const t of ["● Чёлка", "● Пряди", "● Волосы сзади", "● Юбка"]) r.appendChild(txt(t));
  for (const [k, v] of [["Выход", "Волосы спереди"], ["Жёсткость", "70"], ["Затухание", "8"], ["Гравитация", "0.5"], ["Размах", "1.1"]]) { const row = al("HORIZONTAL", {name: "Row", gap: 8}); row.appendChild(txt(k, {color: "muted"})); row.appendChild(txt(v)); r.appendChild(row); }
  r.appendChild(section("Входы")); for (const t of ["Поворот головы X · 0.6 · сдвиг", "Наклон головы · 0.5 · наклон", "Поворот тела X · 0.4 · сдвиг"]) r.appendChild(txt(t));
}

// ---------------------------------------------------------------- Студия
{
  const w = windowFrame("Студия — Light", 1520, 2000); topBar(w, "Студия"); const b = body(w);
  const l = panel("Scenes", 230, {r: 1}); add(b, l, {v: "FILL"});
  l.appendChild(section("Сцены")); l.appendChild(txt("Сцена 1")); l.appendChild(section("Фон"));
  const bh = al("HORIZONTAL", {name: "Bg", gap: 6}); bh.appendChild(btn("Фото…")); bh.appendChild(btn("Убрать")); l.appendChild(bh);
  l.appendChild(section("На сцене")); l.appendChild(txt("1. mika")); l.appendChild(txt("2. mika")); spacer(l);
  add(l, btn("+ Эта модель", true), {h: "FILL"}); add(l, btn("+ Модель из файла .mu…"), {h: "FILL"}); add(l, btn("Сохранить картинку…"), {h: "FILL"});
  const {paper} = canvas(b, {w: 820, h: 512, paper: "card"});
  paper.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {r: 0.75, g: 0.85, b: 0.95, a: 1}}, {position: 1, color: {r: 0.79, g: 0.71, b: 0.56, a: 1}}]}];
  const r = panel("Poses", 330, {l: 1}); add(b, r, {v: "FILL"});
  r.appendChild(section("Позы и эмоции"));
  const g = al("HORIZONTAL", {name: "Tiles", gap: 10}); g.layoutWrap = "WRAP"; g.counterAxisSpacing = 10; add(r, g, {h: "FILL"});
  for (const n of ["Стоит", "Привет!", "Ура!", "Руки на поясе", "Задумалась", "Указывает", "Улыбка", "Смущение", "Злость"]) {
    const t = al("VERTICAL", {name: "Pose", gap: 4, align: "CENTER"}); const th = figma.createFrame(); th.resize(72, 72); th.cornerRadius = 8; th.fills = [fill("canvas")]; t.appendChild(th); t.appendChild(txt(n, {size: 11})); g.appendChild(t);
  }
  r.appendChild(txt("☐ Плавный переход")); params(r, false);
}

// ---------------------------------------------------------------- Эфир
{
  const w = windowFrame("Эфир — Light", 0, 3000); topBar(w, "Эфир"); const b = body(w);
  canvas(b, {w: 640, h: 640, paper: "chroma", fill: "bg"});
  const r = panel("Live", 290, {l: 1}); add(b, r, {v: "FILL"});
  add(r, btn("Запустить эфир", true), {h: "FILL"}); r.appendChild(section("Движение"));
  for (const t of ["☑ Следить за мышью", "☑ Моргать", "☑ Дышать", "☑ Лёгкое покачивание", "☑ Физика волос и одежды"]) r.appendChild(txt(t));
  r.appendChild(section("Микрофон → рот")); r.appendChild(txt("☐ Липсинк с микрофона")); r.appendChild(txt("Системный по умолчанию", {color: "muted"}));
  r.appendChild(section("Эмоции (клавиши 1–9)")); for (const t of ["0 · Без эмоции", "1 · Улыбка", "2 · Счастье ^^", "3 · Подмигивание"]) r.appendChild(txt(t));
  r.appendChild(section("Кадр и фон")); r.appendChild(txt("По пояс · Хромакей зелёный")); add(r, btn("Открыть окно для OBS"), {h: "FILL"});
}

// ---------------------------------------------------------------- Гайдбук
{
  const w = windowFrame("Гайдбук — Light", 1520, 3000); topBar(w, "Гайдбук"); const b = body(w);
  const l = panel("Chapters", 230, {r: 1}); add(b, l, {v: "FILL"}); l.appendChild(section("Гайдбук"));
  for (const t of ["Добро пожаловать", "Подготовка арта", "Нарезка", "Сетка и деформеры", "Параметры и ключи", "Авто-риг", "Физика", "Студия и позы", "Эфир (стрим)", "Экспорт и форматы", "Горячие клавиши", "Системные требования"]) l.appendChild(txt(t));
  const m = al("VERTICAL", {name: "Text", gap: 12, pad: [24, 32, 24, 32]}); add(b, m, {h: "FILL", v: "FILL"});
  m.appendChild(txt("Мю — оживляем 2D-рисунок", {family: SERIF, size: 28}));
  m.appendChild(txt("Мю делает из обычной иллюстрации живую модель для витубинга, как Live2D Cubism Editor: картинка режется на части, на части натягиваются сетки, деформеры гнут и вращают их, а параметры хранят ключевые формы.", {w: 760}));
  m.appendChild(txt("Путь модели", {family: SERIF, size: 16, color: "accent"}));
  m.appendChild(txt("1. Арт  2. Нарезка  3. Риг  4. Физика  5. Студия и Эфир  6. Экспорт", {w: 760}));
}

return {screens: page.children.length};
