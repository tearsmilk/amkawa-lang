// Milkys Hub — UI Kit page (Figma Plugin API, run via use_figma). Re-runnable: rebuilds the page.
const page = figma.currentPage;
page.name = "UI Kit";
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Milkys Hub")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const MONO = ["JetBrains Mono", "Roboto Mono", "Source Code Pro", "IBM Plex Mono"].find(f => has(f, "Regular")) || "Inter";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: MONO, style: "Regular"}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
const T = {
  "bg": ["#FAF9F5", "#262624"], "sidebar": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"],
  "border": ["#E3DFD3", "#3E3D39"], "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"],
  "accent": ["#D97757", "#D97757"], "accent-hover": ["#C6613F", "#E08A6D"], "on-accent": ["#FFFFFF", "#FFFFFF"],
  "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "editor": ["#FFFFFF", "#262624"], "code-bg": ["#F3F1EA", "#1F1E1D"], "code-inline": ["#B5532F", "#E8A487"],
  "tag-bg": ["#F6E7DF", "#45342C"], "callout-bg": ["#F6F4EE", "#2B2A28"],
  "syntax-keyword": ["#008000", "#FF7B72"], "syntax-string": ["#BA2121", "#A5D6FF"], "syntax-func": ["#0000FF", "#D2A8FF"],
  "info": ["#4A7BD0", "#6E9BE6"], "success": ["#3E8E63", "#7BB487"], "warning": ["#C27A2C", "#E59866"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Milkys Hub — " + modeName);
  col.renameMode(col.modes[0].modeId, modeName);
  colIds[modeName] = col.id;
  for (const [name, vals] of Object.entries(T)) {
    const v = figma.variables.createVariable("color/" + name, col, "COLOR");
    v.setValueForMode(col.modes[0].modeId, hex(vals[mi]));
    v.scopes = name.startsWith("syntax") || ["text", "muted", "on-accent", "code-inline"].includes(name)
      ? ["TEXT_FILL", "SHAPE_FILL"] : ["FRAME_FILL", "SHAPE_FILL", "STROKE_COLOR", "TEXT_FILL"];
    V[modeName][name] = v;
  }
}
let MODE = "Light";
const fill = name => figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][name]);

function txt(chars, o = {}) {
  const t = figma.createText();
  t.fontName = {family: o.family || SANS, style: o.style || "Regular"};
  t.fontSize = o.size || 14;
  t.characters = chars;
  t.fills = [fill(o.color || "text")];
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
  const c = figma.createComponent();
  c.name = name;
  c.layoutMode = dir;
  c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "AUTO";
  c.itemSpacing = o.gap ?? 8;
  const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad ?? 0, o.pad ?? 0, o.pad ?? 0, o.pad ?? 0];
  c.paddingTop = t; c.paddingRight = r; c.paddingBottom = b; c.paddingLeft = l;
  c.fills = o.fill ? [fill(o.fill)] : [];
  if (o.radius) c.cornerRadius = o.radius;
  if (o.stroke) { c.strokes = [fill(o.stroke)]; c.strokeWeight = 1; }
  c.counterAxisAlignItems = o.align || "CENTER";
  return c;
}
function variants(comps, parent, props = {}) {
  const set = figma.combineAsVariants(comps, parent);
  set.layoutMode = "HORIZONTAL";
  set.primaryAxisSizingMode = "AUTO"; set.counterAxisSizingMode = "AUTO";
  set.itemSpacing = 16; set.paddingTop = set.paddingBottom = set.paddingLeft = set.paddingRight = 20;
  set.counterAxisAlignItems = "CENTER";
  set.fills = [fill("bg")]; set.cornerRadius = 12;
  set.strokes = [fill("border")]; set.dashPattern = [4, 4];
  for (const [prop, def] of Object.entries(props)) {
    const key = set.addComponentProperty(prop, "TEXT", def);
    for (const v of set.children) {
      const t = v.findOne(n => n.type === "TEXT" && n.name === prop);
      if (t) t.componentPropertyReferences = {characters: key};
    }
  }
  return set;
}
function propText(component, textNode, prop, def) {
  textNode.componentPropertyReferences = {characters: component.addComponentProperty(prop, "TEXT", def)};
}

const root = al("VERTICAL", {name: "Milkys Hub — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.x = 0; root.y = 0;
root.resize(1600, 100);
root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("VERTICAL", {name: "Header", gap: 8});
head.appendChild(txt("✻ Milkys Hub — UI Kit", {family: SERIF, size: 44}));
head.appendChild(txt("Claude-style: тёплые поверхности, терракотовый акцент, serif-заголовки. Токены — коллекции «Milkys Hub — Light» и «Milkys Hub — Dark» с одинаковыми именами.", {size: 16, color: "muted"}));
root.appendChild(head);
function sectionFrame(title) {
  const s = al("VERTICAL", {name: title, gap: 16});
  s.appendChild(txt(title.toUpperCase(), {size: 12, style: "Semi Bold", color: "muted"}));
  root.appendChild(s); s.layoutSizingHorizontal = "FILL";
  return s;
}

// colors
const colors = sectionFrame("Colors");
for (const modeName of ["Light", "Dark"]) {
  MODE = modeName;
  const row = al("HORIZONTAL", {name: "Swatches / " + modeName, gap: 12, pad: 20, radius: 14, fill: "bg", stroke: "border"});
  row.layoutWrap = "WRAP"; row.counterAxisSpacing = 12;
  colors.appendChild(row); row.layoutSizingHorizontal = "FILL";
  for (const name of Object.keys(T)) {
    const sw = al("VERTICAL", {name, gap: 6});
    const chip = figma.createRectangle();
    chip.resize(120, 56); chip.cornerRadius = 10; chip.fills = [fill(name)]; chip.strokes = [fill("border")]; chip.strokeWeight = 1;
    sw.appendChild(chip);
    sw.appendChild(txt(name, {size: 11, style: "Medium"}));
    sw.appendChild(txt(T[name][modeName === "Light" ? 0 : 1], {size: 10, color: "muted"}));
    row.appendChild(sw);
  }
}
MODE = "Light";

// typography
const typo = sectionFrame("Typography");
const tbox = al("VERTICAL", {name: "Type ramp", gap: 14, pad: 24, radius: 14, fill: "card", stroke: "border"});
typo.appendChild(tbox); tbox.layoutSizingHorizontal = "FILL";
for (const [label, o] of [["Title / Serif 30", {family: SERIF, size: 30}], ["Heading / Serif 22", {family: SERIF, size: 22}],
  ["Card title / Serif 18", {family: SERIF, size: 18}], ["Body / Inter 14", {size: 14}], ["Body strong / Inter Semi Bold 14", {size: 14, style: "Semi Bold"}],
  ["Caption / Inter 12 muted", {size: 12, color: "muted"}], ["SECTION / Inter Semi Bold 11", {size: 11, style: "Semi Bold", color: "muted"}],
  ["code / Mono 12", {family: MONO, size: 12, color: "code-inline"}]]) tbox.appendChild(txt(label, o));

// components
const compsSec = sectionFrame("Components");
const grid = al("HORIZONTAL", {name: "Components grid", gap: 24});
grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
compsSec.appendChild(grid); grid.layoutSizingHorizontal = "FILL";
const ids = {};

const btnStyles = {Primary: ["accent", "on-accent", null, 12, [12, 26, 12, 26], 15], Accent: ["accent", "on-accent", null, 9, [7, 14, 7, 14], 13],
  Secondary: ["card", "text", "border", 9, [7, 14, 7, 14], 13], Ghost: [null, "muted", "border", 9, [7, 14, 7, 14], 13], Link: [null, "muted", null, 6, [4, 6, 4, 6], 13]};
const btns = Object.entries(btnStyles).map(([s, [bg, fg, st, r, pad, size]]) => {
  const c = comp("Style=" + s, "HORIZONTAL", {fill: bg, stroke: st, radius: r, pad});
  if (s === "Ghost") c.dashPattern = [4, 3];
  const t = txt(s === "Primary" ? "Новая заметка" : "Кнопка", {size, style: s === "Primary" || s === "Accent" ? "Semi Bold" : "Regular", color: fg});
  t.name = "Label"; c.appendChild(t); return c;
});
const btnSet = variants(btns, grid, {Label: "Кнопка"}); btnSet.name = "Button"; ids.button = btnSet.id;
btnSet.description = "Primary — главное действие, Accent — важное вторичное, Secondary/Ghost/Link — остальное.";

const inputs = ["Default", "Focus"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {fill: "input", stroke: s === "Focus" ? "accent" : "border", radius: 8, pad: [7, 10, 7, 10]});
  c.resize(240, c.height); c.primaryAxisSizingMode = "FIXED";
  const t = txt("Поиск  ⇧⌘F", {size: 13, color: "muted"}); t.name = "Placeholder"; c.appendChild(t); return c;
});
const inputSet = variants(inputs, grid, {Placeholder: "Поиск  ⇧⌘F"}); inputSet.name = "Input"; ids.input = inputSet.id;

const navs = ["Default", "Selected"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {fill: s === "Selected" ? "selected" : null, radius: 8, pad: [7, 10, 7, 10], gap: 10});
  c.resize(240, c.height); c.primaryAxisSizingMode = "FIXED";
  const i = txt("☰", {size: 13, color: "muted"}); i.name = "Icon"; c.appendChild(i);
  const t = txt("Ссылки", {size: 13}); t.name = "Label"; c.appendChild(t); return c;
});
const navSet = variants(navs, grid, {Label: "Ссылки", Icon: "☰"}); navSet.name = "Nav item"; ids.nav = navSet.id;

const trees = ["Default", "Selected"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {fill: s === "Selected" ? "selected" : null, radius: 6, pad: [4, 8, 4, 8], gap: 6});
  c.resize(240, c.height); c.primaryAxisSizingMode = "FIXED";
  const t = txt("Добро пожаловать", {size: 13}); t.name = "Label"; c.appendChild(t); return c;
});
const treeSet = variants(trees, grid, {Label: "Заметка"}); treeSet.name = "Tree item"; ids.tree = treeSet.id;

const tabs = ["Active", "Inactive"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [8, 14, 8, 14], gap: 10});
  if (s === "Active") { c.strokes = [fill("accent")]; c.strokeTopWeight = 0; c.strokeLeftWeight = 0; c.strokeRightWeight = 0; c.strokeBottomWeight = 2; }
  const t = txt("Проекты", {size: 13, color: s === "Active" ? "text" : "muted"}); t.name = "Label"; c.appendChild(t);
  c.appendChild(txt("×", {size: 14, color: "muted"})); return c;
});
const tabSet = variants(tabs, grid, {Label: "Заметка"}); tabSet.name = "Tab"; ids.tab = tabSet.id;

const seg = comp("Segmented / Mode", "HORIZONTAL", {gap: 0, radius: 8, stroke: "border", fill: "card"});
seg.clipsContent = true;
for (const [i, l] of ["Редактор", "Разделить", "Просмотр"].entries()) {
  const s = al("HORIZONTAL", {name: l, pad: [5, 12, 5, 12], fill: i === 1 ? "selected" : null});
  s.appendChild(txt(l, {size: 12})); seg.appendChild(s);
}
grid.appendChild(seg); ids.segmented = seg.id;

const tag = comp("Tag", "HORIZONTAL", {fill: "tag-bg", radius: 5, pad: [2, 6, 2, 6]});
const tagT = txt("#работа", {size: 13, color: "accent"}); tagT.name = "Label"; tag.appendChild(tagT);
grid.appendChild(tag); propText(tag, tagT, "Label", "#работа"); ids.tag = tag.id;

const tasks = ["Todo", "Done"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {gap: 8});
  const box = figma.createRectangle(); box.resize(14, 14); box.cornerRadius = 4;
  box.fills = s === "Done" ? [fill("accent")] : []; box.strokes = [fill(s === "Done" ? "accent" : "muted")]; box.strokeWeight = 1.2;
  c.appendChild(box);
  const t = txt(s === "Done" ? "открыть Milkys Hub" : "попробовать вставить код", {size: 14, color: s === "Done" ? "muted" : "text"});
  t.name = "Label"; c.appendChild(t); return c;
});
const taskSet = variants(tasks, grid, {Label: "Задача"}); taskSet.name = "Task"; ids.task = taskSet.id;

const code = comp("Code block", "VERTICAL", {fill: "code-bg", stroke: "border", radius: 10, pad: [8, 14, 12, 14], gap: 8, align: "MIN"});
code.resize(520, code.height); code.primaryAxisSizingMode = "AUTO"; code.counterAxisSizingMode = "FIXED";
const ch = al("HORIZONTAL", {name: "Header"});
const lang = txt("PYTHON", {size: 11, style: "Semi Bold", color: "muted"}); lang.name = "Language"; ch.appendChild(lang);
const spacer = figma.createFrame(); spacer.name = "Spacer"; spacer.fills = []; spacer.resize(10, 10); ch.appendChild(spacer); spacer.layoutGrow = 1;
ch.appendChild(txt("Копировать", {size: 11, color: "accent"}));
code.appendChild(ch); ch.layoutSizingHorizontal = "FILL";
for (const ln of [[["def ", "syntax-keyword"], ["hello", "syntax-func"], ["(name: str) -> str:", "text"]],
                  [["    return ", "syntax-keyword"], ['f"Привет, {name}!"', "syntax-string"]]]) {
  const row = al("HORIZONTAL", {name: "Line", gap: 0});
  for (const [s, c] of ln) row.appendChild(txt(s, {family: MONO, size: 12, color: c}));
  code.appendChild(row);
}
grid.appendChild(code); propText(code, lang, "Language", "PYTHON"); ids.code = code.id;
code.description = "Блок кода: язык определяется автоматически при вставке, кнопка «Копировать».";

const callouts = [["Tip", "success", "✦ Совет"], ["Note", "info", "✎ Заметка"], ["Warning", "warning", "! Внимание"]].map(([n, colr, title]) => {
  const c = comp("Type=" + n, "VERTICAL", {fill: "callout-bg", pad: [10, 14, 10, 14], gap: 4, align: "MIN"});
  c.strokes = [fill(colr)]; c.strokeTopWeight = 0; c.strokeRightWeight = 0; c.strokeBottomWeight = 0; c.strokeLeftWeight = 3;
  c.resize(300, c.height); c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "FIXED";
  c.appendChild(txt(title, {size: 13, style: "Semi Bold", color: colr}));
  const b = txt("Вставьте код — язык определится сам.", {size: 13}); b.name = "Body"; c.appendChild(b); return c;
});
const calloutSet = variants(callouts, grid, {Body: "Текст выноски"}); calloutSet.name = "Callout"; ids.callout = calloutSet.id;

const sec = comp("Section label", "HORIZONTAL", {});
const secT = txt("ЗАМЕТКИ", {size: 11, style: "Semi Bold", color: "muted"}); secT.name = "Label"; sec.appendChild(secT);
grid.appendChild(sec); propText(sec, secT, "Label", "ЗАМЕТКИ"); ids.section = sec.id;

const rows = ["Header", "Row"].map(s => {
  const c = comp("Kind=" + s, "HORIZONTAL", {pad: [8, 10, 8, 10], gap: 16, fill: s === "Header" ? "bg" : null});
  c.strokes = [fill("border")]; c.strokeTopWeight = 0; c.strokeLeftWeight = 0; c.strokeRightWeight = 0; c.strokeBottomWeight = 1;
  c.resize(640, c.height); c.primaryAxisSizingMode = "FIXED";
  const vals = s === "Header" ? ["НАЗВАНИЕ", "АДРЕС", "ТЕГИ", "ДОБАВЛЕНО"] : ["Claude", "https://claude.ai", "#ai", "14.10.2026"];
  const widths = [160, 240, 80, 100];
  vals.forEach((v, i) => {
    const t = txt(v, {size: s === "Header" ? 11 : 13, style: s === "Header" ? "Semi Bold" : "Regular", color: s === "Header" || i === 1 ? "muted" : "text"});
    t.name = "Col " + (i + 1); c.appendChild(t); t.textAutoResize = "HEIGHT"; t.resize(widths[i], t.height);
  });
  return c;
});
const rowSet = variants(rows, grid, {}); rowSet.name = "Table row"; ids.row = rowSet.id;

const card = comp("Card", "VERTICAL", {fill: "card", stroke: "border", radius: 14, pad: [18, 22, 20, 22], gap: 12, align: "MIN"});
card.resize(360, card.height); card.counterAxisSizingMode = "FIXED";
const ct = txt("Заголовок карточки", {family: SERIF, size: 18}); ct.name = "Title"; card.appendChild(ct);
card.appendChild(txt("Карточки группируют настройки и разделы.", {size: 13, color: "muted"}));
grid.appendChild(card); propText(card, ct, "Title", "Заголовок карточки"); ids.card = card.id;

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, fonts: {SERIF, MONO}, ids, variables: Object.keys(T).length * 2};
