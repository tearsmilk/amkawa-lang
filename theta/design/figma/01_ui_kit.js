// Тета (Theta) — UI Kit page (Figma Plugin API, run via use_figma in the file «Тета — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Theta")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors theta/theta/theme.py (+ overlay colours from theme.extra)
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "sidebar": ["#F0EEE6", "#1F1E1D"], "ok": ["#4E8A5A", "#7BB487"], "warn": ["#B5642E", "#E59866"],
  "overlay": ["#141413", "#141413"], "viewer": ["#141413", "#141413"], "map-water": ["#D9E6EF", "#D9E6EF"], "hero-b": ["#3B4A6B", "#3B4A6B"],
  "white": ["#FFFFFF", "#FFFFFF"], "ink": ["#141413", "#141413"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Theta — " + modeName);  // Starter plan: 1 mode per collection
  col.renameMode(col.modes[0].modeId, modeName);
  colIds[modeName] = col.id;
  for (const [name, vals] of Object.entries(T)) {
    const v = figma.variables.createVariable("color/" + name, col, "COLOR");
    v.setValueForMode(col.modes[0].modeId, hex(vals[mi]));
    V[modeName][name] = v;
  }
}
let MODE = "Light";
const fill = (name, opacity) => { const p = figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][name]); if (opacity !== undefined) p.opacity = opacity; return p; };
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
function comp(name, dir, o = {}) {
  const c = figma.createComponent(); c.name = name; c.layoutMode = dir;
  c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "AUTO"; c.itemSpacing = o.gap ?? 8;
  const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad ?? 0, o.pad ?? 0, o.pad ?? 0, o.pad ?? 0];
  c.paddingTop = t; c.paddingRight = r; c.paddingBottom = b; c.paddingLeft = l;
  c.fills = o.fill ? [fill(o.fill, o.opacity)] : []; if (o.radius) c.cornerRadius = o.radius;
  if (o.stroke) { c.strokes = [fill(o.stroke)]; c.strokeWeight = 1; }
  c.counterAxisAlignItems = o.align || "CENTER";
  return c;
}
function pick(labelText, value, w = 300) {
  const row = al("HORIZONTAL", {name: "Pick " + labelText, gap: 10, align: "CENTER"});
  row.appendChild(txt(labelText, {color: "white", size: 13}));
  const box = al("HORIZONTAL", {name: "Combo", pad: [8, 10, 8, 10], radius: 8, fill: "white", opacity: 0.92}); box.resize(w, 34); box.primaryAxisSizingMode = "FIXED";
  box.appendChild(txt(value, {color: "ink"})); const sp = al("HORIZONTAL"); sp.layoutGrow = 1; box.appendChild(sp); box.appendChild(txt("▾", {color: "ink"}));
  row.appendChild(box); return row;
}
function check(t, on) { const r = al("HORIZONTAL", {name: "Check " + t, gap: 6, align: "CENTER"}); const b = figma.createRectangle(); b.resize(14, 14); b.cornerRadius = 4; b.fills = [fill(on ? "accent" : "white", on ? 1 : 0.15)]; b.strokes = [fill("white", 0.7)]; r.appendChild(b); r.appendChild(txt(t, {color: "white"})); return r; }
function iconBtn(glyph) { const b = al("HORIZONTAL", {name: "Tool", pad: [4, 8, 4, 8], radius: 6}); b.appendChild(txt(glyph, {color: "white", size: 14})); return b; }

const root = al("VERTICAL", {name: "Тета — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const headR = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(headR);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [6, 30, 26, 30]}); headR.appendChild(icon);
icon.appendChild(txt("θ", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); headR.appendChild(hc);
hc.appendChild(txt("Тета — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Локальный GeoGuessr · Street View / Mapillary / Commons · карта OSM · коллекции «Theta — Light» / «Theta — Dark»", {color: "muted", size: 15}));
const grid = al("HORIZONTAL", {name: "Components", gap: 24}); grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
grid.resize(1488, 100); grid.primaryAxisSizingMode = "FIXED"; root.appendChild(grid);

const play = comp("Play button", "HORIZONTAL", {pad: [10, 30, 10, 30], radius: 10, fill: "accent"}); play.appendChild(txt("▶  Играть", {size: 16, style: "Semi Bold", color: "on-accent"})); grid.appendChild(play);
// Hero: new game card
const hero = comp("Hero / New game", "HORIZONTAL", {pad: [22, 26, 22, 26], gap: 20, radius: 18, fill: "hero-b"}); hero.resize(760, 230); hero.primaryAxisSizingMode = "FIXED"; hero.counterAxisAlignItems = "MIN";
const hl = al("VERTICAL", {name: "Left", gap: 10}); hl.layoutGrow = 1;
hl.appendChild(txt("Новая игра", {family: SERIF, size: 34, color: "white"})); hl.appendChild(txt("Мир · 5 раундов · до 25 000 очков", {color: "white", size: 13}));
hl.appendChild(pick("Карта", "Мир")); hl.appendChild(pick("Режим", "Классика")); hl.appendChild(pick("Источник", "Google Street View — интерактивные панорамы")); hl.appendChild(pick("Время на раунд", "Без ограничения"));
const opts = al("HORIZONTAL", {name: "Options", gap: 14}); opts.appendChild(check("Без движения", false)); opts.appendChild(check("Без поворота", false)); opts.appendChild(check("Без зума", true)); hl.appendChild(opts);
hero.appendChild(hl); const hr = al("VERTICAL", {name: "Right", gap: 8}); hr.appendChild(play.createInstance()); hero.appendChild(hr); grid.appendChild(hero);
// Mini card (daily)
const mini = comp("Mini card", "HORIZONTAL", {pad: [10, 12, 10, 12], gap: 12, radius: 12, fill: "card", stroke: "border"}); mini.resize(420, 64); mini.primaryAxisSizingMode = "FIXED";
mini.appendChild(txt("📅", {size: 22})); const mc = al("VERTICAL", {gap: 2}); mc.appendChild(txt("Задание дня", {family: SERIF, size: 16})); mc.appendChild(txt("Ещё не сыграно · 5 раундов, мир", {size: 11, color: "muted"})); mini.appendChild(mc); grid.appendChild(mini);
// Record row
const rec = comp("Record row", "HORIZONTAL", {pad: [10, 14, 10, 14], gap: 12, radius: 14, fill: "card", stroke: "border"}); rec.resize(720, 56); rec.primaryAxisSizingMode = "FIXED";
rec.appendChild(txt("1.", {family: SERIF, size: 16})); const rc = al("VERTICAL", {gap: 2}); rc.layoutGrow = 1; rc.appendChild(txt("Европа · Классика", {family: SERIF, size: 16})); rc.appendChild(txt("Hoka · 24.10.2026 00:12", {size: 11, color: "muted"})); rec.appendChild(rc); rec.appendChild(txt("21 480 / 25 000", {family: SERIF, size: 16})); grid.appendChild(rec);
// Overlay top bar
const top = comp("Overlay / Round bar", "HORIZONTAL", {pad: [8, 14, 8, 14], gap: 14, radius: 12, fill: "overlay", opacity: 0.62}); top.resize(520, 40); top.primaryAxisSizingMode = "FIXED";
for (const [t, o] of [["Раунд 2 / 5", {family: SERIF, size: 16}], ["4 870 очков", {}], ["⏱ 0:42", {}], ["Европа · Классика", {size: 11}]]) top.appendChild(txt(t, {...o, color: "white"}));
const spc = al("HORIZONTAL"); spc.layoutGrow = 1; top.appendChild(spc); top.appendChild(txt("✕", {color: "white"})); grid.appendChild(top);
// Controls
const ctrl = comp("Overlay / Controls", "HORIZONTAL", {pad: [4, 6, 4, 6], gap: 2, radius: 12, fill: "overlay", opacity: 0.62}); for (const g of ["‹", "◎", "›", "+", "−"]) ctrl.appendChild(iconBtn(g)); grid.appendChild(ctrl);
// Map panel
const mapP = comp("Map panel / expanded", "VERTICAL", {pad: 6, gap: 6, radius: 12, fill: "bg", stroke: "border"}); mapP.resize(340, 240); mapP.primaryAxisSizingMode = "FIXED"; mapP.counterAxisAlignItems = "MIN";
const mt = al("HORIZONTAL", {name: "Top", gap: 4, align: "CENTER"}); mt.appendChild(txt("📌", {size: 12})); const ms = al("HORIZONTAL"); ms.layoutGrow = 1; mt.appendChild(ms);
for (const n of ["1", "2", "3", "4"]) { const b = al("HORIZONTAL", {pad: [2, 7, 2, 7], radius: 6, fill: n === "2" ? "selected" : undefined}); b.appendChild(txt(n, {size: 11})); mt.appendChild(b); } mt.appendChild(txt("−  +", {size: 12})); mapP.appendChild(mt);
const mapArea = al("HORIZONTAL", {name: "Map", fill: "map-water", radius: 6}); mapArea.resize(328, 150); mapArea.primaryAxisSizingMode = "FIXED"; mapArea.counterAxisSizingMode = "FIXED"; mapArea.layoutGrow = 1;
const pin = figma.createEllipse(); pin.resize(14, 14); pin.fills = [fill("accent")]; pin.strokes = [fill("white")]; pin.strokeWeight = 2; mapArea.appendChild(pin); mapArea.paddingLeft = 150; mapArea.paddingTop = 60; mapP.appendChild(mapArea);
const ans = al("HORIZONTAL", {name: "Answer", pad: [6, 12, 6, 12], radius: 7, fill: "accent"}); ans.resize(328, 30); ans.primaryAxisSizingMode = "FIXED"; ans.primaryAxisAlignItems = "CENTER"; ans.appendChild(txt("Ответить", {style: "Semi Bold", color: "on-accent"})); mapP.appendChild(ans); grid.appendChild(mapP);
// Result panel
const res = comp("Result panel", "VERTICAL", {pad: [14, 20, 14, 20], gap: 6, radius: 14, fill: "overlay", opacity: 0.82}); res.resize(520, 110); res.primaryAxisSizingMode = "FIXED"; res.counterAxisAlignItems = "MIN";
res.appendChild(txt("4 870 очков", {family: SERIF, size: 26, color: "white"})); res.appendChild(txt("312 м от места · Франция · 41 с", {color: "white"}));
const rr = al("HORIZONTAL"); const rsp = al("HORIZONTAL"); rsp.layoutGrow = 1; rr.appendChild(rsp); const nb = al("HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); nb.appendChild(txt("Следующий раунд", {style: "Semi Bold", color: "on-accent"})); rr.appendChild(nb); rr.resize(480, 30); rr.primaryAxisSizingMode = "FIXED"; res.appendChild(rr); grid.appendChild(res);
// Toast & attribution
const toast = comp("Toast", "HORIZONTAL", {pad: [8, 16, 8, 16], radius: 10, fill: "text"}); toast.appendChild(txt("Поставьте метку на карте", {color: "bg"})); grid.appendChild(toast);
const attr = comp("Attribution", "HORIZONTAL", {pad: [3, 8, 3, 8], radius: 6, fill: "overlay", opacity: 0.55}); attr.appendChild(txt("Ivan Petrov · CC BY 4.0 · Wikimedia Commons", {size: 10, color: "white"})); grid.appendChild(attr);
const sws = comp("Accent swatches", "HORIZONTAL", {pad: 12, gap: 6, radius: 12, fill: "card", stroke: "border"});
for (const [i, c] of ["#D97757", "#3B82C4", "#4E8A5A", "#8E6BC4", "#D06A8F", "#D9A23A", "#3FA7C4", "#5E5D59", "#C8463C", "#3FB08A"].entries()) { const e = figma.createEllipse(); e.resize(24, 24); e.fills = [{type: "SOLID", color: hex(c)}]; if (!i) { e.strokes = [fill("text")]; e.strokeWeight = 3; } sws.appendChild(e); }
grid.appendChild(sws);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
