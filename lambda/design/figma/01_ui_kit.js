// Лямбда (Lambda) — UI Kit page (Figma Plugin API, run via use_figma in the file «Лямбда — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Lambda")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
const MONO = ["JetBrains Mono", "Roboto Mono", "Source Code Pro", "IBM Plex Mono"].find(f => has(f, "Regular")) || "Inter";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}, {family: MONO, style: "Regular"}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors lambda/lyambda/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "canvas": ["#E9E6DC", "#191918"], "board": ["#F7F5EF", "#232322"], "dot": ["#D3CEC1", "#3F3E3A"], "paper": ["#FFFFFF", "#FFFFFF"],
  "ink": ["#141413", "#141413"], "sticky": ["#FFE29A", "#FFE29A"], "sticky-blue": ["#B8DBFF", "#B8DBFF"], "sticky-green": ["#C5EBB4", "#C5EBB4"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Lambda — " + modeName);  // Starter plan: 1 mode per collection
  col.renameMode(col.modes[0].modeId, modeName);
  colIds[modeName] = col.id;
  for (const [name, vals] of Object.entries(T)) {
    const v = figma.variables.createVariable("color/" + name, col, "COLOR");
    v.setValueForMode(col.modes[0].modeId, hex(vals[mi]));
    V[modeName][name] = v;
  }
}
let MODE = "Light";
const fill = name => figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][name]);
function txt(chars, o = {}) {
  const t = figma.createText();
  t.fontName = {family: o.family || SANS, style: o.style || "Regular"};
  t.fontSize = o.size || 13; t.characters = chars; t.fills = [fill(o.color || "text")];
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
function comp(name, dir, o = {}) {
  const c = figma.createComponent(); c.name = name; c.layoutMode = dir;
  c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "AUTO"; c.itemSpacing = o.gap ?? 8;
  const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad ?? 0, o.pad ?? 0, o.pad ?? 0, o.pad ?? 0];
  c.paddingTop = t; c.paddingRight = r; c.paddingBottom = b; c.paddingLeft = l;
  c.fills = o.fill ? [fill(o.fill)] : []; if (o.radius) c.cornerRadius = o.radius;
  if (o.stroke) { c.strokes = [fill(o.stroke)]; c.strokeWeight = 1; }
  c.counterAxisAlignItems = o.align || "CENTER";
  return c;
}
function variants(comps, parent, props = {}) {
  const set = figma.combineAsVariants(comps, parent);
  set.layoutMode = "HORIZONTAL"; set.primaryAxisSizingMode = "AUTO"; set.counterAxisSizingMode = "AUTO";
  set.itemSpacing = 16; set.paddingTop = set.paddingBottom = set.paddingLeft = set.paddingRight = 20;
  set.counterAxisAlignItems = "CENTER"; set.fills = [fill("bg")]; set.cornerRadius = 12;
  set.strokes = [fill("border")]; set.dashPattern = [4, 4];
  for (const [prop, def] of Object.entries(props)) {
    const key = set.addComponentProperty(prop, "TEXT", def);
    for (const v of set.children) { const t = v.findOne(n => n.type === "TEXT" && n.name === prop); if (t) t.componentPropertyReferences = {characters: key}; }
  }
  return set;
}



const root = al("VERTICAL", {name: "Лямбда — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [10, 34, 22, 34]}); head.appendChild(icon);
icon.appendChild(txt("λ", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Лямбда — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Дизайн · доски · презентации · сайты — офлайн · стиль Claude · коллекции «Lambda — Light» / «Lambda — Dark»", {color: "muted", size: 15}));

for (const modeName of ["Light", "Dark"]) {
  MODE = modeName;
  const row = al("HORIZONTAL", {name: "Swatches / " + modeName, gap: 10, pad: 20, radius: 14, fill: "bg", stroke: "border"});
  row.layoutWrap = "WRAP"; row.resize(1488, 100); row.primaryAxisSizingMode = "FIXED"; row.counterAxisSpacing = 12;
  for (const name of Object.keys(T)) {
    const sw = al("VERTICAL", {name, gap: 4});
    const r = figma.createRectangle(); r.resize(72, 44); r.cornerRadius = 8; r.fills = [fill(name)]; r.strokes = [fill("border")]; r.strokeWeight = 1;
    sw.appendChild(r); sw.appendChild(txt(name, {size: 10, color: "muted"})); row.appendChild(sw);
  }
  root.appendChild(row);
}
MODE = "Light";
const grid = al("HORIZONTAL", {name: "Components", gap: 24}); grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
grid.resize(1488, 100); grid.primaryAxisSizingMode = "FIXED"; root.appendChild(grid);

// Top-bar tool button (active = terracotta, like the app)
const toolBtns = ["Default", "Active"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: 6, radius: 7, fill: s === "Active" ? "accent" : null});
  c.appendChild(txt("▭", {size: 16, color: s === "Active" ? "on-accent" : "text"})); return c;
});
variants(toolBtns, grid).name = "Tool button";

// Kind card on the home screen
const kindCard = comp("Kind card", "VERTICAL", {pad: [16, 18, 16, 18], radius: 14, fill: "card", stroke: "border", gap: 6});
kindCard.counterAxisAlignItems = "MIN"; kindCard.resize(260, kindCard.height); kindCard.primaryAxisSizingMode = "AUTO"; kindCard.counterAxisSizingMode = "FIXED";
kindCard.appendChild(txt("◇", {size: 28, color: "accent"}));
const kt = txt("Дизайн", {family: SERIF, size: 17}); kt.name = "Title"; kindCard.appendChild(kt);
kindCard.appendChild(txt("Интерфейсы, макеты, иконки: фреймы, автолейаут, компоненты, прототипы", {color: "muted", w: 224}));
grid.appendChild(kindCard);

// Layer row
const layerRows = [["Default", false], ["Selected", true], ["Component", false]].map(([s, sel]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [4, 8, 4, 8], gap: 8, radius: 5, fill: sel ? "selected" : null});
  c.resize(220, c.height); c.primaryAxisSizingMode = "FIXED";
  c.appendChild(txt(s === "Component" ? "❖" : "#", {color: s === "Component" ? "accent" : "muted"}));
  const n = txt(s === "Component" ? "Кнопка / Основная" : "Главная", {color: s === "Component" ? "accent" : "text"}); n.name = "Name"; c.appendChild(n);
  return c;
});
variants(layerRows, grid, {Name: "Слой"}).name = "Layer row";

// Inspector number field (scrub label + value)
const numField = comp("Number field", "HORIZONTAL", {gap: 4, align: "CENTER"});
numField.appendChild(txt("Ш", {size: 11, color: "muted"}));
const nf = al("HORIZONTAL", {name: "Field", pad: [3, 6, 3, 6], radius: 6, fill: "input"}); nf.resize(90, nf.height); nf.primaryAxisSizingMode = "FIXED";
const nv = txt("393"); nv.name = "Value"; nf.appendChild(nv); numField.appendChild(nf); grid.appendChild(numField);

// Paint row (swatch + hex + opacity)
const paint = comp("Paint row", "HORIZONTAL", {gap: 6, align: "CENTER"});
const sw = figma.createRectangle(); sw.resize(20, 20); sw.cornerRadius = 4; sw.fills = [fill("accent")]; paint.appendChild(sw);
for (const v of ["D97757", "100%"]) { const f = al("HORIZONTAL", {name: "Field", pad: [3, 6, 3, 6], radius: 6, fill: "input"}); f.appendChild(txt(v)); paint.appendChild(f); }
paint.appendChild(txt("👁  −", {color: "muted"})); grid.appendChild(paint);

// Selection: frame + handles + size pill
const sel = comp("Selection", "VERTICAL", {gap: 8, align: "CENTER"});
const box = figma.createFrame(); box.resize(160, 100); box.fills = [fill("paper")]; box.strokes = [fill("accent")]; box.strokeWeight = 1;
for (const [x, y] of [[0, 0], [160, 0], [0, 100], [160, 100], [80, 0], [80, 100], [0, 50], [160, 50]]) {
  const h = figma.createRectangle(); h.resize(7, 7); h.x = x - 3.5; h.y = y - 3.5; h.fills = [fill("paper")]; h.strokes = [fill("accent")]; h.strokeWeight = 1.2; box.appendChild(h);
}
box.clipsContent = false; sel.appendChild(box);
const pill = al("HORIZONTAL", {name: "Size", pad: [2, 6, 2, 6], radius: 4, fill: "accent"}); pill.appendChild(txt("160 × 100", {size: 11, color: "on-accent"})); sel.appendChild(pill);
grid.appendChild(sel);

// FigJam sticky + shape + connector
const stickies = [["Yellow", "sticky"], ["Blue", "sticky-blue"], ["Green", "sticky-green"]].map(([s, col]) => {
  const c = comp("Color=" + s, "VERTICAL", {pad: 18, fill: col});
  c.resize(140, 140); c.primaryAxisSizingMode = "FIXED"; c.counterAxisSizingMode = "FIXED"; c.counterAxisAlignItems = "MIN";
  c.effects = [{type: "DROP_SHADOW", color: {r: 0, g: 0, b: 0, a: 0.12}, offset: {x: 0, y: 3}, radius: 6, spread: 0, visible: true, blendMode: "NORMAL"}];
  const t = txt("Идея", {size: 18, color: "ink"}); t.name = "Text"; c.appendChild(t); return c;
});
variants(stickies, grid, {Text: "Идея"}).name = "Sticky";
const shape = comp("Shape with text", "HORIZONTAL", {pad: [24, 30, 24, 30], radius: 14, fill: "paper", align: "CENTER"});
shape.strokes = [fill("ink")]; shape.strokeWeight = 2; shape.appendChild(txt("Шаг", {size: 16, color: "ink"})); grid.appendChild(shape);
const conn = comp("Connector", "HORIZONTAL", {pad: 8});
const cv = figma.createVector(); cv.vectorPaths = [{windingRule: "NONE", data: "M 0 0 L 60 0 L 60 50 L 120 50"}];
cv.strokes = [fill("ink")]; cv.strokeWeight = 2; cv.strokeCap = "ARROW_LINES"; conn.appendChild(cv); grid.appendChild(conn);

// Floating FigJam toolbar
const fb = comp("Board toolbar", "HORIZONTAL", {pad: [6, 10, 6, 10], radius: 14, fill: "card", stroke: "border", gap: 6});
for (const g of ["➤", "✋", "✎", "▬", "▢", "◆", "↗", "T", "▭", "☺", "🖼"]) fb.appendChild(txt(g, {size: 20}));
grid.appendChild(fb);

// Slide thumbnail + site block
const thumb = comp("Slide thumbnail", "HORIZONTAL", {gap: 8, align: "CENTER"});
const st = al("VERTICAL", {name: "Slide", pad: [14, 16, 14, 16], gap: 6, fill: "text", radius: 4}); st.resize(176, 99); st.primaryAxisSizingMode = "FIXED"; st.counterAxisSizingMode = "FIXED";
st.appendChild(txt("Лямбда", {family: SERIF, size: 16, color: "bg"})); thumb.appendChild(st); thumb.appendChild(txt("1", {color: "muted"}));
grid.appendChild(thumb);
const block = comp("Site block", "VERTICAL", {pad: 24, gap: 10, fill: "bg", radius: 10, stroke: "border", align: "CENTER"});
block.appendChild(txt("Делаем понятные продукты", {family: SERIF, size: 22}));
const bb = al("HORIZONTAL", {name: "Button", pad: [8, 16, 8, 16], radius: 8, fill: "accent"}); bb.appendChild(txt("Начать проект", {style: "Semi Bold", color: "on-accent"}));
block.appendChild(bb); grid.appendChild(block);

const btn = comp("Button / Accent", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "accent"});
btn.appendChild(txt("Презентовать", {style: "Semi Bold", color: "on-accent"})); grid.appendChild(btn);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
