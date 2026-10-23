package ruruka.suka.rurukasuka.ui;

import ruruka.suka.rurukasuka.Currency;
import ruruka.suka.rurukasuka.account.RurukaAccount;
import ruruka.suka.rurukasuka.account.SessionStore;
import ruruka.suka.rurukasuka.net.SiteApi;
import ruruka.suka.rurukasuka.render.BakedCosmetic;
import ruruka.suka.rurukasuka.render.CosmeticManager;
import ruruka.suka.rurukasuka.render.SkinLoader;
import ruruka.suka.rurukasuka.render.gui.PlayerCosmeticGuiRenderState;
import ruruka.suka.rurukasuka.mixin.GuiGraphicsAccessor;
import ruruka.suka.rurukasuka.RurukaSuka;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.client.model.geom.ModelLayers;
import net.minecraft.client.model.player.PlayerModel;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.world.entity.player.PlayerModelType;
import net.minecraft.world.entity.player.PlayerSkin;

import java.util.ArrayList;
import java.util.List;

/**
 * Аккаунт в стиле Minecraft (как гардероб и сайт).
 * Не вошёл — окно входа: почта, пароль, «Войти». Вошёл — игрок в чёрной рамке
 * с надетой косметикой, ник, номер, баланс и кнопки «Открыть гардероб» / «Выйти».
 */
public class AccountScreen extends Screen {
    private final Screen parent;
    private EditBox emailBox;
    private EditBox passBox;
    private String status = "";
    private int statusColor = McGui.WHITE;
    private volatile boolean busy = false;

    private static final int PAD = 7;
    private static final String NOTE = "Нет аккаунта? Создай его на сайте onii.ink и войди здесь с той же почтой.";
    private int winX, winY, winW, winH, chatY;
    private int fX1, fY1, fX2, fY2;                 // рамка игрока
    private int sX1, sX2, sY;                       // блок статистики
    private int[] stars = new int[0];
    private PlayerModel wideModel, slimModel;
    private float rotX = -5f, rotY = 30f;

    public AccountScreen(Screen parent) {
        super(Component.translatable("rurukasuka.account.title"));
        this.parent = parent;
        if (RurukaAccount.LOCAL.isLoggedIn() && RurukaAccount.LOCAL.token() != null) {
            final String tok = RurukaAccount.LOCAL.token();
            new Thread(() -> {
                try {
                    SiteApi.Session s = SiteApi.me(tok);
                    Minecraft.getInstance().execute(() -> {
                        RurukaAccount.LOCAL.applyMe(s.balance(), s.nick(), s.owned(), s.equipped(), s.variants());
                        if (this.minecraft != null) this.rebuildWidgets();
                    });
                } catch (Exception ignored) {}
            }, "RurukaSuka-me").start();
        }
    }

    private static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    @Override
    protected void init() {
        stars = McGui.stars(width, height);
        boolean in = RurukaAccount.LOCAL.isLoggedIn();
        winW = clamp(width - 24, 280, 400);
        // окно входа — по высоте содержимого: поля, кнопки и подсказка (в 1–2 строки)
        int noteLines = McGui.wrap(font, NOTE, winW - 2 * (PAD + 4) - 0).size();
        winH = in ? clamp(height - 40, 180, 230) : 124 + noteLines * 10 + 6;
        winX = (width - winW) / 2;
        winY = Math.max(4, (height - (winH + 16)) / 2);
        chatY = winY + winH + 4;

        int x = winX + PAD + 4, w = winW - 2 * (PAD + 4);
        int half = (w - 4) / 2;

        if (!in) {
            int y = winY + 24;
            emailBox = new EditBox(font, x + 1, y + 11, w - 2, 18, Component.translatable("rurukasuka.account.email"));
            emailBox.setHint(Component.literal("почта с сайта"));
            emailBox.setMaxLength(255);
            addRenderableWidget(emailBox);

            passBox = new EditBox(font, x + 1, y + 45, w - 2, 18, Component.translatable("rurukasuka.account.password"));
            passBox.setHint(Component.literal("пароль"));
            passBox.setMaxLength(255);
            addRenderableWidget(passBox);

            addRenderableWidget(new McButton(x, y + 72, half, 20,
                    Component.literal("Войти"), b -> doLogin()).cherry());
            addRenderableWidget(new McButton(x + half + 4, y + 72, w - half - 4, 20,
                    Component.literal("Назад"), b -> onClose()));
        } else {
            // игрок слева, статистика справа, кнопки внизу
            int btnY2 = winY + winH - PAD - 20, btnY1 = btnY2 - 24;
            fX1 = winX + PAD; fY1 = winY + 20; fY2 = btnY1 - 8;
            fX2 = fX1 + clamp((int) ((fY2 - fY1) * 0.72f), 64, 110);
            sX1 = fX2 + 10; sX2 = winX + winW - PAD - 2; sY = fY1;

            var models = Minecraft.getInstance().getEntityModels();
            wideModel = new PlayerModel(models.bakeLayer(ModelLayers.PLAYER), false);
            slimModel = new PlayerModel(models.bakeLayer(ModelLayers.PLAYER_SLIM), true);

            addRenderableWidget(new McButton(winX + PAD, btnY1, winW - 2 * PAD, 20,
                    Component.literal("Открыть гардероб"), b -> {
                        if (minecraft != null) minecraft.setScreen(new WardrobeScreen(this));
                    }).cherry());
            int hw = (winW - 2 * PAD - 4) / 2;
            addRenderableWidget(new McButton(winX + PAD, btnY2, hw, 20,
                    Component.literal("Выйти из аккаунта"), b -> {
                        RurukaAccount.LOCAL.logout(); SkinLoader.reset(); SessionStore.clear();
                        setStatus("Ты вышел из аккаунта", McGui.WHITE);
                        this.rebuildWidgets();
                    }));
            addRenderableWidget(new McButton(winX + PAD + hw + 4, btnY2, winW - 2 * PAD - hw - 4, 20,
                    Component.literal("Назад"), b -> onClose()));
        }
    }

    private void doLogin() {
        if (busy) return;
        String email = emailBox.getValue().trim();
        String pass = passBox.getValue();
        if (email.isEmpty() || pass.isEmpty()) {
            setStatus("Введи почту и пароль", McGui.MC_RED);
            return;
        }
        busy = true;
        setStatus("Вхожу…", McGui.WHITE);
        new Thread(() -> {
            try {
                SiteApi.Session s = SiteApi.login(email, pass);
                Minecraft.getInstance().execute(() -> {
                    RurukaAccount.LOCAL.applyLogin(s.token(), s.uuid(), s.nick(), s.balance(), s.owned(), s.equipped(), s.variants());
                    SkinLoader.loadFrom(s.skin() == null ? null : RurukaSuka.abs(s.skin()), s.skinModel());
                    SessionStore.save(s.token());
                    busy = false;
                    setStatus("Вход выполнен", McGui.MC_GREEN);
                    this.rebuildWidgets();
                });
            } catch (Exception ex) {
                String msg = ex.getMessage() == null ? "Нет связи с сайтом, попробуй ещё раз" : ex.getMessage();
                Minecraft.getInstance().execute(() -> {
                    busy = false;
                    setStatus(msg, McGui.MC_RED);
                });
            }
        }, "RurukaSuka-login").start();
    }

    private void setStatus(String s, int color) {
        this.status = s;
        this.statusColor = color;
    }

    @Override
    public void render(GuiGraphics g, int mouseX, int mouseY, float delta) {
        McGui.sky(g, width, height, stars);
        McGui.panel(g, winX, winY, winX + winW, winY + winH);

        if (!RurukaAccount.LOCAL.isLoggedIn()) {
            int x = winX + PAD + 4, y = winY + 24;
            McGui.ink(g, font, "Вход в аккаунт", winX + PAD + 1, winY + 8, McGui.INK);
            McGui.ink(g, font, "Почта", x, y, McGui.INK_SOFT);
            McGui.ink(g, font, "Пароль", x, y + 34, McGui.INK_SOFT);
            int ny = y + 100;
            for (String line : McGui.wrap(font, NOTE, winW - 2 * (PAD + 4))) {
                McGui.ink(g, font, line, x, ny, McGui.INK_SOFT);
                ny += 10;
            }
        } else {
            RurukaAccount acc = RurukaAccount.LOCAL;
            McGui.ink(g, font, "Аккаунт", winX + PAD + 1, winY + 8, McGui.INK);
            String ok = "вход выполнен";
            McGui.ink(g, font, ok, winX + winW - PAD - 1 - font.width(ok), winY + 8, 0xFF2C7A37);

            // игрок с надетой косметикой — как в инвентаре
            McGui.frame(g, fX1, fY1, fX2, fY2);
            renderPlayer(g);

            String nick = acc.nick() == null ? "не создан" : acc.nick();
            String uuid = acc.uuid() == null ? "—" : String.valueOf(acc.uuid());
            McGui.ink(g, font, McGui.fit(font, nick, sX2 - sX1), sX1, sY + 2, McGui.INK);
            McGui.statRow(g, font, sX1, sX2, sY + 16, "Номер игрока", uuid);
            String coins = Currency.format(acc.coins());
            McGui.statRow(g, font, sX1, sX2, sY + 36, "Баланс", coins);
            PixelIcons.coin(g, sX2 - font.width(coins) - PixelIcons.SIZE - 3, sY + 36 + 4, 1);
            g.fill(sX1, sY + 56, sX2, sY + 57, McGui.SLOT);
            g.fill(sX1, sY + 57, sX2, sY + 58, McGui.GUI_HI);
            int hy = sY + 64;
            for (String line : McGui.wrap(font, "Скин, ник и пароль меняются на сайте onii.ink.", sX2 - sX1)) {
                if (hy + 8 > fY2) break;
                McGui.ink(g, font, line, sX1, hy, McGui.INK_SOFT);
                hy += 10;
            }
        }

        McGui.chat(g, font, winX, chatY, winW, status, statusColor);
        super.render(g, mouseX, mouseY, delta);
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
        PlayerSkin skin = SkinLoader.currentOrDefault();
        PlayerModel pm = skin.model() == PlayerModelType.SLIM ? slimModel : wideModel;
        if (pm == null) return;
        int x1 = fX1 + 1, y1 = fY1 + 1, x2 = fX2 - 1, y2 = fY2 - 1;
        float scale = 0.82f * (y2 - y1) / 2.125f;
        ((GuiGraphicsAccessor) g).rurukasuka$guiRenderState().submitPicturesInPictureState(
                new PlayerCosmeticGuiRenderState("account_preview", pm, skin.body().texturePath(),
                        rotX, rotY, x1, y1, x2, y2, scale, pieces, null));
    }

    @Override
    public boolean mouseDragged(MouseButtonEvent event, double dragX, double dragY) {
        double mx = event.x(), my = event.y();
        if (RurukaAccount.LOCAL.isLoggedIn() && mx >= fX1 && mx <= fX2 && my >= fY1 && my <= fY2) {
            rotY += (float) (dragX * 0.6);
            rotX = Math.max(-45f, Math.min(45f, rotX - (float) (dragY * 0.6)));
            return true;
        }
        return super.mouseDragged(event, dragX, dragY);
    }

    @Override
    public void onClose() {
        if (minecraft != null) minecraft.setScreen(parent);
    }
}
