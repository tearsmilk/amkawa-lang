package ruruka.suka.rurukasuka.ui;

import ruruka.suka.rurukasuka.Currency;
import ruruka.suka.rurukasuka.account.RurukaAccount;
import ruruka.suka.rurukasuka.cosmetic.Cosmetic;
import ruruka.suka.rurukasuka.cosmetic.CosmeticCategory;
import ruruka.suka.rurukasuka.cosmetic.CosmeticRegistry;
import ruruka.suka.rurukasuka.net.SiteApi;
import ruruka.suka.rurukasuka.render.BakedCosmetic;
import ruruka.suka.rurukasuka.render.CosmeticManager;
import ruruka.suka.rurukasuka.render.gui.CosmeticGuiRenderState;
import ruruka.suka.rurukasuka.render.gui.PlayerCosmeticGuiRenderState;
import ruruka.suka.rurukasuka.render.SkinLoader;
import ruruka.suka.rurukasuka.mixin.GuiGraphicsAccessor;
import net.minecraft.resources.Identifier;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.client.model.player.PlayerModel;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.world.entity.player.PlayerModelType;
import net.minecraft.world.entity.player.PlayerSkin;

import java.util.ArrayList;
import java.util.List;

/**
 * Гардероб rurukaSuka в стиле инвентаря Minecraft (как на сайте):
 * вкладки категорий сверху как в креативе, серое окно, косметика в слотах с прокруткой,
 * справа — игрок в чёрной рамке с примеркой, подсказка предмета и кнопка покупки.
 * Сообщения — строкой чата под окном.
 */
public class WardrobeScreen extends Screen {
    private final Screen parent;
    private CosmeticCategory category = CosmeticCategory.HATS;
    private Cosmetic selected = null;

    // ── раскладка (в пикселях интерфейса) ──
    private static final int PAD = 7, GAP = 5, SB_W = 12, THUMB_H = 15;
    // размеры вкладок и кнопок зависят от размера окна (большое окно — крупнее)
    private int tabW = 26, tabH = 24, iconPx = 1, btnH = 20;
    private int winX, winY, winW, winH, tabsY, chatY;
    private int gX0, gX1, gY0, gY1, sbX1, sbX2;
    private int cols = 3, cellS = 48, cellH = 59, gapX = 5, gapY = 5, rowsVisible = 1, scrollRow = 0;
    private int pvX1, pvX2;
    private int mpX1, mpY1, mpX2, mpY2;          // рамка игрока
    private int tipX1, tipY1, tipX2, tipY2;      // подсказка предмета
    private int vbX1, vbY1, vbX2, vbY2;          // кнопка цвета
    private int[] stars = new int[0];

    private static final float GUI_ROT_X = -4f, GUI_ROT_Y = 25f, GUI_PIVOT_Y = 0.3f;
    private static final float GUI_SCALE_CARD = 0.34f;

    // цвета строки статуса (как цвета чата Minecraft)
    private static final int C_INFO = McGui.WHITE, C_OK = McGui.MC_GREEN, C_ERR = McGui.MC_RED;

    private McButton actionBtn;
    private PlayerModel wideModel, slimModel;
    private float previewRotX = -5f, previewRotY = 30f;
    private String status = "";
    private int statusColor = C_INFO;
    private volatile boolean busy = false;
    private volatile boolean fetching = false;

    // наведение — считается при отрисовке кадра
    private Cosmetic hoverItem = null;
    private CosmeticCategory hoverTab = null;

    public WardrobeScreen(Screen parent) {
        super(Component.translatable("rurukasuka.wardrobe.title"));
        this.parent = parent;
        refresh();
    }

    @Override
    protected void init() {
        // окно занимает почти весь экран: отступ ~12px, но не больше 760×440
        winW = clamp(width - 24, 300, 760);
        boolean big = winW >= 600;
        tabW = big ? 34 : 26;
        tabH = big ? 30 : 24;
        iconPx = big ? 2 : 1;
        btnH = big ? 24 : 20;
        winH = clamp(height - 24 - tabH - 16, 176, 440);
        winX = (width - winW) / 2;
        int top = Math.max(4, (height - (tabH - 3 + winH + 16)) / 2);
        tabsY = top;
        winY = top + tabH - 3;
        chatY = winY + winH + 4;

        int cy0 = winY + 20, cy1 = winY + winH - PAD;

        // правая колонка: рамка игрока, подсказка, кнопка цвета, кнопка действия
        int pvW = clamp((int) (winW * 0.34f), 118, 250);
        pvX2 = winX + winW - PAD;
        pvX1 = pvX2 - pvW;
        int actY = cy1 - btnH;
        vbX1 = pvX1; vbX2 = pvX2; vbY2 = actY - 4; vbY1 = vbY2 - (big ? 20 : 16);
        tipX1 = pvX1; tipX2 = pvX2; tipY2 = vbY1 - 4; tipY1 = tipY2 - (big ? 34 : 30);
        mpX1 = pvX1; mpX2 = pvX2; mpY1 = cy0; mpY2 = tipY1 - 4;

        // сетка слотов + полоса прокрутки
        sbX2 = pvX1 - 6; sbX1 = sbX2 - SB_W;
        gX0 = winX + PAD; gX1 = sbX1 - 4;
        gY0 = cy0 + 3; gY1 = cy1;
        int gW = gX1 - gX0, gH = gY1 - gY0;
        // слот около 56px; колонок — сколько влезает по ширине
        int target = clamp(winW / 9, 52, 80);   // желаемый размер слота растёт вместе с окном
        cols = Math.max(2, (gW + GAP) / (target + GAP));
        cellS = (gW - (cols - 1) * GAP) / cols;
        // число рядов — ближайшее целое под высоту (минимум 2); если ряды не влезают — слоты меньше
        int rows = Math.max(2, Math.round((gH + GAP) / (float) (cellS + 12 + GAP)));
        int byH = (gH - (rows - 1) * GAP) / rows - 12;
        if (byH < cellS) {
            cellS = Math.max(36, byH);
            cols = Math.max(2, (gW + GAP) / (cellS + GAP));
        }
        cellH = cellS + 12;
        rowsVisible = Math.max(1, Math.min(rows, (gH + GAP) / (cellH + GAP)));
        // остаток ширины и высоты — в промежутки, чтобы сетка заполняла область целиком
        gapX = cols > 1 ? Math.max(GAP, (gW - cols * cellS) / (cols - 1)) : GAP;
        gapY = rowsVisible > 1 ? Math.max(GAP, (gH - rowsVisible * cellH) / (rowsVisible - 1)) : GAP;
        // ряды разъехались слишком широко — лучше на колонку меньше, но слоты крупнее
        if (rowsVisible > 1 && cols > 2 && gapY > cellH / 4) {
            int bigS = Math.min(byH, (gW - (cols - 2) * GAP) / (cols - 1));
            if (bigS > cellS) {
                cols -= 1;
                cellS = bigS;
                cellH = cellS + 12;
                rowsVisible = Math.max(1, Math.min(rows, (gH + GAP) / (cellH + GAP)));
                gapX = Math.max(GAP, (gW - cols * cellS) / (cols - 1));
                gapY = rowsVisible > 1 ? Math.max(GAP, (gH - rowsVisible * cellH) / (rowsVisible - 1)) : GAP;
            }
        }
        clampScroll();

        // звёзды на фоне — как на сайте
        stars = McGui.stars(width, height);

        // модели игрока (wide/slim) — печём один раз
        var models = Minecraft.getInstance().getEntityModels();
        wideModel = new PlayerModel(models.bakeLayer(ModelLayers.PLAYER), false);
        slimModel = new PlayerModel(models.bakeLayer(ModelLayers.PLAYER_SLIM), true);

        actionBtn = new McButton(pvX1, actY, pvW, btnH,
                Component.translatable("rurukasuka.wardrobe.buy"), b -> onBuyOrEquip()).cherry();
        addRenderableWidget(actionBtn);

        int backW = 56;
        addRenderableWidget(new McButton(winX + winW - backW, tabsY + 2, backW, tabH - 6,
                Component.translatable("rurukasuka.wardrobe.back"), b -> onClose()));
        updateActionLabel();
    }

    private static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    private String catName(CosmeticCategory c) {
        String s = Component.translatable(c.translationKey).getString();
        if (s == null || s.isEmpty()) return s;
        return Character.toUpperCase(s.charAt(0)) + s.substring(1).toLowerCase();
    }

    private List<Cosmetic> items() { return CosmeticRegistry.byCategory(category); }

    private int maxScroll() {
        int rows = (items().size() + cols - 1) / cols;
        return Math.max(0, rows - rowsVisible);
    }

    private void clampScroll() { scrollRow = clamp(scrollRow, 0, maxScroll()); }

    // ── данные (логика прежняя) ──
    private void refresh() {
        if (fetching) return;
        fetching = true;
        if (!CosmeticRegistry.isLoaded()) setStatus("Загружаю каталог…", C_INFO);
        new Thread(() -> {
            try {
                List<Cosmetic> items = SiteApi.cosmetics().stream()
                        .map(it -> new Cosmetic(it.id(), it.name(),
                                CosmeticCategory.fromApi(it.category()), it.price(),
                                it.scale(), it.offX(), it.offY(), it.offZ(), it.variants()))
                        .toList();
                SiteApi.Session me = null;
                if (RurukaAccount.LOCAL.isLoggedIn() && RurukaAccount.LOCAL.token() != null) {
                    try { me = SiteApi.me(RurukaAccount.LOCAL.token()); } catch (Exception ignored) {}
                }
                final SiteApi.Session meF = me;
                Minecraft.getInstance().execute(() -> {
                    CosmeticRegistry.load(items);
                    if (meF != null) RurukaAccount.LOCAL.applyMe(meF.balance(), meF.nick(), meF.owned(), meF.equipped(), meF.variants());
                    fetching = false;
                    setStatus("", C_INFO);
                    if (this.minecraft != null) this.rebuildWidgets();
                });
            } catch (Exception e) {
                String m = e.getMessage() == null ? "Каталог недоступен" : e.getMessage();
                Minecraft.getInstance().execute(() -> { fetching = false; setStatus(m, C_ERR); });
            }
        }, "RurukaSuka-catalog").start();
    }

    private void onBuyOrEquip() {
        if (selected == null) return;
        RurukaAccount acc = RurukaAccount.LOCAL;
        if (!acc.isLoggedIn()) { setStatus("Сначала войди в аккаунт в главном меню", C_ERR); return; }
        if (busy) return;
        final int id = selected.id();
        if (acc.owns(id)) {
            final boolean equip = !acc.isEquipped(id);
            busy = true;
            updateActionLabel();
            setStatus(equip ? "Надеваю…" : "Снимаю…", C_INFO);
            new Thread(() -> {
                try {
                    var eq = SiteApi.equip(acc.token(), id, equip);
                    Minecraft.getInstance().execute(() -> {
                        acc.applyEquip(eq); busy = false;
                        setStatus(equip ? "Надето" : "Снято", C_OK);
                        updateActionLabel();
                    });
                } catch (Exception e) {
                    String m = e.getMessage() == null ? "Не получилось, попробуй ещё раз" : e.getMessage();
                    Minecraft.getInstance().execute(() -> { busy = false; setStatus(m, C_ERR); updateActionLabel(); });
                }
            }, "RurukaSuka-equip").start();
            return;
        }
        busy = true;
        updateActionLabel();
        setStatus("Покупаю…", C_INFO);
        new Thread(() -> {
            try {
                SiteApi.PurchaseResult r = SiteApi.purchase(acc.token(), id);
                Minecraft.getInstance().execute(() -> {
                    acc.applyPurchase(r.balance(), r.owned());
                    busy = false;
                    setStatus("Куплено! Теперь можно надеть", C_OK);
                    updateActionLabel();
                });
            } catch (Exception e) {
                String m = e.getMessage() == null ? "Не получилось, попробуй ещё раз" : e.getMessage();
                Minecraft.getInstance().execute(() -> { busy = false; setStatus(m, C_ERR); updateActionLabel(); });
            }
        }, "RurukaSuka-purchase").start();
    }

    private void updateActionLabel() {
        if (actionBtn == null) return;
        RurukaAccount acc = RurukaAccount.LOCAL;
        if (selected == null) {
            actionBtn.setMessage(Component.translatable("rurukasuka.wardrobe.pick"));
        } else if (!acc.owns(selected.id())) {
            actionBtn.setMessage(selected.price() > 0
                    ? Component.translatable("rurukasuka.wardrobe.buy_for", Currency.format(selected.price()))
                    : Component.translatable("rurukasuka.wardrobe.buy_free"));
        } else {
            actionBtn.setMessage(Component.translatable(acc.isEquipped(selected.id())
                    ? "rurukasuka.wardrobe.unequip" : "rurukasuka.wardrobe.equip"));
        }
        actionBtn.active = selected != null && !busy;
    }

    private String variantName(Cosmetic c) {
        int vid = RurukaAccount.LOCAL.variantOf(c.id());
        if (vid == 0) return "базовый";
        for (Cosmetic.Variant v : c.variants()) if (v.id() == vid) return v.name();
        return "базовый";
    }

    private void cycleVariant() {
        if (selected == null) return;
        RurukaAccount acc = RurukaAccount.LOCAL;
        var vs = selected.variants();
        if (vs.isEmpty()) return;
        int cur = acc.variantOf(selected.id());
        int pos = 0;
        if (cur > 0) for (int i = 0; i < vs.size(); i++) if (vs.get(i).id() == cur) { pos = i + 1; break; }
        int next = (pos + 1) % (vs.size() + 1);
        final int nextVid = next == 0 ? 0 : vs.get(next - 1).id();
        acc.setVariantLocal(selected.id(), nextVid);
        if (!acc.isLoggedIn()) return;
        final int cid = selected.id();
        new Thread(() -> {
            try {
                var map = SiteApi.setVariant(acc.token(), cid, nextVid);
                Minecraft.getInstance().execute(() -> acc.applyVariants(map));
            } catch (Exception ignored) {}
        }, "RurukaSuka-variant-set").start();
    }

    private void select(Cosmetic c) {
        selected = c;
        setStatus("", C_INFO);
        updateActionLabel();
        // прокрутить так, чтобы выбранная вещь была видна
        int idx = items().indexOf(c);
        if (idx >= 0) {
            int row = idx / cols;
            if (row < scrollRow) scrollRow = row;
            if (row >= scrollRow + rowsVisible) scrollRow = row - rowsVisible + 1;
            clampScroll();
        }
    }

    private void selectDelta(int d) {
        List<Cosmetic> items = items();
        if (items.isEmpty()) return;
        int idx = selected == null ? -1 : items.indexOf(selected);
        if (idx < 0) idx = d > 0 ? -1 : 0;
        idx = (idx + d + items.size()) % items.size();
        select(items.get(idx));
    }

    private void setCategory(CosmeticCategory c) {
        category = c; selected = null; scrollRow = 0;
        updateActionLabel();
    }

    private void setStatus(String s, int color) { this.status = s; this.statusColor = color; }

    // ── отрисовка ──
    @Override
    public void render(GuiGraphics g, int mouseX, int mouseY, float delta) {
        hoverItem = null;
        hoverTab = null;

        renderSky(g);

        // невыбранные вкладки — за окном
        CosmeticCategory[] cats = CosmeticCategory.values();
        for (int i = 0; i < cats.length; i++) {
            if (cats[i] == category) continue;
            int tx = winX + i * (tabW + 1);
            McGui.tab(g, tx, tabsY + 2, tx + tabW, winY + 1, false);
        }
        McGui.panel(g, winX, winY, winX + winW, winY + winH);
        // выбранная вкладка — поверх окна, сливается с ним
        int selIdx = category.ordinal();
        int stx = winX + selIdx * (tabW + 1);
        McGui.tab(g, stx, tabsY, stx + tabW, winY, true);
        for (int i = 0; i < cats.length; i++) {
            int tx = winX + i * (tabW + 1);
            int ty = cats[i] == category ? tabsY : tabsY + 2;
            int isz = PixelIcons.SIZE * iconPx;
            PixelIcons.category(g, cats[i], tx + (tabW - isz) / 2, ty + (tabH - 2 - isz) / 2 + 1, iconPx);
            if (mouseX >= tx && mouseX < tx + tabW && mouseY >= tabsY && mouseY < winY) hoverTab = cats[i];
        }

        renderHeader(g);
        renderGrid(g, mouseX, mouseY);
        renderScrollbar(g, mouseX, mouseY);
        renderPreview(g, mouseX, mouseY);
        renderChat(g);

        super.render(g, mouseX, mouseY, delta);

        // подпись вкладки при наведении — в последнюю очередь, поверх всего
        if (hoverTab != null && hoverTab != category) {
            String t = catName(hoverTab);
            int w = font.width(t) + 8;
            int x = Math.min(mouseX + 10, width - w - 2), y = Math.max(2, mouseY - 18);
            McGui.tooltip(g, x, y, x + w, y + 14);
            g.drawString(font, Component.literal(t), x + 4, y + 3, McGui.WHITE);
        }
    }

    private void renderSky(GuiGraphics g) { McGui.sky(g, width, height, stars); }

    private void renderHeader(GuiGraphics g) {
        List<Cosmetic> items = items();
        long owned = items.stream().filter(c -> RurukaAccount.LOCAL.owns(c.id())).count();
        String title = catName(category);
        McGui.ink(g, font, title, winX + PAD + 1, winY + 7, McGui.INK);
        if (!items.isEmpty()) {
            McGui.ink(g, font, "куплено " + owned + " из " + items.size(),
                    winX + PAD + 1 + font.width(title) + 6, winY + 7, McGui.INK_SOFT);
        }
        // баланс справа: монетка + число
        String coins = RurukaAccount.LOCAL.isLoggedIn() ? Currency.format(RurukaAccount.LOCAL.coins()) : "вход не выполнен";
        int cw = font.width(coins);
        int bx = winX + winW - PAD - 1 - cw;
        McGui.ink(g, font, coins, bx, winY + 7, McGui.INK);
        if (RurukaAccount.LOCAL.isLoggedIn()) PixelIcons.coin(g, bx - PixelIcons.SIZE - 2, winY + 5, 1);
    }

    private void renderGrid(GuiGraphics g, int mouseX, int mouseY) {
        List<Cosmetic> items = items();
        if (items.isEmpty()) {
            String key = fetching ? "rurukasuka.wardrobe.loading" : "rurukasuka.wardrobe.empty";
            McGui.inkCentered(g, font, Component.translatable(key).getString(), (gX0 + gX1) / 2, gY0 + 30, McGui.INK_SOFT);
            return;
        }
        int first = scrollRow * cols;
        int last = Math.min(items.size(), first + rowsVisible * cols);
        for (int i = first; i < last; i++) {
            Cosmetic c = items.get(i);
            int col = (i - first) % cols, row = (i - first) / cols;
            int cx = gX0 + col * (cellS + gapX);
            int cy = gY0 + row * (cellH + gapY);
            boolean hover = mouseX >= cx && mouseX < cx + cellS && mouseY >= cy && mouseY < cy + cellH;
            if (hover) hoverItem = c;
            boolean sel = c == selected;
            boolean owned = RurukaAccount.LOCAL.owns(c.id());
            boolean eq = owned && RurukaAccount.LOCAL.isEquipped(c.id());

            if (sel) McGui.selection(g, cx, cy, cx + cellS, cy + cellS);
            McGui.slot(g, cx, cy, cx + cellS, cy + cellS, hover);

            // 3D-модель в слоте
            int ax = cx + 1, ay = cy + 1, aw = cellS - 2, ah = cellS - 2;
            CosmeticManager.ensure(c.id());
            BakedCosmetic baked = CosmeticManager.get(c.id());
            if (baked != null) {
                Identifier tex = CosmeticManager.textureFor(c.id());
                if (tex != null) {
                    String key = c.id() + "_" + RurukaAccount.LOCAL.variantOf(c.id());
                    ((GuiGraphicsAccessor) g).rurukasuka$guiRenderState().submitPicturesInPictureState(
                            new CosmeticGuiRenderState(key, baked.model(), tex,
                                    GUI_ROT_X, GUI_ROT_Y, GUI_PIVOT_Y, ax, ay, ax + aw, ay + ah, ah * GUI_SCALE_CARD, null));
                }
            }

            // подпись под слотом; квадратик слева: зелёный — надето, серый контур — куплено
            int ny = cy + cellS + 3;
            int markW = owned ? 7 : 0;
            String name = McGui.fit(font, c.name(), cellS - markW);
            int nx = cx + (cellS - (font.width(name) + markW)) / 2;
            if (eq) {
                g.fill(nx, ny + 1, nx + 5, ny + 6, 0xFF2C7A37);
                g.fill(nx, ny + 1, nx + 4, ny + 5, 0xFF3FA34D);
            } else if (owned) {
                McGui.outline(g, nx, ny + 1, nx + 5, ny + 6, McGui.INK_SOFT);
            }
            McGui.ink(g, font, name, nx + markW, ny, sel ? McGui.INK : McGui.INK_SOFT);
        }
    }

    /** Полоса прокрутки как в креативном инвентаре. */
    private void renderScrollbar(GuiGraphics g, int mouseX, int mouseY) {
        McGui.slot(g, sbX1, gY0, sbX2, gY1, false);
        g.fill(sbX1 + 1, gY0 + 1, sbX2 - 1, gY1 - 1, 0xFF6B6B6B);
        int max = maxScroll();
        int travel = (gY1 - gY0 - 2) - THUMB_H;
        int ty = gY0 + 1 + (max == 0 ? 0 : Math.round(travel * (scrollRow / (float) max)));
        boolean hover = mouseX >= sbX1 && mouseX < sbX2 && mouseY >= ty && mouseY < ty + THUMB_H;
        McGui.button(g, sbX1 + 1, ty, sbX2 - 1, ty + THUMB_H, false, hover && max > 0, max > 0);
    }

    private void addPiece(List<PlayerCosmeticGuiRenderState.Piece> list, int id) {
        CosmeticManager.ensure(id);
        BakedCosmetic baked = CosmeticManager.get(id);
        if (baked == null) return;
        Identifier tex = CosmeticManager.textureFor(id);
        if (tex == null) return;
        float[] tf = CosmeticManager.transformOf(id);
        list.add(new PlayerCosmeticGuiRenderState.Piece(baked.model(), tex, baked.category(),
                tf[0], tf[1], tf[2], tf[3]));
    }

    private void renderPlayer(GuiGraphics g) {
        var pieces = new ArrayList<PlayerCosmeticGuiRenderState.Piece>();
        for (int id : RurukaAccount.LOCAL.equippedIds()) addPiece(pieces, id);
        // примерка выбранной, если не надета
        if (selected != null && !RurukaAccount.LOCAL.isEquipped(selected.id())) addPiece(pieces, selected.id());

        PlayerSkin skin = SkinLoader.currentOrDefault();
        PlayerModel pm = skin.model() == PlayerModelType.SLIM ? slimModel : wideModel;
        if (pm == null) return;
        int x1 = mpX1 + 1, y1 = mpY1 + 1, x2 = mpX2 - 1, y2 = mpY2 - 1;
        float scale = 0.82f * (y2 - y1) / 2.125f;
        ((GuiGraphicsAccessor) g).rurukasuka$guiRenderState().submitPicturesInPictureState(
                new PlayerCosmeticGuiRenderState("player_preview", pm, skin.body().texturePath(),
                        previewRotX, previewRotY, x1, y1, x2, y2, scale, pieces, null));
    }

    private void renderPreview(GuiGraphics g, int mouseX, int mouseY) {
        // игрок в чёрной рамке — как в инвентаре
        McGui.frame(g, mpX1, mpY1, mpX2, mpY2);
        renderPlayer(g);

        // подсказка предмета: наведённый слот, иначе выбранный
        McGui.tooltip(g, tipX1, tipY1, tipX2, tipY2);
        Cosmetic info = hoverItem != null ? hoverItem : selected;
        int inner = tipX2 - tipX1 - 28;
        int cx = (tipX1 + tipX2) / 2;
        int midY = (tipY1 + tipY2) / 2;           // строки центрируются по высоте подсказки
        int line1 = midY - 10, line2 = midY + 2;
        if (info == null) {
            String hint = Component.translatable("rurukasuka.wardrobe.pick").getString();
            g.drawCenteredString(font, Component.literal(McGui.fit(font, hint, inner)), cx, midY - 4, McGui.MC_GRAY);
        } else {
            g.drawCenteredString(font, Component.literal(McGui.fit(font, info.name(), inner)), cx, line1, McGui.WHITE);
            RurukaAccount acc = RurukaAccount.LOCAL;
            if (acc.owns(info.id())) {
                boolean eq = acc.isEquipped(info.id());
                g.drawCenteredString(font, Component.literal(eq ? "Надето" : "Куплено"), cx, line2,
                        eq ? McGui.MC_GREEN : McGui.MC_GRAY);
            } else if (info.price() > 0) {
                String price = Currency.format(info.price());
                int pw = font.width(price) + PixelIcons.SIZE + 3;
                int px = cx - pw / 2;
                PixelIcons.coin(g, px, line2 - 2, 1);
                g.drawString(font, Component.literal(price), px + PixelIcons.SIZE + 3, line2, McGui.MC_GOLD);
            } else {
                g.drawCenteredString(font, Component.literal("Бесплатно"), cx, line2, McGui.MC_GREEN);
            }
        }
        // стрелки листания выбранной вещи
        if (!items().isEmpty()) {
            boolean hl = mouseX >= tipX1 && mouseX < tipX1 + 14 && mouseY >= tipY1 && mouseY < tipY2;
            boolean hr = mouseX >= tipX2 - 14 && mouseX < tipX2 && mouseY >= tipY1 && mouseY < tipY2;
            g.drawString(font, Component.literal("<"), tipX1 + 5, midY - 4, hl ? McGui.WHITE : McGui.MC_GRAY);
            g.drawString(font, Component.literal(">"), tipX2 - 9, midY - 4, hr ? McGui.WHITE : McGui.MC_GRAY);
        }

        // кнопка цвета — только если вещь куплена и у неё есть варианты
        if (selected != null && RurukaAccount.LOCAL.owns(selected.id()) && !selected.variants().isEmpty()) {
            boolean h = mouseX >= vbX1 && mouseX < vbX2 && mouseY >= vbY1 && mouseY < vbY2;
            McGui.button(g, vbX1, vbY1, vbX2, vbY2, false, h, true);
            String label = McGui.fit(font, "◄ Цвет: " + variantName(selected) + " ►", vbX2 - vbX1 - 8);
            g.drawCenteredString(font, Component.literal(label), (vbX1 + vbX2) / 2, (vbY1 + vbY2) / 2 - 5, McGui.WHITE);
        }
    }

    /** Сообщение строкой чата под окном: «<rurukaSuka> Куплено!» — как на сайте. */
    private void renderChat(GuiGraphics g) { McGui.chat(g, font, winX, chatY, winW, status, statusColor); }

    // ── ввод ──
    @Override
    public boolean mouseClicked(MouseButtonEvent event, boolean doubleClick) {
        double mx = event.x(), my = event.y();

        // вкладки категорий
        CosmeticCategory[] cats = CosmeticCategory.values();
        if (my >= tabsY && my < winY) {
            for (int i = 0; i < cats.length; i++) {
                int tx = winX + i * (tabW + 1);
                if (mx >= tx && mx < tx + tabW) { setCategory(cats[i]); return true; }
            }
        }

        // стрелки в подсказке
        if (my >= tipY1 && my < tipY2) {
            if (mx >= tipX1 && mx < tipX1 + 14) { selectDelta(-1); return true; }
            if (mx >= tipX2 - 14 && mx < tipX2) { selectDelta(1); return true; }
        }

        // кнопка цвета
        if (selected != null && RurukaAccount.LOCAL.owns(selected.id()) && !selected.variants().isEmpty()
                && mx >= vbX1 && mx < vbX2 && my >= vbY1 && my < vbY2) {
            cycleVariant();
            return true;
        }

        // полоса прокрутки: клик выше/ниже ползунка листает страницу
        if (mx >= sbX1 && mx < sbX2 && my >= gY0 && my < gY1) {
            int max = maxScroll();
            if (max > 0) {
                int travel = (gY1 - gY0 - 2) - THUMB_H;
                int ty = gY0 + 1 + Math.round(travel * (scrollRow / (float) max));
                if (my < ty) scrollRow -= rowsVisible;
                else if (my >= ty + THUMB_H) scrollRow += rowsVisible;
                clampScroll();
            }
            return true;
        }

        // слоты
        List<Cosmetic> items = items();
        int first = scrollRow * cols;
        int last = Math.min(items.size(), first + rowsVisible * cols);
        for (int i = first; i < last; i++) {
            int col = (i - first) % cols, row = (i - first) / cols;
            int cx = gX0 + col * (cellS + gapX);
            int cy = gY0 + row * (cellH + gapY);
            if (mx >= cx && mx < cx + cellS && my >= cy && my < cy + cellH) {
                select(items.get(i));
                return true;
            }
        }
        return super.mouseClicked(event, doubleClick);
    }

    @Override
    public boolean mouseDragged(MouseButtonEvent event, double dragX, double dragY) {
        double mx = event.x(), my = event.y();
        // перетаскивание ползунка
        if (mx >= sbX1 - 6 && mx < sbX2 + 6 && my >= gY0 - 6 && my < gY1 + 6 && maxScroll() > 0) {
            int travel = (gY1 - gY0 - 2) - THUMB_H;
            float t = (float) ((my - gY0 - 1 - THUMB_H / 2.0) / Math.max(1, travel));
            scrollRow = Math.round(Math.max(0f, Math.min(1f, t)) * maxScroll());
            clampScroll();
            return true;
        }
        // вращение игрока
        if (mx >= mpX1 && mx <= mpX2 && my >= mpY1 && my <= mpY2) {
            previewRotY += (float) (dragX * 0.6);
            previewRotX = Math.max(-45f, Math.min(45f, previewRotX - (float) (dragY * 0.6)));
            return true;
        }
        return super.mouseDragged(event, dragX, dragY);
    }

    /**
     * Колесо мыши листает сетку. Без @Override намеренно: если в этой версии игры
     * сигнатура другая, метод просто не вызовется, а листать можно полосой прокрутки.
     */
    public boolean mouseScrolled(double mouseX, double mouseY, double scrollX, double scrollY) {
        if (mouseX >= gX0 && mouseX < sbX2 && mouseY >= gY0 && mouseY < gY1) {
            scrollRow -= (int) Math.signum(scrollY);
            clampScroll();
            return true;
        }
        return false;
    }

    @Override
    public void onClose() {
        if (minecraft != null) minecraft.setScreen(parent);
    }
}
