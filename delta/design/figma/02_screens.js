// Дельта (Delta) — Screens page: Main (Light/Dark), New document, Adjustment, Export, Welcome. Run after 01_ui_kit.js.
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
  const col = cols.find(c => c.name === "Delta — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Delta — " + mode + ")");
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
function contextBar(tool, opts) {
  const b = al("HORIZONTAL", {name: "Context bar", gap: 12, pad: [8, 14, 8, 14], align: "CENTER"}); border(b, {b: 1});
  b.appendChild(txt(tool, {family: SERIF, size: 17}));
  for (const [l, v] of opts) { if (l) b.appendChild(txt(l, {color: "muted"})); const f = al("HORIZONTAL", {name: "Field", pad: [3, 8, 3, 8], radius: 6, fill: "input", stroke: "border"}); f.appendChild(txt(v)); b.appendChild(f); }
  spacer(b); b.appendChild(txt("ПКМ — второй цвет · ⇧ — прямая · Alt — пипетка · [ ] — размер", {size: 12, color: "muted"}));
  return b;
}
function toolbox() {
  const t = al("VERTICAL", {name: "Tools", gap: 4, pad: [10, 8, 10, 8], fill: "panel", align: "CENTER"}); border(t, {r: 1});
  t.resize(84, 10); t.counterAxisSizingMode = "FIXED";
  t.appendChild(txt("δ", {family: SERIF, style: SERIF_I, size: 26, color: "accent"}));
  const g = ["🖌", "⌫", "▧", "▤", "⦿", "╱", "▭", "◯", "⬚", "⬭", "➰", "✧", "✥", "⤢", "▦", "💬", "A", "░", "✋", "⌕", "↻"];
  for (let i = 0; i < g.length; i += 2) {
    const r = al("HORIZONTAL", {name: "Row", gap: 4});
    for (const k of g.slice(i, i + 2)) { const b = al("HORIZONTAL", {name: "Tool", pad: [5, 9, 5, 9], radius: 7, fill: k === "🖌" ? "selected" : null, stroke: k === "🖌" ? "accent" : null}); b.appendChild(txt(k, {size: 14})); r.appendChild(b); }
    t.appendChild(r);
  }
  return t;
}
function mangaPage(scale) {
  const pg = figma.createFrame(); pg.name = "Manga page"; pg.resize(1240 * scale, 1754 * scale); pg.fills = [fill("paper")];
  pg.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 4}, radius: 12, spread: 0, visible: true, blendMode: "NORMAL"}];
  const panels = [[60, 60, 1120, 760], [60, 850, 540, 840], [640, 850, 540, 840]];
  for (const [x, y, w, h] of panels) { const r = figma.createRectangle(); r.x = x * scale; r.y = y * scale; r.resize(w * scale, h * scale); r.fills = []; r.strokes = [fill("ink")]; r.strokeWeight = 3; pg.appendChild(r); }
  const face = figma.createEllipse(); face.resize(420 * scale, 460 * scale); face.x = 410 * scale; face.y = 240 * scale; face.fills = [fill("skin")]; face.strokes = [fill("ink")]; face.strokeWeight = 2; pg.appendChild(face);
  for (let k = 0; k < 9; k++) { const h = figma.createVector(); const x0 = (390 + k * 55) * scale; h.vectorPaths = [{windingRule: "NONE", data: `M ${x0} ${240 * scale} Q ${x0 + 40 * scale} ${400 * scale} ${x0 + 160 * scale} ${600 * scale}`}]; h.strokes = [fill("ink")]; h.strokeWeight = 2; h.fills = []; pg.appendChild(h); }
  const tone = figma.createRectangle(); tone.x = 62 * scale; tone.y = 852 * scale; tone.resize(536 * scale, 836 * scale);
  tone.fills = [{type: "SOLID", color: {r: 0.08, g: 0.08, b: 0.08}, opacity: 0.18}]; tone.name = "Screentone (dots)"; pg.appendChild(tone);
  const bub = figma.createEllipse(); bub.resize(300 * scale, 170 * scale); bub.x = 760 * scale; bub.y = 960 * scale; bub.fills = [fill("paper")]; bub.strokes = [fill("ink")]; bub.strokeWeight = 2; pg.appendChild(bub);
  const bt = txt("Привет!", {size: 13, color: "ink"}); bt.x = 870 * scale; bt.y = 1030 * scale; pg.appendChild(bt);
  return pg;
}
function rightDocks() {
  const p = al("VERTICAL", {name: "Docks", gap: 0, fill: "panel"}); border(p, {l: 1}); p.resize(290, 10); p.counterAxisSizingMode = "FIXED";
  const sec = (title) => { const h = al("HORIZONTAL", {name: title, pad: [6, 10, 6, 10]}); border(h, {b: 1}); h.appendChild(section(title)); add(p, h, {h: "FILL"}); };
  sec("Цвет");
  const c = al("VERTICAL", {name: "Colour", gap: 6, pad: 10}); add(p, c, {h: "FILL"});
  const sv = figma.createRectangle(); sv.resize(268, 130); sv.cornerRadius = 4;
  sv.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [{position: 0, color: {r: 1, g: 1, b: 1, a: 1}}, {position: 1, color: {r: 0.85, g: 0.47, b: 0.34, a: 1}}]},
              {type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {r: 0, g: 0, b: 0, a: 0}}, {position: 1, color: {r: 0, g: 0, b: 0, a: 1}}]}];
  c.appendChild(sv);
  sec("Кисти");
  const b = al("VERTICAL", {name: "Brushes", gap: 2, pad: 8}); add(p, b, {h: "FILL"});
  for (const [n, sel] of [["✏  Карандаш", false], ["✒  G-перо (тушь)", true], ["🖌  Кисть-ручка", false], ["▮  Маркер", false], ["☁  Аэрограф", false], ["💧  Акварель", false]]) {
    const r = al("HORIZONTAL", {name: n, pad: [4, 8, 4, 8], radius: 6, fill: sel ? "selected" : null}); r.appendChild(txt(n)); add(b, r, {h: "FILL"});
  }
  for (const [l, v] of [["Размер", "7 px"], ["Сглаживание", "55%"], ["Нажим → размер", "✓"]]) { const r = al("HORIZONTAL", {name: l, gap: 8}); r.appendChild(txt(l, {color: "muted", w: 120})); r.appendChild(txt(v)); b.appendChild(r); }
  sec("Слои");
  const l = al("VERTICAL", {name: "Layers", gap: 2, pad: 8}); add(p, l, {h: "FILL", v: "FILL"});
  for (const [n, sel] of [["Реплика", false], ["Линии", true], ["Цвет кожи", false], ["Тон", false], ["Кадры", false], ["Набросок", false]]) {
    const r = al("HORIZONTAL", {name: n, gap: 8, pad: [4, 8, 4, 8], radius: 6, fill: sel ? "selected" : null}); add(l, r, {h: "FILL"});
    r.appendChild(txt("👁")); const th = figma.createRectangle(); th.resize(36, 26); th.fills = [fill("paper")]; th.strokes = [fill("border")]; th.strokeWeight = 1; r.appendChild(th);
    const col = al("VERTICAL", {name: "t", gap: 0}); r.appendChild(col); col.appendChild(txt(n)); col.appendChild(txt("Обычный · 100%", {size: 11, color: "muted"}));
  }
  return p;
}
function timeline() {
  const t = al("VERTICAL", {name: "Animation", gap: 0, fill: "panel"}); border(t, {t: 1});
  const h = al("HORIZONTAL", {name: "Title", pad: [6, 10, 6, 10]}); border(h, {b: 1}); h.appendChild(section("Анимация")); add(t, h, {h: "FILL"});
  const bar = al("HORIZONTAL", {name: "Controls", gap: 12, pad: [6, 10, 6, 10], align: "CENTER"}); add(t, bar, {h: "FILL"});
  for (const s of ["⏮", "◀", "▶", "▶▶", "⏭", "☑ Повтор", "◆ Ключ", "Удалить ключи"]) bar.appendChild(txt(s, {color: s === "▶" ? "accent" : "text"}));
  spacer(bar); bar.appendChild(txt("кадр 12 из 47 · 0:00.50", {color: "muted"})); bar.appendChild(txt("24 к/с · 48 к.", {color: "muted"}));
  for (const [name, val, keysAt] of [["▾ Линии", "", [0, 24]], ["◆ Позиция X", "20.0", [0, 24]], ["◇ Позиция Y", "0.0", []], ["◆ Масштаб", "102.6 %", [0, 36]], ["◆ Поворот", "6.0°", [24]]]) {
    const r = al("HORIZONTAL", {name, gap: 0}); add(t, r, {h: "FILL"}); border(r, {b: 1});
    const lab = al("HORIZONTAL", {name: "Label", pad: [3, 8, 3, 16]}); lab.resize(230, 22); lab.primaryAxisSizingMode = "FIXED"; lab.counterAxisSizingMode = "FIXED";
    lab.appendChild(txt(name, {color: name.startsWith("▾") ? "text" : "muted", w: 150})); lab.appendChild(txt(val, {color: "accent"})); r.appendChild(lab);
    const track = figma.createFrame(); track.name = "Track"; track.fills = name.startsWith("▾") ? [fill("selected")] : []; track.resize(900, 22); r.appendChild(track);
    for (const k of keysAt) { const d = figma.createRectangle(); d.resize(8, 8); d.rotation = 45; d.x = 10 + k * 18; d.y = 5; d.fills = [fill("key")]; track.appendChild(d); }
    const ph = figma.createRectangle(); ph.resize(2, 22); ph.x = 10 + 12 * 18; ph.fills = [fill("accent")]; track.appendChild(ph);
  }
  return t;
}
function mainScreen(name, x, y) {
  const win = windowFrame(name, x, y);
  add(win, contextBar("Кисть", [["Размер", "7 px"], ["", "✒ G-перо (тушь)"]]), {h: "FILL"});
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  add(body, toolbox(), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0}); add(body, center, {h: "FILL", v: "FILL"});
  const tabs = al("HORIZONTAL", {name: "Tabs", pad: [6, 12, 0, 12]}); add(center, tabs, {h: "FILL"});
  const tab = al("HORIZONTAL", {name: "Tab", pad: [0, 4, 6, 4], gap: 8}); tab.strokes = [fill("accent")]; tab.strokeTopWeight = 0; tab.strokeLeftWeight = 0; tab.strokeRightWeight = 0; tab.strokeBottomWeight = 2;
  tab.appendChild(txt("глава-1")); tab.appendChild(txt("×", {color: "muted"})); tabs.appendChild(tab);
  const canvas = al("HORIZONTAL", {name: "Canvas", fill: "canvas"}); add(center, canvas, {h: "FILL", v: "FILL"});
  canvas.primaryAxisAlignItems = "CENTER"; canvas.counterAxisAlignItems = "CENTER"; canvas.appendChild(mangaPage(0.3));
  add(center, timeline(), {h: "FILL"});
  add(body, rightDocks(), {v: "FILL"});
  const sb = al("HORIZONTAL", {name: "Status bar", gap: 14, pad: [4, 12, 4, 12], fill: "panel"}); border(sb, {t: 1}); add(win, sb, {h: "FILL"});
  sb.appendChild(txt("x 620  y 470", {size: 11, color: "muted"})); spacer(sb); sb.appendChild(txt("31% · 1240×1754 px · 150 dpi · 6 сл.", {size: 11, color: "muted"}));
  return win;
}
function dialog(name, x, y, title, rows, button) {
  const d = al("VERTICAL", {name: name + " — " + MODE, gap: 10, pad: [22, 26, 20, 26], radius: 12, fill: "bg", stroke: "border"});
  d.resize(460, 10); d.counterAxisSizingMode = "FIXED"; d.x = x; d.y = y;
  d.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.15}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  d.appendChild(txt(title, {family: SERIF, size: 28}));
  for (const [k, v] of rows) {
    const r = al("HORIZONTAL", {name: k, gap: 12, align: "CENTER"}); add(d, r, {h: "FILL"});
    r.appendChild(txt(k, {w: 150}));
    const f = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); f.appendChild(txt(v)); add(r, f, {h: "FILL"});
  }
  const bb = al("HORIZONTAL", {name: "Buttons", gap: 8}); add(d, bb, {h: "FILL"}); spacer(bb);
  const c = al("HORIZONTAL", {name: "Cancel", pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"}); c.appendChild(txt("Отмена")); bb.appendChild(c);
  const o = al("HORIZONTAL", {name: "OK", pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); o.appendChild(txt(button, {style: "Semi Bold", color: "on-accent"})); bb.appendChild(o);
  return d;
}

const created = [];
MODE = "Light"; created.push(mainScreen("Main — Light", 0, 0).id);
MODE = "Dark"; created.push(mainScreen("Main — Dark", 1520, 0).id);
MODE = "Light"; created.push(dialog("New document", 0, 1000, "Новый документ", [["Шаблон", "Страница манги A4 · 150 dpi"], ["Ширина", "1240 px"], ["Высота", "1754 px"], ["Разрешение, dpi", "150"], ["Фон", "Белая бумага"], ["Анимация: кадров/с", "24"], ["Анимация: длительность", "2,0 с"]], "Создать").id);
MODE = "Light"; created.push(dialog("Adjustment", 520, 1000, "Цветовой тон / насыщенность", [["Тон", "0"], ["Насыщенность", "+20"], ["Яркость", "0"], ["", "☐ Тонирование   ☑ Предпросмотр"]], "Применить").id);
MODE = "Light"; created.push(dialog("Export", 1040, 1000, "Экспорт", [["Формат", "GIF — анимация"], ["Масштаб", "50 %"], ["", "620×877 px · 48 кадров · 24 к/с · 2.0 с"]], "Экспортировать…").id);
MODE = "Dark"; created.push(dialog("Text", 1560, 1000, "Текст", [["Текст", "Привет!"], ["Шрифт", "Georgia"], ["Размер", "36 px"], ["", "☑ Вертикально (как в японской манге)"]], "Добавить").id);
await page.children[0].screenshot({scale: 0.5});
return {pageId: page.id, createdNodeIds: created};
