// Дзета (Zeta) — Screens page: Main (Light/Dark), New sprite, Export, Welcome. Run after 01_ui_kit.js.
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
  const col = cols.find(c => c.name === "Zeta — " + mode);
  if (!col) throw new Error("Run 01_ui_kit.js first (missing collection Zeta — " + mode + ")");
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

const SLIME = [  // 32×32 demo sprite (frame 2 of «прыжок»): s sky, g grass, d dark grass, o slime, h highlight, k eye, w white, b shade
  ...Array(4).fill("s".repeat(32)),
  "s".repeat(24) + "wwww" + "ssss", "s".repeat(24) + "wwww" + "ssss", "s".repeat(24) + "wwww" + "ssss", "s".repeat(24) + "wwww" + "ssss",
  "s".repeat(32), "s".repeat(32), "s".repeat(32),
  "sssssssssoooooooooooooossssssssss".slice(0, 32),
  "ssssssssoooooooooooooooossssssss",
  "sssssssoooohhhooooooooooosssssss",
  "sssssssoooohhhooooooooooosssssss",
  "sssssssooooooooooooooooooosssssss".slice(0, 32),
  "sssssssooookkooookkooooooosssssss".slice(0, 32),
  "sssssssooookkooookkooooooosssssss".slice(0, 32),
  "sssssssooookkooookkooooooosssssss".slice(0, 32),
  "sssssssoooooooooooooooooooosssss".slice(0, 32),
  "ggggggggoooooooooooooooooggggggg".slice(0, 32),
  "ggggggggbbbbbbbbbbbbbbbbbggggggg".slice(0, 32),
  "g".repeat(32), "gggdgggggggggggggggggdgggggggggg", "g".repeat(32), "gggggggggggdgggggggggggggggggggg",
  ...Array(5).fill("g".repeat(32)),
];
const SLIME_COL = {s: "frame-current", g: "cel-empty", d: "muted", o: "accent", h: "checker-a", k: "text", w: "bg", b: "onion-prev"};
function sprite(unit) {
  const f = figma.createFrame(); f.name = "Sprite 32×32"; f.fills = []; f.resize(32 * unit, 32 * unit);
  SLIME.forEach((row, y) => { let x = 0; while (x < 32) { const ch = row[x] || "s"; let n = 1; while (x + n < 32 && (row[x + n] || "s") === ch) n++;
    const r = figma.createRectangle(); r.resize(n * unit, unit); r.x = x * unit; r.y = y * unit; r.fills = [fill(SLIME_COL[ch] || "frame-current")]; f.appendChild(r); x += n; } });
  return f;
}
function windowFrame(name, x, y) {
  const win = al("VERTICAL", {name, gap: 0, fill: "bg"});
  win.resize(1440, 900); win.primaryAxisSizingMode = "FIXED"; win.counterAxisSizingMode = "FIXED";
  win.cornerRadius = 12; win.clipsContent = true; win.x = x; win.y = y;
  win.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  return win;
}
function contextBar(tool) {
  const b = al("HORIZONTAL", {name: "Context bar", gap: 12, pad: [8, 14, 8, 14], align: "CENTER"}); border(b, {b: 1});
  b.appendChild(txt(tool, {family: SERIF, size: 17}));
  for (const [l, v] of [["Кисть", "1 px"], ["", "■ квадрат"]]) {
    if (l) b.appendChild(txt(l, {color: "muted"}));
    const f = al("HORIZONTAL", {name: "Field", pad: [3, 8, 3, 8], radius: 6, fill: "input", stroke: "border"}); f.appendChild(txt(v)); b.appendChild(f);
  }
  b.appendChild(txt("☐ Pixel-perfect", {})); b.appendChild(txt("Симметрия ⇹ ⇳", {color: "muted"}));
  spacer(b); b.appendChild(txt("ПКМ — второй цвет · ⇧ — линия · Alt — пипетка", {size: 12, color: "muted"}));
  b.appendChild(txt("#   1600%", {color: "muted"}));
  return b;
}
function toolbox() {
  const t = al("VERTICAL", {name: "Tools", gap: 6, pad: [10, 9, 10, 9], fill: "panel", align: "CENTER"}); border(t, {r: 1});
  t.resize(64, 10); t.counterAxisSizingMode = "FIXED";
  t.appendChild(txt("ζ", {family: SERIF, style: SERIF_I, size: 26, color: "accent"}));
  ["✎", "⌫", "⦿", "▧", "╱", "▭", "◯", "⬚", "➰", "✧", "✥", "✋", "⌕"].forEach((g, i) => {
    const b = al("HORIZONTAL", {name: "Tool " + i, pad: [6, 12, 6, 12], radius: 7, fill: i === 0 ? "selected" : null, stroke: i === 0 ? "accent" : null});
    b.appendChild(txt(g, {size: 15, color: i === 0 ? "accent" : "text"})); t.appendChild(b);
  });
  spacer(t);
  const sw = figma.createFrame(); sw.fills = []; sw.resize(46, 46);
  const back = figma.createRectangle(); back.resize(28, 28); back.x = 17; back.y = 17; back.fills = [fill("text")];
  const front = figma.createRectangle(); front.resize(28, 28); front.fills = [fill("accent")]; front.strokes = [fill("border")]; front.strokeWeight = 1;
  sw.appendChild(back); sw.appendChild(front); t.appendChild(sw);
  return t;
}
function colorPanel() {
  const p = al("VERTICAL", {name: "Colour panel", gap: 8, pad: [12, 12, 12, 12], fill: "panel"}); border(p, {l: 1});
  p.resize(250, 10); p.counterAxisSizingMode = "FIXED";
  p.appendChild(section("Цвет"));
  const sv = figma.createRectangle(); sv.name = "SV square"; sv.resize(226, 220); sv.cornerRadius = 4;
  sv.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [{position: 0, color: {r: 1, g: 1, b: 1, a: 1}}, {position: 1, color: {r: 0.85, g: 0.47, b: 0.34, a: 1}}]},
              {type: "GRADIENT_LINEAR", gradientTransform: [[0, 1, 0], [-1, 0, 1]], gradientStops: [{position: 0, color: {r: 0, g: 0, b: 0, a: 0}}, {position: 1, color: {r: 0, g: 0, b: 0, a: 1}}]}];
  p.appendChild(sv);
  const hue = figma.createRectangle(); hue.name = "Hue"; hue.resize(226, 10); hue.cornerRadius = 2;
  hue.fills = [{type: "GRADIENT_LINEAR", gradientTransform: [[1, 0, 0], [0, 1, 0]], gradientStops: [0, 1/6, 2/6, 3/6, 4/6, 5/6, 1].map((pos, i) => ({position: pos, color: [{r:1,g:0,b:0},{r:1,g:1,b:0},{r:0,g:1,b:0},{r:0,g:1,b:1},{r:0,g:0,b:1},{r:1,g:0,b:1},{r:1,g:0,b:0}][i]})).map(s => ({position: s.position, color: {...s.color, a: 1}}))}];
  p.appendChild(hue);
  const hex = al("HORIZONTAL", {name: "Hex", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); hex.appendChild(txt("#D97757")); add(p, hex, {h: "FILL"});
  const pr = al("HORIZONTAL", {name: "Palette header", gap: 6}); add(p, pr, {h: "FILL"}); pr.appendChild(section("Палитра")); spacer(pr); pr.appendChild(txt("Пресет…  ···", {color: "muted"}));
  const pal = al("HORIZONTAL", {name: "Palette", gap: 1}); pal.layoutWrap = "WRAP"; pal.counterAxisSpacing = 1; pal.resize(226, 10); pal.primaryAxisSizingMode = "FIXED";
  for (const k of ["text", "muted", "faint", "border", "panel", "bg", "card", "onion-prev", "accent", "cel", "frame-current", "onion-next", "cel-empty", "selected", "hover", "checker-b"]) {
    const r = figma.createRectangle(); r.resize(16, 16); r.fills = [fill(k)]; pal.appendChild(r);
  }
  p.appendChild(pal);
  p.appendChild(section("Предпросмотр"));
  const pv = al("HORIZONTAL", {name: "Preview", pad: 20, fill: "canvas"}); pv.primaryAxisAlignItems = "CENTER"; pv.appendChild(sprite(6)); add(p, pv, {h: "FILL", v: "FILL"});
  return p;
}
function timeline() {
  const t = al("VERTICAL", {name: "Timeline", gap: 0, fill: "panel"}); border(t, {t: 1});
  const bar = al("HORIZONTAL", {name: "Controls", gap: 12, pad: [6, 10, 6, 10], align: "CENTER"}); add(t, bar, {h: "FILL"});
  bar.appendChild(section("Таймлайн"));
  for (const s of ["⏮", "◀", "▶", "▶▶", "⏭", "◐", "＋ кадр", "⧉ кадр", "− кадр", "＋ слой", "− слой"]) bar.appendChild(txt(s, {color: s === "▶" ? "accent" : "text"}));
  spacer(bar); bar.appendChild(txt("Длительность", {color: "muted"}));
  const d = al("HORIZONTAL", {name: "Duration", pad: [3, 8, 3, 8], radius: 6, fill: "input", stroke: "border"}); d.appendChild(txt("120 мс")); bar.appendChild(d);
  bar.appendChild(txt("8.3 к/с · кадр 2 из 4", {color: "muted"}));
  const head = al("HORIZONTAL", {name: "Header", gap: 0}); add(t, head, {h: "FILL"});
  const pad = figma.createFrame(); pad.fills = []; pad.resize(190, 34); head.appendChild(pad);
  const frames = al("VERTICAL", {name: "Frames", gap: 0}); head.appendChild(frames);
  const tg = al("HORIZONTAL", {name: "Tag прыжок", pad: [0, 4, 0, 4], fill: "accent"}); tg.resize(96, 14); tg.primaryAxisSizingMode = "FIXED"; tg.appendChild(txt("прыжок", {size: 10, color: "on-accent"})); frames.appendChild(tg);
  const nums = al("HORIZONTAL", {name: "Numbers", gap: 0}); frames.appendChild(nums);
  for (let f = 1; f <= 4; f++) { const n = al("HORIZONTAL", {name: "F" + f, fill: f === 2 ? "frame-current" : null}); n.resize(24, 20); n.primaryAxisSizingMode = "FIXED"; n.counterAxisSizingMode = "FIXED"; n.primaryAxisAlignItems = "CENTER"; n.counterAxisAlignItems = "CENTER"; n.appendChild(txt(String(f), {size: 10, color: f === 2 ? "text" : "muted"})); nums.appendChild(n); }
  for (const [name, sel] of [["Глаза", false], ["Слизень", true], ["Фон", false]]) {
    const row = al("HORIZONTAL", {name: "Layer " + name, gap: 0}); add(t, row, {h: "FILL"}); border(row, {b: 1});
    const l = al("HORIZONTAL", {name: "Name", gap: 10, pad: [4, 8, 4, 8], fill: sel ? "selected" : null}); l.resize(190, 24); l.primaryAxisSizingMode = "FIXED"; l.counterAxisSizingMode = "FIXED";
    l.appendChild(txt("●")); l.appendChild(txt("·", {color: "faint"})); l.appendChild(txt(name)); row.appendChild(l);
    for (let f = 1; f <= 4; f++) { const c = al("HORIZONTAL", {name: "Cel", fill: f === 2 ? "frame-current" : null}); c.resize(24, 24); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED"; c.primaryAxisAlignItems = "CENTER"; c.counterAxisAlignItems = "CENTER";
      const e = figma.createEllipse(); e.resize(8, 8); e.fills = [fill("cel")]; c.appendChild(e); row.appendChild(c); }
  }
  return t;
}
function mainScreen(name, x, y) {
  const win = windowFrame(name, x, y);
  add(win, contextBar("Карандаш"), {h: "FILL"});
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  add(body, toolbox(), {v: "FILL"});
  const center = al("VERTICAL", {name: "Center", gap: 0}); add(body, center, {h: "FILL", v: "FILL"});
  const tabs = al("HORIZONTAL", {name: "Tabs", pad: [6, 12, 0, 12]}); add(center, tabs, {h: "FILL"});
  const tab = al("HORIZONTAL", {name: "Tab слизень", pad: [0, 4, 6, 4], gap: 8}); tab.strokes = [fill("accent")]; tab.strokeTopWeight = 0; tab.strokeLeftWeight = 0; tab.strokeRightWeight = 0; tab.strokeBottomWeight = 2;
  tab.appendChild(txt("слизень")); tab.appendChild(txt("×", {color: "muted"})); tabs.appendChild(tab);
  const canvas = al("HORIZONTAL", {name: "Canvas", fill: "canvas"}); add(center, canvas, {h: "FILL", v: "FILL"});
  canvas.primaryAxisAlignItems = "CENTER"; canvas.counterAxisAlignItems = "CENTER";
  canvas.appendChild(sprite(16));
  const tl = timeline(); add(center, tl, {h: "FILL"});
  add(body, colorPanel(), {v: "FILL"});
  const sb = al("HORIZONTAL", {name: "Status bar", gap: 14, pad: [4, 12, 4, 12], fill: "panel"}); border(sb, {t: 1}); add(win, sb, {h: "FILL"});
  sb.appendChild(txt("x 20  y 14", {size: 11, color: "muted"})); sb.appendChild(txt("#D97757 · α 255", {size: 11, color: "muted"})); spacer(sb);
  sb.appendChild(txt("32×32 px · 3 сл. · 4 к.", {size: 11, color: "muted"}));
  return win;
}
function dialog(name, x, y, title, rows, button) {
  const d = al("VERTICAL", {name: name + " — " + MODE, gap: 10, pad: [22, 26, 20, 26], radius: 12, fill: "bg", stroke: "border"});
  d.resize(440, 10); d.counterAxisSizingMode = "FIXED"; d.x = x; d.y = y;
  d.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.15}, offset: {x: 0, y: 12}, radius: 40, spread: 0, visible: true, blendMode: "NORMAL"}];
  d.appendChild(txt(title, {family: SERIF, size: 28}));
  for (const [k, v] of rows) {
    if (k === "presets") { const r = al("HORIZONTAL", {name: "Presets", gap: 6}); for (const p of v) { const b = al("HORIZONTAL", {name: p, pad: [4, 8, 4, 8], radius: 6, fill: "card", stroke: "border"}); b.appendChild(txt(p, {size: 12})); r.appendChild(b); } d.appendChild(r); continue; }
    const r = al("HORIZONTAL", {name: k, gap: 12, align: "CENTER"}); add(d, r, {h: "FILL"});
    r.appendChild(txt(k, {w: 130}));
    const f = al("HORIZONTAL", {name: "Field", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "border"}); f.appendChild(txt(v)); add(r, f, {h: "FILL"});
  }
  const bb = al("HORIZONTAL", {name: "Buttons", gap: 8}); add(d, bb, {h: "FILL"}); spacer(bb);
  const c = al("HORIZONTAL", {name: "Cancel", pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"}); c.appendChild(txt("Отмена")); bb.appendChild(c);
  const o = al("HORIZONTAL", {name: "OK", pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); o.appendChild(txt(button, {style: "Semi Bold", color: "on-accent"})); bb.appendChild(o);
  return d;
}
function welcome(x, y) {
  const win = windowFrame("Welcome — " + MODE, x, y);
  add(win, contextBar("Карандаш"), {h: "FILL"});
  const body = al("HORIZONTAL", {name: "Body", gap: 0}); add(win, body, {h: "FILL", v: "FILL"});
  add(body, toolbox(), {v: "FILL"});
  const c = al("VERTICAL", {name: "Welcome", gap: 14, pad: [150, 80, 40, 260], fill: "bg"}); add(body, c, {h: "FILL", v: "FILL"});
  const head = al("HORIZONTAL", {name: "Logo", gap: 18, align: "CENTER"}); c.appendChild(head);
  head.appendChild(txt("ζ", {family: SERIF, style: SERIF_I, size: 110, color: "accent"}));
  const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
  hc.appendChild(txt("Дзета", {family: SERIF, size: 34})); hc.appendChild(txt("Пиксель-арт и анимация · версия 1.0.0", {color: "muted"}));
  const cols = al("HORIZONTAL", {name: "Columns", gap: 60}); c.appendChild(cols);
  const a = al("VERTICAL", {name: "Start", gap: 6}); cols.appendChild(a); a.appendChild(section("Начало"));
  for (const s of ["Новый спрайт…", "Открыть…", "Вставить из буфера как спрайт"]) a.appendChild(txt(s, {color: "accent"}));
  const b = al("VERTICAL", {name: "Recent", gap: 6}); cols.appendChild(b); b.appendChild(section("Недавние"));
  for (const s of ["слизень.aseprite", "герой-бег.aseprite", "тайлы.png"]) b.appendChild(txt(s, {color: "accent"}));
  c.appendChild(txt("B карандаш · E ластик · I пипетка · G заливка · M выделение · V перемещение · Enter — анимация", {color: "muted"}));
  return win;
}

const created = [];
MODE = "Light"; created.push(mainScreen("Main — Light", 0, 0).id);
MODE = "Dark"; created.push(mainScreen("Main — Dark", 1520, 0).id);
MODE = "Light"; created.push(welcome(0, 1000).id);
MODE = "Light"; created.push(dialog("New sprite", 1520, 1000, "Новый спрайт", [["presets", ["16×16", "32×32", "64×64", "128×128", "256×144"]], ["Ширина, px", "32"], ["Высота, px", "32"], ["Фон", "Прозрачный"], ["Палитра", "DB32"]], "Создать").id);
MODE = "Light"; created.push(dialog("Export", 2020, 1000, "Экспорт", [["Формат", "GIF — анимация"], ["Масштаб", "4×"], ["Кадры", "Метка «прыжок» (1–4)"], ["Раскладка листа", "В строку"]], "Экспортировать…").id);
MODE = "Dark"; created.push(dialog("Layer properties", 2520, 1000, "Свойства слоя", [["Имя", "Слизень"], ["Наложение", "Обычный"], ["Непрозрачность", "255"]], "OK").id);
await page.children[0].screenshot({scale: 0.5});
return {pageId: page.id, createdNodeIds: created};
