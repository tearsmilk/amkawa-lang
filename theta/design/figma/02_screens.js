// Тета (Theta) — Screens page: Загрузка, Главная (Light / Dark), Игра (панорама + карта в углу: свёрнута / развёрнута),
// Игра — результат раунда, Игра — страны подряд, Итоги, Рекорды, Настройки. Run after 01_ui_kit.js.
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
  const col = cols.find(c => c.name === "Theta — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Theta — " + mode + ")");
  V[mode] = {};
  for (const v of vars) if (v.variableCollectionId === col.id) V[mode][v.name.replace("color/", "")] = v;
}
let MODE = "Light";
const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
const fill = (n, opacity) => { const p = figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][n]); if (opacity !== undefined) p.opacity = opacity; return p; };
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
  f.fills = o.fill ? [fill(o.fill, o.opacity)] : [];
  if (o.pad !== undefined) { const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad, o.pad, o.pad, o.pad]; f.paddingTop = t; f.paddingRight = r; f.paddingBottom = b; f.paddingLeft = l; }
  if (o.radius) f.cornerRadius = o.radius;
  if (o.stroke) { f.strokes = [fill(o.stroke)]; f.strokeWeight = 1; }
  if (o.align) f.counterAxisAlignItems = o.align;
  return f;
}
function fixed(f, w, h) { f.resize(w, h); f.primaryAxisSizingMode = "FIXED"; f.counterAxisSizingMode = "FIXED"; return f; }
function btn(t, accent, o = {}) { const b = al("HORIZONTAL", {name: "Button " + t, pad: [6, 12, 6, 12], radius: 7, fill: accent ? "accent" : "card", stroke: accent ? undefined : "border"}); b.appendChild(txt(t, {style: accent ? "Semi Bold" : "Regular", color: accent ? "on-accent" : "text", ...o})); return b; }
function sidebar(active) {
  const s = al("VERTICAL", {name: "Sidebar", gap: 3, pad: [18, 12, 14, 12], fill: "sidebar"}); fixed(s, 200, 800); s.strokes = [fill("border")]; s.strokeWeight = 1;
  const brand = al("HORIZONTAL", {gap: 8, align: "CENTER"}); brand.appendChild(txt("θ", {family: SERIF, style: SERIF_I, size: 30, color: "accent"})); brand.appendChild(txt("Тета", {family: SERIF, size: 17})); s.appendChild(brand);
  const sp0 = al("HORIZONTAL"); sp0.resize(10, 14); s.appendChild(sp0);
  for (const [t, g] of [["Главная", "⌂"], ["Рекорды", "🏆"], ["Настройки", "⚙"]]) { const b = al("HORIZONTAL", {name: t, gap: 8, pad: [7, 10, 7, 10], radius: 7, fill: t === active ? "selected" : undefined}); b.resize(176, 30); b.primaryAxisSizingMode = "FIXED"; b.appendChild(txt(g, {size: 12})); b.appendChild(txt(t)); s.appendChild(b); }
  const sp = al("VERTICAL"); sp.layoutGrow = 1; s.appendChild(sp);
  s.appendChild(txt("Задание дня: не сыграно", {size: 11, color: "muted"})); s.appendChild(txt("версия 1.0.0", {size: 11, color: "muted"}));
  return s;
}
function shell(name, active, body) {
  const f = al("HORIZONTAL", {name, gap: 0, fill: "bg"}); fixed(f, 1240, 800);
  f.appendChild(sidebar(active)); body.layoutGrow = 1; f.appendChild(body); return f;
}
function pick(labelText, value, w = 320) {
  const row = al("HORIZONTAL", {gap: 10, align: "CENTER"}); row.appendChild(txt(labelText, {color: "white"}));
  const box = al("HORIZONTAL", {pad: [8, 10, 8, 10], radius: 8, fill: "white", opacity: 0.92}); box.resize(w, 34); box.primaryAxisSizingMode = "FIXED";
  box.appendChild(txt(value, {color: "ink"})); const sp = al("HORIZONTAL"); sp.layoutGrow = 1; box.appendChild(sp); box.appendChild(txt("▾", {color: "ink"})); row.appendChild(box); return row;
}
function check(t, on) { const r = al("HORIZONTAL", {gap: 6, align: "CENTER"}); const b = figma.createRectangle(); b.resize(14, 14); b.cornerRadius = 4; b.fills = [fill(on ? "accent" : "white", on ? 1 : 0.15)]; b.strokes = [fill("white", 0.7)]; r.appendChild(b); r.appendChild(txt(t, {color: "white"})); return r; }
function recordRow(n, title, sub, pts) { const r = al("HORIZONTAL", {gap: 12, pad: [10, 14, 10, 14], radius: 14, fill: "card", stroke: "border", align: "CENTER"}); r.resize(960, 56); r.primaryAxisSizingMode = "FIXED"; if (n) r.appendChild(txt(n, {family: SERIF, size: 16})); const c = al("VERTICAL", {gap: 2}); c.layoutGrow = 1; c.appendChild(txt(title, {family: SERIF, size: 16})); c.appendChild(txt(sub, {size: 11, color: "muted"})); r.appendChild(c); r.appendChild(txt(pts, {family: SERIF, size: 16})); return r; }

// ---- Главная
function homeBody(dark) {
  const b = al("VERTICAL", {name: "Page", gap: 14, pad: [26, 32, 26, 32], fill: "bg"});
  b.appendChild(txt("Добрый вечер, Hoka", {family: SERIF, size: 28}));
  const hero = al("HORIZONTAL", {name: "Hero", pad: [22, 26, 22, 26], gap: 20, radius: 18, fill: "hero-b"}); hero.resize(976, 250); hero.primaryAxisSizingMode = "FIXED"; hero.counterAxisAlignItems = "MIN";
  const hl = al("VERTICAL", {gap: 10}); hl.layoutGrow = 1; hl.appendChild(txt("Новая игра", {family: SERIF, size: 34, color: "white"})); hl.appendChild(txt("Мир · 5 раундов · до 25 000 очков", {color: "white"}));
  hl.appendChild(pick("Карта", "Мир")); hl.appendChild(pick("Режим", "Классика")); hl.appendChild(pick("Источник", "Google Street View — интерактивные панорамы")); hl.appendChild(pick("Время на раунд", "Без ограничения"));
  const o = al("HORIZONTAL", {gap: 14}); o.appendChild(check("Без движения", false)); o.appendChild(check("Без поворота", false)); o.appendChild(check("Без зума", false)); hl.appendChild(o); hero.appendChild(hl);
  const hr = al("VERTICAL", {gap: 8}); const play = al("HORIZONTAL", {pad: [10, 30, 10, 30], radius: 10, fill: "accent"}); play.appendChild(txt("▶  Играть", {size: 16, style: "Semi Bold", color: "on-accent"})); hr.appendChild(play); hero.appendChild(hr); b.appendChild(hero);
  b.appendChild(txt("ЗАДАНИЕ ДНЯ", {size: 10, style: "Semi Bold", color: "muted"}));
  const d = al("HORIZONTAL", {pad: [10, 12, 10, 12], gap: 12, radius: 12, fill: "card", stroke: "border", align: "CENTER"}); d.resize(976, 64); d.primaryAxisSizingMode = "FIXED"; d.appendChild(txt("📅", {size: 22})); const dc = al("VERTICAL", {gap: 2}); dc.appendChild(txt("Задание дня", {family: SERIF, size: 16})); dc.appendChild(txt("Ещё не сыграно · 5 раундов, мир", {size: 11, color: "muted"})); d.appendChild(dc); b.appendChild(d);
  b.appendChild(txt("НЕДАВНИЕ ИГРЫ", {size: 10, style: "Semi Bold", color: "muted"}));
  b.appendChild(recordRow("", "Европа · Классика", "Hoka · 24.10.2026 00:12", "21 480 / 25 000")); b.appendChild(recordRow("", "Мир · Страны подряд", "Hoka · 23.10.2026 23:40 · серия 7", "7 подряд"));
  return b;
}
// ---- Игра
function gameScreen(name, variant) {
  const f = al("VERTICAL", {name, gap: 0, fill: "viewer"}); fixed(f, 1240, 800); f.clipsContent = true;
  const sky = figma.createRectangle(); sky.resize(1240, 800); sky.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {...hex("#A8C8FF"), a: 1}}, {position: 0.55, color: {...hex("#C9B48A"), a: 1}}, {position: 1, color: {...hex("#5B4632"), a: 1}}]}]; f.appendChild(sky); sky.layoutPositioning = "ABSOLUTE"; sky.x = 0; sky.y = 0;
  const top = al("HORIZONTAL", {name: "Round bar", pad: [8, 14, 8, 14], gap: 14, radius: 12, fill: "overlay", opacity: 0.62, align: "CENTER"}); top.resize(540, 40); top.primaryAxisSizingMode = "FIXED";
  for (const [t, o] of [[variant === "streak" ? "Серия: 3" : "Раунд 2 / 5", {family: SERIF, size: 16}], ["4 870 очков", {}], ["⏱ 0:42", {}], [variant === "streak" ? "Мир · Страны подряд" : "Европа · Классика", {size: 11}]]) top.appendChild(txt(t, {...o, color: "white"}));
  const sp = al("HORIZONTAL"); sp.layoutGrow = 1; top.appendChild(sp); top.appendChild(txt("✕", {color: "white"})); f.appendChild(top); top.layoutPositioning = "ABSOLUTE"; top.x = 12; top.y = 12;
  const ctrl = al("HORIZONTAL", {name: "Controls", pad: [4, 6, 4, 6], gap: 2, radius: 12, fill: "overlay", opacity: 0.62}); for (const g of ["‹", "◎", "›", "+", "−"]) { const bb = al("HORIZONTAL", {pad: [4, 8, 4, 8]}); bb.appendChild(txt(g, {color: "white", size: 14})); ctrl.appendChild(bb); } f.appendChild(ctrl); ctrl.layoutPositioning = "ABSOLUTE"; ctrl.x = 540; ctrl.y = 744;
  const attr = al("HORIZONTAL", {name: "Attribution", pad: [3, 8, 3, 8], radius: 6, fill: "overlay", opacity: 0.55}); attr.appendChild(txt(variant === "commons" ? "Ivan Petrov · CC BY 4.0 · Wikimedia Commons" : "© Google", {size: 10, color: "white"})); f.appendChild(attr); attr.layoutPositioning = "ABSOLUTE"; attr.x = 12; attr.y = 766;
  const big = variant !== "collapsed";
  const mp = al("VERTICAL", {name: "Map panel", pad: 6, gap: 6, radius: 12, fill: "bg", stroke: "border"}); const [mw, mh] = big ? [340, 240] : [220, 150]; fixed(mp, mw, mh); mp.counterAxisAlignItems = "MIN";
  if (big) { const mt = al("HORIZONTAL", {gap: 4, align: "CENTER"}); mt.appendChild(txt("📌", {size: 12})); const ms = al("HORIZONTAL"); ms.layoutGrow = 1; mt.appendChild(ms); for (const n of ["1", "2", "3", "4"]) { const bb = al("HORIZONTAL", {pad: [2, 7, 2, 7], radius: 6, fill: n === "2" ? "selected" : undefined}); bb.appendChild(txt(n, {size: 11})); mt.appendChild(bb); } mt.appendChild(txt("−  +", {size: 12})); mt.resize(mw - 12, 20); mt.primaryAxisSizingMode = "FIXED"; mp.appendChild(mt); }
  if (variant === "streak") { const cb = al("HORIZONTAL", {pad: [6, 10, 6, 10], radius: 6, fill: "input", stroke: "border"}); cb.resize(mw - 12, 30); cb.primaryAxisSizingMode = "FIXED"; cb.appendChild(txt("Какая это страна?", {color: "faint"})); mp.appendChild(cb); }
  else { const ma = al("HORIZONTAL", {name: "Map", fill: "map-water", radius: 6}); fixed(ma, mw - 12, mh - (big ? 76 : 50)); const pin = figma.createEllipse(); pin.resize(14, 14); pin.fills = [fill("accent")]; pin.strokes = [fill("white")]; pin.strokeWeight = 2; ma.appendChild(pin); ma.paddingLeft = (mw - 12) / 2; ma.paddingTop = (mh - 76) / 2; mp.appendChild(ma); }
  const ans = al("HORIZONTAL", {pad: [6, 12, 6, 12], radius: 7, fill: variant === "collapsed" ? "selected" : "accent"}); ans.resize(mw - 12, 30); ans.primaryAxisSizingMode = "FIXED"; ans.primaryAxisAlignItems = "CENTER"; ans.appendChild(txt("Ответить", {style: "Semi Bold", color: variant === "collapsed" ? "faint" : "on-accent"})); mp.appendChild(ans);
  f.appendChild(mp); mp.layoutPositioning = "ABSOLUTE"; mp.x = 1240 - mw - 12; mp.y = 800 - mh - 12;
  if (variant === "result") {
    const res = al("VERTICAL", {name: "Result", pad: [14, 20, 14, 20], gap: 6, radius: 14, fill: "overlay", opacity: 0.82}); res.resize(520, 110); res.primaryAxisSizingMode = "FIXED"; res.counterAxisAlignItems = "MIN";
    res.appendChild(txt("4 870 очков", {family: SERIF, size: 26, color: "white"})); res.appendChild(txt("312 м от места · Франция · 41 с", {color: "white"}));
    const rr = al("HORIZONTAL"); const rsp = al("HORIZONTAL"); rsp.layoutGrow = 1; rr.appendChild(rsp); rr.appendChild(btn("Следующий раунд", true)); rr.resize(480, 30); rr.primaryAxisSizingMode = "FIXED"; res.appendChild(rr);
    f.appendChild(res); res.layoutPositioning = "ABSOLUTE"; res.x = 360; res.y = 610;
  }
  return f;
}
// ---- Итоги
function finalScreen() {
  const b = al("VERTICAL", {name: "Page", gap: 10, pad: [30, 40, 30, 40], fill: "bg"});
  b.appendChild(txt("21 480 из 25 000", {family: SERIF, size: 28})); b.appendChild(txt("Европа · Классика · Hoka", {color: "muted"}));
  for (const [i, d, c, p] of [[1, "312 м", "Франция", "4 870"], [2, "48 км", "Италия", "3 410"], [3, "1,2 км", "Германия", "4 650"], [4, "230 км", "Польша", "3 760"], [5, "4,5 км", "Чехия", "4 790"]]) b.appendChild(recordRow("", "Раунд " + i, d + " · " + c, p));
  const row = al("HORIZONTAL", {gap: 8}); row.appendChild(btn("Играть ещё", true)); row.appendChild(btn("На главную", false)); b.appendChild(row);
  return shell("Итоги", "Главная", b);
}
// ---- Рекорды
function recordsScreen() {
  const b = al("VERTICAL", {name: "Page", gap: 12, pad: [26, 32, 26, 32], fill: "bg"});
  const h = al("HORIZONTAL", {gap: 8, align: "CENTER"}); h.appendChild(txt("Рекорды", {family: SERIF, size: 28})); const sp = al("HORIZONTAL"); sp.layoutGrow = 1; h.appendChild(sp); h.appendChild(btn("Все карты ▾", false)); h.appendChild(btn("Все режимы ▾", false)); h.resize(976, 40); h.primaryAxisSizingMode = "FIXED"; b.appendChild(h);
  for (const [n, t, s, p] of [["1.", "Европа · Классика", "Hoka · 24.10.2026 00:12", "21 480 / 25 000"], ["2.", "Мир · Классика", "Hoka · 23.10.2026 22:05", "17 920 / 25 000"], ["3.", "Мир · Страны подряд", "Hoka · 23.10.2026 23:40 · серия 7", "7 подряд"]]) b.appendChild(recordRow(n, t, s, p));
  return shell("Рекорды", "Рекорды", b);
}
// ---- Настройки
function settingsScreen() {
  const b = al("VERTICAL", {name: "Page", gap: 12, pad: [26, 32, 26, 32], fill: "bg"});
  b.appendChild(txt("Настройки", {family: SERIF, size: 28}));
  b.appendChild(txt("ИГРОК", {size: 10, style: "Semi Bold", color: "muted"})); const nick = al("HORIZONTAL", {pad: [5, 8, 5, 8], radius: 6, fill: "input", stroke: "border"}); nick.resize(320, 28); nick.primaryAxisSizingMode = "FIXED"; nick.appendChild(txt("Hoka")); b.appendChild(nick);
  b.appendChild(txt("ИСТОЧНИКИ", {size: 10, style: "Semi Bold", color: "muted"}));
  const box = al("VERTICAL", {gap: 8, pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border"}); box.resize(976, 10); box.primaryAxisSizingMode = "AUTO"; box.counterAxisSizingMode = "FIXED";
  for (const [title, ph, hint] of [["Google Street View — ключ Maps Platform", "••••••••••••••••", "Включите Maps JavaScript API и Street View Static API. Поиск точек бесплатный, показ панорамы ≈ $14 за 1000 раундов — кредита $200/мес хватает на ~14 000 раундов."], ["Mapillary — client token", "MLY|…", "Бесплатно: mapillary.com → Developers → Register application → Client token."]]) {
    box.appendChild(txt(title, {family: SERIF, size: 16})); const r = al("HORIZONTAL", {gap: 8, align: "CENTER"}); const e = al("HORIZONTAL", {pad: [5, 8, 5, 8], radius: 6, fill: "input", stroke: "border"}); e.resize(900, 28); e.primaryAxisSizingMode = "FIXED"; e.appendChild(txt(ph, {color: "faint"})); r.appendChild(e); r.appendChild(txt("👁", {size: 12})); box.appendChild(r); box.appendChild(txt(hint, {size: 11, color: "muted", w: 940}));
  }
  box.appendChild(txt("☑ Только официальные панорамы Google (без пользовательских)"));
  b.appendChild(box);
  b.appendChild(txt("КЕШ", {size: 10, style: "Semi Bold", color: "muted"})); const cr = al("HORIZONTAL", {gap: 8, align: "CENTER"}); cr.appendChild(txt("Лимит кеша картинок, МБ")); cr.appendChild(btn("500", false)); cr.appendChild(txt("сейчас 128 МБ", {size: 11, color: "muted"})); cr.appendChild(btn("Очистить кеш", false)); b.appendChild(cr);
  b.appendChild(txt("ОФОРМЛЕНИЕ", {size: 10, style: "Semi Bold", color: "muted"})); const tr = al("HORIZONTAL", {gap: 8, align: "CENTER"}); tr.appendChild(txt("Тема")); tr.appendChild(btn("Как в системе ▾", false)); tr.appendChild(txt("Акцент")); for (const [i, c] of ["#D97757", "#3B82C4", "#4E8A5A", "#8E6BC4", "#D06A8F", "#D9A23A", "#3FA7C4", "#5E5D59", "#C8463C", "#3FB08A"].entries()) { const e = figma.createEllipse(); e.resize(24, 24); e.fills = [{type: "SOLID", color: hex(c)}]; if (!i) { e.strokes = [fill("text")]; e.strokeWeight = 2; } tr.appendChild(e); } b.appendChild(tr);
  b.appendChild(txt("☑ Заголовки с засечками"));
  return shell("Настройки", "Настройки", b);
}
// ---- Загрузка
function splash() {
  const f = al("VERTICAL", {name: "Загрузка", gap: 6, fill: "bg"}); fixed(f, 1240, 800); f.primaryAxisAlignItems = "CENTER"; f.counterAxisAlignItems = "CENTER";
  f.appendChild(txt("θ", {family: SERIF, style: SERIF_I, size: 120, color: "accent"})); f.appendChild(txt("Тета", {family: SERIF, size: 30})); f.appendChild(txt("Угадай, где ты", {color: "muted"}));
  const bar = figma.createRectangle(); bar.resize(320, 6); bar.cornerRadius = 3; bar.fills = [fill("border")]; f.appendChild(bar); f.appendChild(txt("Читаем страны…", {size: 11, color: "muted"}));
  return f;
}

const frames = [splash(), shell("Главная — Light", "Главная", homeBody(false))];
MODE = "Dark"; frames.push(shell("Главная — Dark", "Главная", homeBody(true))); MODE = "Light";
frames.push(gameScreen("Игра — карта свёрнута", "collapsed"), gameScreen("Игра — карта развёрнута", "expanded"), gameScreen("Игра — результат раунда", "result"),
            gameScreen("Игра — страны подряд", "streak"), gameScreen("Игра — фото Commons", "commons"), finalScreen(), recordsScreen(), settingsScreen());
let x = 0, y = 0;
for (const [i, fr] of frames.entries()) { fr.x = x; fr.y = y; x += fr.width + 80; if ((i + 1) % 3 === 0) { x = 0; y += 880; } }
await Promise.all(frames.map(fr => fr.screenshot({scale: 0.25})));
return {frames: frames.length};
