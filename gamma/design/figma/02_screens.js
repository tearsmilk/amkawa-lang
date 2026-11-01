// Гамма (Gamma) — Screens page: Главная (Light / Dark), Настройки, Горячие клавиши, выделение области, запись идёт.
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
  const col = cols.find(c => c.name === "Gamma — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Gamma — " + mode + ")");
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

function frame(name, w, h, fillName = "bg") {
  const f = figma.createFrame(); f.name = name; f.resize(w, h); f.fills = [fill(fillName)]; f.clipsContent = true; return f;
}
function btn(t, kind = "default") {
  const b = al("HORIZONTAL", {name: "Button " + t, pad: [5, 12, 5, 12], radius: 7, fill: kind === "accent" ? "accent" : kind === "rec" ? "rec" : "card", stroke: kind === "default" ? "border" : null});
  b.appendChild(txt(t, {style: kind === "default" ? "Regular" : "Semi Bold", color: kind === "default" ? "text" : "on-accent"})); return b;
}
function kbd(t) { const k = al("HORIZONTAL", {name: "Kbd", pad: [1, 6, 1, 6], radius: 5, fill: "panel", stroke: "border"}); k.appendChild(txt(t, {size: 11, color: "muted"})); return k; }
function sidebar(active) {
  const s = al("VERTICAL", {name: "Sidebar", gap: 4, pad: [18, 12, 14, 12], fill: "sidebar"}); s.resize(200, 720); s.primaryAxisSizingMode = "FIXED"; s.counterAxisSizingMode = "FIXED";
  s.strokes = [fill("border")]; s.strokeRightWeight = 1; s.strokeLeftWeight = 0; s.strokeTopWeight = 0; s.strokeBottomWeight = 0;
  const brand = al("HORIZONTAL", {name: "Brand", gap: 6, align: "CENTER"}); brand.appendChild(txt("γ", {family: SERIF, style: SERIF_I, size: 30, color: "accent"})); brand.appendChild(txt("Гамма", {family: SERIF, size: 17})); s.appendChild(brand);
  const sp = figma.createFrame(); sp.resize(10, 14); sp.fills = []; s.appendChild(sp);
  for (const [i, t] of ["Главная", "Настройки", "Горячие клавиши"].entries()) {
    const b = al("HORIZONTAL", {name: t, pad: [7, 10, 7, 10], radius: 7, fill: i === active ? "selected" : null}); b.resize(176, 30); b.primaryAxisSizingMode = "FIXED";
    b.appendChild(txt(["⌂", "⚙", "⌨"][i] + "  " + t)); s.appendChild(b);
  }
  return s;
}
function shell(name, active) {
  const f = frame(name, 1100, 720); f.layoutMode = "HORIZONTAL"; f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED";
  f.appendChild(sidebar(active));
  const body = al("VERTICAL", {name: "Page", gap: 14, pad: [28, 36, 24, 36]}); body.layoutGrow = 1; body.layoutAlign = "STRETCH"; f.appendChild(body);
  return [f, body];
}

let X = 0;
function place(f) { f.x = X; f.y = 0; X += f.width + 80; page.appendChild(f); }

// Главная (Light, Dark)
for (const mode of ["Light", "Dark"]) {
  MODE = mode;
  const [f, b] = shell("Главная — " + mode, 0);
  b.appendChild(txt("Что запишем?", {family: SERIF, size: 28}));
  b.appendChild(txt("Снимки и видео экрана — целиком или выделенной области. Всё сохраняется в папки из настроек, горячие клавиши работают из любой программы.", {color: "muted", w: 820}));
  const row = al("HORIZONTAL", {name: "Actions", gap: 12});
  for (const [g, c, t, k, d] of [["▣", "accent", "Снимок области", "⇧⌘2", "Выделите мышкой — сохранится и скопируется"], ["▭", "text", "Снимок экрана", "⇧⌘1", "Весь экран под курсором одним нажатием"],
                               ["●", "rec", "Запись области", "⇧⌘8", "Выделите место на экране — запишется только оно"], ["◉", "rec", "Запись экрана", "⇧⌘9", "Весь экран; повторное нажатие — стоп"]]) {
    const card = al("VERTICAL", {name: t, gap: 6, pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border"}); card.resize(198, 132); card.primaryAxisSizingMode = "FIXED"; card.counterAxisSizingMode = "FIXED";
    const top = al("HORIZONTAL", {name: "Top", align: "CENTER"}); top.resize(166, 30); top.primaryAxisSizingMode = "FIXED"; top.primaryAxisAlignItems = "SPACE_BETWEEN";
    top.appendChild(txt(g, {size: 24, color: c})); top.appendChild(kbd(k)); card.appendChild(top);
    card.appendChild(txt(t, {family: SERIF, size: 16})); card.appendChild(txt(d, {size: 11, color: "muted", w: 166})); row.appendChild(card);
  }
  b.appendChild(row);
  const au = al("HORIZONTAL", {name: "Sound", gap: 0, align: "CENTER"});
  au.appendChild(txt("ЗВУК ПРИ ЗАПИСИ    ", {size: 10, style: "Semi Bold", color: "muted"}));
  for (const [i, t] of ["Без звука", "Микрофон", "Звук системы", "Микрофон + система"].entries()) {
    const s = al("HORIZONTAL", {name: t, pad: [5, 12, 5, 12], fill: i === 1 ? "selected" : "card", stroke: i === 1 ? "accent" : "border"});
    s.topLeftRadius = s.bottomLeftRadius = i === 0 ? 7 : 0; s.topRightRadius = s.bottomRightRadius = i === 3 ? 7 : 0; s.appendChild(txt(t)); au.appendChild(s);
  }
  au.appendChild(txt("    микрофон по умолчанию", {size: 11, color: "muted"}));
  b.appendChild(au);
  const rb = al("HORIZONTAL", {name: "Replay", gap: 14, pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "accent"}); rb.resize(828, 90); rb.primaryAxisSizingMode = "FIXED";
  rb.appendChild(txt("↺", {size: 28, color: "accent"}));
  const rc = al("VERTICAL", {name: "Text", gap: 4}); rc.layoutGrow = 1;
  const rh = al("HORIZONTAL", {name: "Head", gap: 8, align: "CENTER"}); rh.appendChild(txt("Откат", {family: SERIF, size: 18}));
  const badge = al("HORIZONTAL", {name: "Badge", pad: [1, 8, 1, 8], radius: 8, fill: "accent"}); badge.appendChild(txt("● идёт", {size: 11, color: "on-accent"})); rh.appendChild(badge); rc.appendChild(rh);
  rc.appendChild(txt("Гамма постоянно помнит последние 05:00 экрана. Нажмите ⇧⌘0 — и получите видео: 05:00 до нажатия + 01:00 после (итого 06:00).", {color: "muted", w: 560}));
  rc.appendChild(txt("В буфере 03:12 из 05:00", {size: 11, color: "muted"})); rb.appendChild(rc);
  const rbt = al("VERTICAL", {name: "Buttons", gap: 6}); rbt.appendChild(btn("Выключить")); rbt.appendChild(btn("Сохранить откат", "accent")); rb.appendChild(rbt);
  b.appendChild(rb);
  const rh2 = al("HORIZONTAL", {name: "Recent header", align: "CENTER"}); rh2.resize(828, 30); rh2.primaryAxisSizingMode = "FIXED"; rh2.primaryAxisAlignItems = "SPACE_BETWEEN";
  rh2.appendChild(txt("Недавние", {family: SERIF, size: 18})); rh2.appendChild(txt("Папка снимков    Папка видео", {color: "accent"})); b.appendChild(rh2);
  const rec = al("HORIZONTAL", {name: "Recent", gap: 20});
  for (const [n, v] of [["Откат 2026-10-17 в 15.10.00", true], ["Запись 2026-10-17 в 15.00.00", true], ["Снимок 2026-10-17 в 14.02.00", false], ["Снимок 2026-10-17 в 14.01.00", false]]) {
    const it = al("VERTICAL", {name: n, gap: 6, align: "CENTER"});
    const th = figma.createRectangle(); th.resize(176, 110); th.cornerRadius = 6; th.fills = [fill(v ? "desk-a" : "desk-b")]; it.appendChild(th);
    it.appendChild(txt(n, {size: 12})); rec.appendChild(it);
  }
  b.appendChild(rec);
  place(f);
}
MODE = "Light";

// Настройки
{
  const [f, b] = shell("Настройки", 1);
  b.itemSpacing = 10;
  b.appendChild(txt("Настройки", {family: SERIF, size: 28}));
  const sec = t => b.appendChild(txt(t, {size: 10, style: "Semi Bold", color: "muted"}));
  const row = (t, v, extra) => {
    const r = al("HORIZONTAL", {name: t, gap: 10, align: "CENTER"}); r.resize(828, 28); r.primaryAxisSizingMode = "FIXED";
    const l = txt(t); l.resize(210, l.height); l.textAutoResize = "HEIGHT"; r.appendChild(l);
    const fld = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: extra ? null : "input", stroke: extra ? null : "border"}); fld.layoutGrow = 1; fld.appendChild(txt(v, {color: extra ? "muted" : "text"})); r.appendChild(fld);
    if (extra) { r.appendChild(btn("Выбрать…")); r.appendChild(btn("📁")); }
    b.appendChild(r);
  };
  const chk = t => { const r = al("HORIZONTAL", {name: t, gap: 6, align: "CENTER"}); const c = figma.createRectangle(); c.resize(14, 14); c.cornerRadius = 4; c.fills = [fill("accent")]; r.appendChild(c); r.appendChild(txt(t)); b.appendChild(r); };
  sec("СОХРАНЕНИЕ"); row("Видео", "~/Movies/Гамма", true); row("Снимки", "~/Pictures/Гамма", true); row("Формат видео", "MP4 (H.264)"); row("Формат снимков", "PNG — без потерь");
  sec("ВИДЕО"); row("Кадров в секунду", "30"); row("Качество", "Высокое"); row("Кодировщик", "Аппаратный (VideoToolbox) — меньше нагрузка"); row("Размер", "Как на экране (Retina — в полном разрешении)"); row("Обратный отсчёт", "3 секунды");
  chk("Показывать курсор"); chk("Убирать окно Гаммы во время записи"); chk("Не показывать окна Гаммы на снимках и записях (рамка, панель, уведомления)");
  sec("ЗВУК"); row("Микрофон", "По умолчанию (как в системе)"); row("Звук системы", "Найти автоматически (BlackHole, Loopback…)");
  sec("ОТКАТ"); row("Помнить до нажатия, мин", "5,0"); row("Дописать после нажатия, мин", "1,0");
  place(f);
}

// Горячие клавиши
{
  const [f, b] = shell("Горячие клавиши", 2);
  b.appendChild(txt("Горячие клавиши", {family: SERIF, size: 28}));
  b.appendChild(txt("Работают из любой программы, даже когда Гамма свёрнута. Нажмите на поле и затем сочетание; ⌫ — очистить, Esc — отмена. Системные ⇧⌘3 / ⇧⌘4 / ⇧⌘5 заняты macOS.", {color: "muted", w: 820}));
  for (const [t, k] of [["Снимок области", "⇧⌘2"], ["Снимок экрана", "⇧⌘1"], ["Запись области (повтор — стоп)", "⇧⌘8"], ["Запись экрана (повтор — стоп)", "⇧⌘9"],
                        ["Сохранить откат", "⇧⌘0"], ["Включить / выключить откат", "⇧⌘-"], ["Показать Гамму", "Не задано"]]) {
    const r = al("HORIZONTAL", {name: t, gap: 14, align: "CENTER"});
    const l = txt(t); l.resize(220, l.height); l.textAutoResize = "HEIGHT"; r.appendChild(l);
    const h = al("HORIZONTAL", {name: "Hotkey", pad: [3, 8, 3, 8], radius: 6, fill: "input", stroke: k === "⇧⌘8" ? "accent" : "border"}); h.resize(130, 26); h.primaryAxisSizingMode = "FIXED"; h.primaryAxisAlignItems = "CENTER";
    h.appendChild(txt(k === "⇧⌘8" ? "Нажмите сочетание…" : k)); r.appendChild(h); r.appendChild(btn("✕")); b.appendChild(r);
  }
  b.appendChild(btn("Вернуть по умолчанию"));
  place(f);
}

// Выделение области для записи (поверх экрана)
{
  const f = frame("Выделение области — запись", 1100, 720, "desk-a");
  const g = figma.createRectangle(); g.resize(1100, 720); g.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [{position: 0, color: {...hex("#3B4A6B"), a: 1}}, {position: 1, color: {...hex("#D97757"), a: 1}}]}]; f.appendChild(g);
  const win = figma.createRectangle(); win.resize(520, 360); win.x = 110; win.y = 90; win.cornerRadius = 10; win.fills = [fill("ivory")]; f.appendChild(win);
  const dim = figma.createRectangle(); dim.resize(1100, 720); dim.fills = [{type: "SOLID", color: hex("#141413"), opacity: 0.45}]; f.appendChild(dim);
  const sel = figma.createRectangle(); sel.resize(500, 300); sel.x = 260; sel.y = 160; sel.fills = [fill("ivory")]; sel.opacity = 0.96; sel.strokes = [fill("rec")]; sel.dashPattern = [6, 4]; sel.strokeWeight = 1.5; f.appendChild(sel);
  for (const [x, y] of [[260, 160], [510, 160], [760, 160], [760, 310], [760, 460], [510, 460], [260, 460], [260, 310]]) {
    const h = figma.createEllipse(); h.resize(9, 9); h.x = x - 4.5; h.y = y - 4.5; h.fills = [fill("ivory")]; h.strokes = [fill("rec")]; h.strokeWeight = 1.5; f.appendChild(h);
  }
  const pill = al("HORIZONTAL", {name: "Size", pad: [4, 10, 4, 10], radius: 12, fill: "dim"}); pill.appendChild(txt("1000 × 600", {size: 12, color: "ivory"})); f.appendChild(pill); pill.x = 470; pill.y = 128;
  const bar = al("HORIZONTAL", {name: "Toolbar", pad: [5, 6, 5, 6], radius: 12, fill: "ivory", stroke: "border", gap: 2, align: "CENTER"});
  bar.appendChild(txt("Звук:", {size: 11, color: "muted"}));
  for (const [t, on] of [["Без звука", false], ["Микрофон", true], ["Система", false], ["Оба", false]]) { const bb = al("HORIZONTAL", {name: t, pad: [5, 9, 5, 9], radius: 7, fill: on ? "selected" : null}); bb.appendChild(txt(t, {color: "ink"})); bar.appendChild(bb); }
  const c = al("HORIZONTAL", {name: "Cancel", pad: [5, 9, 5, 9], radius: 7}); c.appendChild(txt("Отмена", {color: "ink"})); bar.appendChild(c); bar.appendChild(btn("●  Начать запись", "rec"));
  f.appendChild(bar); bar.x = 300; bar.y = 474;
  place(f);
}

// Запись идёт: рамка + панель + значок в строке меню
{
  const f = frame("Запись идёт", 1100, 720, "desk-a");
  const g = figma.createRectangle(); g.resize(1100, 720); g.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [{position: 0, color: {...hex("#3B4A6B"), a: 1}}, {position: 1, color: {...hex("#D97757"), a: 1}}]}]; f.appendChild(g);
  const menu = figma.createRectangle(); menu.resize(1100, 26); menu.fills = [{type: "SOLID", color: hex("#FAF9F5"), opacity: 0.85}]; f.appendChild(menu);
  const tray = txt("γ●  01:23", {size: 13, color: "ink"}); f.appendChild(tray); tray.x = 960; tray.y = 5;
  const win = figma.createRectangle(); win.resize(520, 360); win.x = 110; win.y = 90; win.cornerRadius = 10; win.fills = [fill("ivory")]; f.appendChild(win);
  const fr = figma.createRectangle(); fr.resize(508, 308); fr.x = 256; fr.y = 156; fr.cornerRadius = 3; fr.fills = []; fr.strokes = [fill("rec")]; fr.strokeWeight = 2; fr.dashPattern = [6, 4]; f.appendChild(fr);
  const bar = al("HORIZONTAL", {name: "Record bar", pad: [7, 8, 7, 12], radius: 14, fill: "ivory", stroke: "border", gap: 8, align: "CENTER"});
  const dot = figma.createEllipse(); dot.resize(10, 10); dot.fills = [fill("rec")]; bar.appendChild(dot);
  bar.appendChild(txt("01:23", {family: SERIF, size: 17, color: "ink"})); bar.appendChild(txt("Запись области · микрофон", {size: 11, color: "muted"}));
  bar.appendChild(btn("Стоп", "rec")); bar.appendChild(txt("🗑", {size: 13}));
  f.appendChild(bar); bar.x = 380; bar.y = 476;
  const toast = al("HORIZONTAL", {name: "Toast — откат", pad: 10, radius: 14, fill: "ivory", stroke: "border", gap: 10});
  const th = figma.createRectangle(); th.resize(96, 64); th.cornerRadius = 8; th.fills = [fill("desk-a")]; toast.appendChild(th);
  const tc = al("VERTICAL", {name: "Text", gap: 3}); tc.appendChild(txt("Сохраняю откат…", {family: SERIF, size: 15, color: "ink"}));
  tc.appendChild(txt("Последние 05:00 уже в буфере, дописываю ещё 00:42. Итого ≈ 06:00.", {size: 11, color: "muted", w: 210})); toast.appendChild(tc);
  f.appendChild(toast); toast.x = 740; toast.y = 600;
  place(f);
}
return {screens: page.children.length};
