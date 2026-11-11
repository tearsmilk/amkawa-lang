// Гамма (Gamma) — UI Kit page (Figma Plugin API, run via use_figma in the file «Гамма — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Gamma")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors gamma/gamma/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "sidebar": ["#F0EEE6", "#1F1E1D"], "rec": ["#D64545", "#E05A5A"], "dim": ["#141413", "#141413"], "ink": ["#141413", "#141413"],
  "desk-a": ["#3B4A6B", "#3B4A6B"], "desk-b": ["#D97757", "#D97757"], "ivory": ["#FAF9F5", "#FAF9F5"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Gamma — " + modeName);  // Starter plan: 1 mode per collection
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

const root = al("VERTICAL", {name: "Гамма — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [6, 30, 26, 30]}); head.appendChild(icon);
icon.appendChild(txt("γ", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Гамма — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Запись экрана и скриншоты · область или весь экран · звук · откат · коллекции «Gamma — Light» / «Gamma — Dark»", {color: "muted", size: 15}));

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

// Action card (home): icon, hotkey, serif title, hint
const cards = [["Снимок области", "⇧⌘2", "▣", "accent"], ["Запись области", "⇧⌘8", "●", "rec"]].map(([title, key, g, c]) => {
  const k = comp("Kind=" + title, "VERTICAL", {pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border", gap: 6});
  k.counterAxisAlignItems = "MIN"; k.resize(240, k.height); k.counterAxisSizingMode = "FIXED";
  const top = al("HORIZONTAL", {name: "Top", gap: 8, align: "CENTER"}); top.resize(208, 30); top.primaryAxisSizingMode = "FIXED"; top.primaryAxisAlignItems = "SPACE_BETWEEN";
  top.appendChild(txt(g, {size: 24, color: c}));
  const kb = al("HORIZONTAL", {name: "Kbd", pad: [1, 6, 1, 6], radius: 5, fill: "panel", stroke: "border"}); kb.appendChild(txt(key, {size: 11, color: "muted"})); top.appendChild(kb);
  k.appendChild(top);
  const t = txt(title, {family: SERIF, size: 16}); t.name = "Title"; k.appendChild(t);
  k.appendChild(txt("Выделите мышкой — сохранится и скопируется", {size: 11, color: "muted", w: 208}));
  return k;
});
variants(cards, grid, {Title: "Снимок области"}).name = "Action card";

// Audio segmented control
const seg = al("HORIZONTAL", {name: "Audio segments", gap: 0}); grid.appendChild(seg);
["Без звука", "Микрофон", "Звук системы", "Микрофон + система"].forEach((t, i) => {
  const b = comp(i === 0 ? "Segment / Selected" : "Segment / " + t, "HORIZONTAL", {pad: [5, 12, 5, 12], fill: i === 0 ? "selected" : "card", stroke: i === 0 ? "accent" : "border"});
  b.topLeftRadius = b.bottomLeftRadius = i === 0 ? 7 : 0; b.topRightRadius = b.bottomRightRadius = i === 3 ? 7 : 0;
  b.appendChild(txt(t)); seg.appendChild(b);
});

// Replay box (on)
const rb = comp("Replay box", "HORIZONTAL", {pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "accent", gap: 14});
rb.counterAxisAlignItems = "MIN"; rb.resize(720, rb.height); rb.primaryAxisSizingMode = "FIXED";
rb.appendChild(txt("↺", {size: 28, color: "accent"}));
const rc = al("VERTICAL", {name: "Text", gap: 4}); rc.layoutGrow = 1;
const rh = al("HORIZONTAL", {name: "Head", gap: 8, align: "CENTER"}); rh.appendChild(txt("Откат", {family: SERIF, size: 18}));
const badge = al("HORIZONTAL", {name: "Badge", pad: [1, 8, 1, 8], radius: 8, fill: "accent"}); badge.appendChild(txt("● идёт", {size: 11, color: "on-accent"})); rh.appendChild(badge);
rc.appendChild(rh);
rc.appendChild(txt("Гамма постоянно помнит последние 05:00 экрана. Нажмите ⇧⌘0 — и получите видео: 05:00 до нажатия + 01:00 после (итого 06:00).", {color: "muted", w: 480}));
rc.appendChild(txt("В буфере 03:12 из 05:00", {size: 11, color: "muted"}));
rb.appendChild(rc);
const rbtn = al("VERTICAL", {name: "Buttons", gap: 6});
const off = al("HORIZONTAL", {name: "Toggle", pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"}); off.appendChild(txt("Выключить")); rbtn.appendChild(off);
const save = al("HORIZONTAL", {name: "Save", pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); save.appendChild(txt("Сохранить откат", {style: "Semi Bold", color: "on-accent"})); rbtn.appendChild(save);
rb.appendChild(rbtn); grid.appendChild(rb);

// Hotkey field
const hks = ["Default", "Listening"].map(s => {
  const h = comp("State=" + s, "HORIZONTAL", {pad: [3, 8, 3, 8], radius: 6, fill: "input", stroke: s === "Listening" ? "accent" : "border"});
  h.resize(130, h.height); h.primaryAxisSizingMode = "FIXED"; h.primaryAxisAlignItems = "CENTER";
  const t = txt(s === "Listening" ? "Нажмите сочетание…" : "⇧⌘2"); t.name = "Value"; h.appendChild(t); return h;
});
variants(hks, grid, {Value: "⇧⌘2"}).name = "Hotkey field";

// Selection toolbar (over the screen)
const sb = comp("Selection toolbar", "HORIZONTAL", {pad: [5, 6, 5, 6], radius: 12, fill: "ivory", stroke: "border", gap: 2});
sb.appendChild(txt("Звук:", {size: 11, color: "muted"}));
for (const [t, on] of [["Без звука", false], ["Микрофон", true], ["Система", false], ["Оба", false]]) {
  const b = al("HORIZONTAL", {name: t, pad: [5, 9, 5, 9], radius: 7, fill: on ? "selected" : null}); b.appendChild(txt(t, {color: "ink"})); sb.appendChild(b);
}
const cancel = al("HORIZONTAL", {name: "Cancel", pad: [5, 9, 5, 9], radius: 7}); cancel.appendChild(txt("Отмена", {color: "ink"})); sb.appendChild(cancel);
const go = al("HORIZONTAL", {name: "Start", pad: [5, 14, 5, 14], radius: 7, fill: "rec"}); go.appendChild(txt("●  Начать запись", {style: "Semi Bold", color: "on-accent"})); sb.appendChild(go);
grid.appendChild(sb);

// Size pill + loupe
const pill = comp("Size pill", "HORIZONTAL", {pad: [4, 10, 4, 10], radius: 12, fill: "dim"}); pill.opacity = 0.9;
pill.appendChild(txt("1280 × 720", {size: 12, color: "ivory"})); grid.appendChild(pill);
const loupe = comp("Loupe", "VERTICAL", {pad: 0, gap: 6, align: "CENTER"});
const lens = figma.createFrame(); lens.resize(116, 116); lens.cornerRadius = 12; lens.fills = [fill("ink")]; lens.strokes = [fill("ivory")]; lens.strokeWeight = 2;
const lv = figma.createVector(); lv.vectorPaths = [{windingRule: "NONE", data: "M 58 0 L 58 116 M 0 58 L 116 58"}]; lv.strokes = [fill("accent")]; lv.strokeWeight = 1; lens.appendChild(lv);
loupe.appendChild(lens); const lp = al("HORIZONTAL", {name: "Coords", pad: [3, 10, 3, 10], radius: 12, fill: "dim"}); lp.appendChild(txt("800, 600", {size: 12, color: "ivory"})); loupe.appendChild(lp);
grid.appendChild(loupe);

// Recording bar
const bar = comp("Record bar", "HORIZONTAL", {pad: [7, 8, 7, 12], radius: 14, fill: "ivory", stroke: "border", gap: 8});
const dot = figma.createEllipse(); dot.resize(10, 10); dot.fills = [fill("rec")]; bar.appendChild(dot);
bar.appendChild(txt("01:23", {family: SERIF, size: 17, color: "ink"}));
bar.appendChild(txt("Запись области · микрофон", {size: 11, color: "muted"}));
const stop = al("HORIZONTAL", {name: "Stop", pad: [4, 10, 4, 10], radius: 7, fill: "rec"}); stop.appendChild(txt("Стоп", {style: "Semi Bold", color: "on-accent"})); bar.appendChild(stop);
bar.appendChild(txt("🗑", {size: 13})); grid.appendChild(bar);

// Recording frame
const frame = comp("Record frame", "HORIZONTAL", {pad: 0});
const fr = figma.createRectangle(); fr.resize(220, 130); fr.cornerRadius = 3; fr.fills = []; fr.strokes = [fill("rec")]; fr.strokeWeight = 2; fr.dashPattern = [6, 4];
frame.appendChild(fr); grid.appendChild(frame);

// Countdown
const cd = comp("Countdown", "VERTICAL", {pad: 0, gap: 4, align: "CENTER"});
const circ = al("HORIZONTAL", {name: "Circle", radius: 70, fill: "accent", pad: [10, 48, 18, 48]}); circ.appendChild(txt("3", {family: SERIF, size: 76, color: "on-accent"})); cd.appendChild(circ);
cd.appendChild(txt("щелчок — отмена", {size: 11, color: "muted"})); grid.appendChild(cd);

// Toast
const toast = comp("Toast", "HORIZONTAL", {pad: 10, radius: 14, fill: "ivory", stroke: "border", gap: 10});
toast.resize(340, toast.height); toast.primaryAxisSizingMode = "FIXED"; toast.counterAxisAlignItems = "MIN";
const th = figma.createRectangle(); th.resize(96, 64); th.cornerRadius = 8; th.fills = [fill("desk-a")]; toast.appendChild(th);
const tc = al("VERTICAL", {name: "Text", gap: 3});
const tt = txt("Откат сохранён", {family: SERIF, size: 15, color: "ink"}); tt.name = "Title"; tc.appendChild(tt);
tc.appendChild(txt("Откат 2026-10-17 в 15.10.00.mp4 · 06:00", {size: 11, color: "muted", w: 210}));
const tb = al("HORIZONTAL", {name: "Actions", gap: 4});
for (const t of ["Открыть", "Показать"]) { const b = al("HORIZONTAL", {name: t, pad: [4, 10, 4, 10], radius: 7, fill: "card", stroke: "border"}); b.appendChild(txt(t, {size: 12})); tb.appendChild(b); }
tc.appendChild(tb); toast.appendChild(tc); grid.appendChild(toast);

// Buttons
const btn = comp("Button / Accent", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "accent"});
btn.appendChild(txt("Сохранить откат", {style: "Semi Bold", color: "on-accent"})); grid.appendChild(btn);
const btn2 = comp("Button / Default", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"});
btn2.appendChild(txt("Выбрать…")); grid.appendChild(btn2);
const btn3 = comp("Button / Record", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "rec"});
btn3.appendChild(txt("●  Начать запись", {style: "Semi Bold", color: "on-accent"})); grid.appendChild(btn3);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
