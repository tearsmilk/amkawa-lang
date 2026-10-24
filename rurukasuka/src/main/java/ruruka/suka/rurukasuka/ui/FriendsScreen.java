package ruruka.suka.rurukasuka.ui;

import ruruka.suka.rurukasuka.account.RurukaAccount;
import ruruka.suka.rurukasuka.net.SiteApi;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * Друзья + чат в стиле Minecraft (как гардероб и сайт): серое окно, слева вдавленный список
 * друзей и заявок, справа чат на чёрном фоне строками «<ник> сообщение». Данные — с сайта.
 */
public class FriendsScreen extends Screen {
    private final Screen parent;

    // ── раскладка ──
    private static final int PAD = 7, ROW_H = 16, INPUT_H = 18;
    private int winX, winY, winW, winH, chatY;
    private int rX1, rX2, listY1, listY2;          // список друзей
    private int cX1, cX2, msgY1, msgY2;            // чат
    private int[] stars = new int[0];

    // ── данные (логика прежняя) ──
    private SiteApi.Friends data = new SiteApi.Friends(List.of(), List.of(), List.of());
    private SiteApi.Friend selected = null;
    private final List<SiteApi.Msg> messages = new ArrayList<>();
    private int lastMsgId = 0;

    private EditBox addBox, chatBox;
    private String status = "";
    private int statusColor = McGui.WHITE;
    private volatile boolean running = true;
    private int railScroll = 0;      // в строках списка
    private int chatScroll = 0;      // сколько строк чата отмотано вверх

    // кликабельные места (заполняются при отрисовке)
    private final List<int[]> friendRects = new ArrayList<>();      // {x1,y1,x2,y2,index}
    private final List<int[]> acceptRects = new ArrayList<>();      // {x1,y1,x2,y2,userId}
    private final List<int[]> declineRects = new ArrayList<>();

    public FriendsScreen(Screen parent) {
        super(Component.literal("Друзья"));
        this.parent = parent;
    }

    private static int clamp(int v, int lo, int hi) { return Math.max(lo, Math.min(hi, v)); }

    @Override
    protected void init() {
        winW = clamp(width - 24, 320, 700);
        winH = clamp(height - 24 - 16, 200, 420);
        winX = (width - winW) / 2;
        winY = Math.max(4, (height - (winH + 16)) / 2);
        chatY = winY + winH + 4;
        stars = McGui.stars(width, height);

        int cy0 = winY + 22, cy1 = winY + winH - PAD;
        int railW = clamp((int) (winW * 0.34f), 120, 220);
        rX1 = winX + PAD; rX2 = rX1 + railW;
        listY1 = cy0; listY2 = cy1 - INPUT_H - 4;
        cX1 = rX2 + 8; cX2 = winX + winW - PAD;
        msgY1 = cy0 + 12; msgY2 = cy1 - INPUT_H - 4;

        // добавить друга
        addBox = new EditBox(font, rX1 + 1, cy1 - INPUT_H + 1, railW - 26, INPUT_H - 2, Component.literal("ник"));
        addBox.setMaxLength(24);
        addBox.setHint(Component.literal("ник друга"));
        addRenderableWidget(addBox);
        addRenderableWidget(new McButton(rX2 - 22, cy1 - INPUT_H, 22, INPUT_H,
                Component.literal("+"), b -> doAddFriend()));

        // поле сообщения
        int sendW = clamp(font.width("Отправить") + 16, 64, 90);
        chatBox = new EditBox(font, cX1 + 1, cy1 - INPUT_H + 1, cX2 - cX1 - sendW - 6, INPUT_H - 2, Component.literal("сообщение"));
        chatBox.setMaxLength(500);
        chatBox.setHint(Component.literal("сообщение…"));
        addRenderableWidget(chatBox);
        addRenderableWidget(new McButton(cX2 - sendW, cy1 - INPUT_H, sendW, INPUT_H,
                Component.literal("Отправить"), b -> doSend()).cherry());

        // назад — справа в шапке окна
        addRenderableWidget(new McButton(winX + winW - PAD - 56, winY + 4, 56, 15,
                Component.literal("Назад"), b -> onClose()));

        refreshFriends();
        startPoll();
    }

    private String token() { return RurukaAccount.LOCAL.token(); }

    private void setStatus(String s, int color) { status = s; statusColor = color; }

    private void refreshFriends() {
        if (!RurukaAccount.LOCAL.isLoggedIn()) { setStatus("Войди в аккаунт в главном меню", McGui.MC_RED); return; }
        new Thread(() -> {
            try {
                SiteApi.Friends f = SiteApi.friends(token());
                Minecraft.getInstance().execute(() -> { data = f; });
            } catch (Exception ignored) {}
        }, "RurukaSuka-friends").start();
    }

    private void openChat(SiteApi.Friend f) {
        selected = f;
        messages.clear();
        lastMsgId = 0;
        chatScroll = 0;
        setStatus("", McGui.WHITE);
        new Thread(() -> {
            try {
                List<SiteApi.Msg> ms = SiteApi.messages(token(), f.id(), 0);
                Minecraft.getInstance().execute(() -> {
                    if (selected != null && selected.id() == f.id()) {
                        messages.clear(); messages.addAll(ms);
                        if (!ms.isEmpty()) lastMsgId = ms.get(ms.size() - 1).id();
                    }
                });
            } catch (Exception ignored) {}
        }, "RurukaSuka-chat").start();
    }

    private void doAddFriend() {
        String nick = addBox.getValue().trim();
        if (nick.isEmpty()) { setStatus("Впиши ник друга слева внизу", McGui.MC_RED); return; }
        new Thread(() -> {
            try {
                SiteApi.requestFriend(token(), nick);
                Minecraft.getInstance().execute(() -> {
                    setStatus("Заявка отправлена: " + nick, McGui.MC_GREEN);
                    addBox.setValue(""); refreshFriends();
                });
            } catch (Exception e) {
                String m = e.getMessage() == null ? "Не получилось отправить заявку" : e.getMessage();
                Minecraft.getInstance().execute(() -> setStatus(m, McGui.MC_RED));
            }
        }, "RurukaSuka-friend-add").start();
    }

    private void accept(int userId) {
        new Thread(() -> {
            try {
                SiteApi.acceptFriend(token(), userId);
                Minecraft.getInstance().execute(() -> { setStatus("Заявка принята", McGui.MC_GREEN); refreshFriends(); });
            } catch (Exception ignored) {}
        }, "RurukaSuka-friend-accept").start();
    }

    private void decline(int userId) {
        new Thread(() -> {
            try {
                SiteApi.removeFriend(token(), userId);
                Minecraft.getInstance().execute(() -> { setStatus("Заявка отклонена", McGui.WHITE); refreshFriends(); });
            } catch (Exception ignored) {}
        }, "RurukaSuka-friend-decline").start();
    }

    private void doSend() {
        if (selected == null) { setStatus("Сначала выбери друга слева", McGui.MC_RED); return; }
        String text = chatBox.getValue().trim();
        if (text.isEmpty()) return;
        chatBox.setValue("");
        chatScroll = 0;
        final int to = selected.id();
        new Thread(() -> {
            try {
                SiteApi.sendMessage(token(), to, text);
                List<SiteApi.Msg> ms = SiteApi.messages(token(), to, lastMsgId);
                Minecraft.getInstance().execute(() -> {
                    if (selected != null && selected.id() == to) {
                        messages.addAll(ms);
                        if (!ms.isEmpty()) lastMsgId = ms.get(ms.size() - 1).id();
                    }
                });
            } catch (Exception e) {
                String m = e.getMessage() == null ? "Сообщение не отправилось" : e.getMessage();
                Minecraft.getInstance().execute(() -> setStatus(m, McGui.MC_RED));
            }
        }, "RurukaSuka-msg-send").start();
    }

    private void startPoll() {
        Thread t = new Thread(() -> {
            int tick = 0;
            while (running) {
                try {
                    if (RurukaAccount.LOCAL.isLoggedIn()) {
                        if (tick % 2 == 0) {  // друзья реже
                            try {
                                SiteApi.Friends f = SiteApi.friends(token());
                                Minecraft.getInstance().execute(() -> { if (running) data = f; });
                            } catch (Exception ignored) {}
                        }
                        SiteApi.Friend sel = selected;
                        if (sel != null) {
                            try {
                                List<SiteApi.Msg> ms = SiteApi.messages(token(), sel.id(), lastMsgId);
                                if (!ms.isEmpty()) Minecraft.getInstance().execute(() -> {
                                    if (running && selected != null && selected.id() == sel.id()) {
                                        messages.addAll(ms);
                                        lastMsgId = ms.get(ms.size() - 1).id();
                                    }
                                });
                            } catch (Exception ignored) {}
                        }
                    }
                } catch (Exception ignored) {}
                tick++;
                try { Thread.sleep(2000); } catch (InterruptedException e) { return; }
            }
        }, "RurukaSuka-friends-poll");
        t.setDaemon(true);
        t.start();
    }

    // ── отрисовка ──
    @Override
    public void render(GuiGraphics g, int mouseX, int mouseY, float delta) {
        McGui.sky(g, width, height, stars);
        McGui.panel(g, winX, winY, winX + winW, winY + winH);
        McGui.ink(g, font, "Друзья", winX + PAD + 1, winY + 8, McGui.INK);
        String count = data.friends().size() + " в списке";
        McGui.ink(g, font, count, winX + PAD + 1 + font.width("Друзья") + 6, winY + 8, McGui.INK_SOFT);

        renderRail(g, mouseX, mouseY);
        renderChatArea(g);
        McGui.chat(g, font, winX, chatY, winW, status, statusColor);

        super.render(g, mouseX, mouseY, delta);
    }

    /** Строки списка: заголовок раздела, друг, входящая заявка, исходящая заявка. */
    private record Row(int kind, SiteApi.Friend f, int index, String text) {
        static final int HEADER = 0, FRIEND = 1, INCOMING = 2, OUTGOING = 3, EMPTY = 4;
    }

    private List<Row> rows() {
        List<Row> rs = new ArrayList<>();
        rs.add(new Row(Row.HEADER, null, -1, "Друзья"));
        for (int i = 0; i < data.friends().size(); i++) rs.add(new Row(Row.FRIEND, data.friends().get(i), i, null));
        if (data.friends().isEmpty()) rs.add(new Row(Row.EMPTY, null, -1, "Пока никого. Добавь друга по нику внизу."));
        if (!data.incoming().isEmpty()) {
            rs.add(new Row(Row.HEADER, null, -1, "Заявки: " + data.incoming().size()));
            for (SiteApi.Friend f : data.incoming()) rs.add(new Row(Row.INCOMING, f, -1, null));
        }
        if (!data.outgoing().isEmpty()) {
            rs.add(new Row(Row.HEADER, null, -1, "Ждут ответа"));
            for (SiteApi.Friend f : data.outgoing()) rs.add(new Row(Row.OUTGOING, f, -1, null));
        }
        return rs;
    }

    private int visibleRows() { return Math.max(1, (listY2 - listY1 - 4) / ROW_H); }

    private void renderRail(GuiGraphics g, int mouseX, int mouseY) {
        friendRects.clear(); acceptRects.clear(); declineRects.clear();
        McGui.slot(g, rX1, listY1, rX2, listY2, false);

        List<Row> rs = rows();
        railScroll = clamp(railScroll, 0, Math.max(0, rs.size() - visibleRows()));
        int x1 = rX1 + 3, x2 = rX2 - 3;
        int y = listY1 + 3;
        for (int i = railScroll; i < rs.size() && y + ROW_H <= listY2 - 1; i++) {
            Row r = rs.get(i);
            switch (r.kind()) {
                case Row.HEADER -> McGui.ink(g, font, r.text(), x1 + 1, y + 5, McGui.GUI_HI);
                case Row.EMPTY -> {
                    // подсказка в несколько строк: высота = строки × 10 + 4 (общий шаг ROW_H вычтен заранее)
                    List<String> lines = McGui.wrap(font, r.text(), x2 - x1 - 2);
                    int k = 0;
                    for (String line : lines) {
                        if (y + 4 + k * 10 + 8 > listY2 - 1) break;
                        McGui.ink(g, font, line, x1 + 1, y + 4 + k * 10, McGui.INK);
                        k++;
                    }
                    y += k * 10 + 4 - ROW_H;
                }
                case Row.FRIEND -> {
                    boolean sel = selected != null && selected.id() == r.f().id();
                    boolean hover = mouseX >= x1 && mouseX < x2 && mouseY >= y && mouseY < y + ROW_H - 1;
                    if (sel || hover) g.fill(x1, y, x2, y + ROW_H - 1, sel ? McGui.GUI : 0xFFA4A4A4);
                    if (sel) McGui.outline(g, x1, y, x2, y + ROW_H - 1, McGui.WHITE);
                    avatar(g, r.f().nick(), x1 + 2, y + 2);
                    McGui.ink(g, font, McGui.fit(font, r.f().nick(), x2 - x1 - 20), x1 + 17, y + 4, McGui.INK);
                    friendRects.add(new int[]{x1, y, x2, y + ROW_H - 1, r.index()});
                }
                case Row.INCOMING -> {
                    avatar(g, r.f().nick(), x1 + 2, y + 2);
                    McGui.ink(g, font, McGui.fit(font, r.f().nick(), x2 - x1 - 54), x1 + 17, y + 4, McGui.INK);
                    int ax = x2 - 34, dx = x2 - 16;
                    boolean ha = mouseX >= ax && mouseX < ax + 15 && mouseY >= y + 1 && mouseY < y + 14;
                    boolean hd = mouseX >= dx && mouseX < dx + 15 && mouseY >= y + 1 && mouseY < y + 14;
                    McGui.button(g, ax, y + 1, ax + 15, y + 14, false, ha, true);
                    McGui.button(g, dx, y + 1, dx + 15, y + 14, false, hd, true);
                    g.drawCenteredString(font, Component.literal("✓"), ax + 8, y + 3, McGui.MC_GREEN);
                    g.drawCenteredString(font, Component.literal("✗"), dx + 8, y + 3, McGui.MC_RED);
                    acceptRects.add(new int[]{ax, y + 1, ax + 15, y + 14, r.f().id()});
                    declineRects.add(new int[]{dx, y + 1, dx + 15, y + 14, r.f().id()});
                }
                case Row.OUTGOING -> {
                    avatar(g, r.f().nick(), x1 + 2, y + 2);
                    McGui.ink(g, font, McGui.fit(font, r.f().nick(), x2 - x1 - 20), x1 + 17, y + 4, McGui.INK);
                }
                default -> { }
            }
            y += ROW_H;
        }
    }

    /** Квадратик-аватар с первой буквой ника; цвет зависит от ника. */
    private void avatar(GuiGraphics g, String nick, int x, int y) {
        int[] cols = {0xFFB5476A, 0xFF4F8A2C, 0xFF3A6EA5, 0xFFC97A34, 0xFF7A4FB0, 0xFF2E8B8B};
        int c = cols[Math.floorMod(nick == null ? 0 : nick.hashCode(), cols.length)];
        g.fill(x, y, x + 12, y + 12, 0xFF000000);
        g.fill(x + 1, y + 1, x + 11, y + 11, c);
        g.fill(x + 1, y + 1, x + 11, y + 2, 0x40FFFFFF);
        String ch = (nick == null || nick.isEmpty()) ? "?" : nick.substring(0, 1).toUpperCase();
        g.drawCenteredString(font, Component.literal(ch), x + 6, y + 2, McGui.WHITE);
    }

    /** Строки чата после переноса: имя (с цветом) и текст. */
    private record ChatLine(String name, int nameColor, String text) {}

    private List<ChatLine> chatLines(int maxPx) {
        List<ChatLine> out = new ArrayList<>();
        if (selected == null) return out;
        for (SiteApi.Msg m : messages) {
            boolean mine = m.from() != selected.id();
            String name = "<" + (mine ? "Вы" : selected.nick()) + "> ";
            int color = mine ? McGui.BLOSSOM : 0xFF55FFFF;
            List<String> parts = McGui.wrap(font, m.text(), maxPx - font.width(name));
            for (int i = 0; i < parts.size(); i++) {
                out.add(new ChatLine(i == 0 ? name : "", color, (i == 0 ? "" : "  ") + parts.get(i)));
            }
        }
        return out;
    }

    private int chatVisibleLines() { return Math.max(1, (msgY2 - msgY1 - 6) / 10); }

    private void renderChatArea(GuiGraphics g) {
        // ник собеседника над чатом
        String head = selected == null ? "Чат" : "Чат с " + selected.nick();
        McGui.ink(g, font, McGui.fit(font, head, cX2 - cX1 - 70), cX1 + 1, listY1 + 1, McGui.INK);
        McGui.frame(g, cX1, msgY1, cX2, msgY2);

        int cx = (cX1 + cX2) / 2, midY = (msgY1 + msgY2) / 2 - 4;
        if (!RurukaAccount.LOCAL.isLoggedIn()) {
            g.drawCenteredString(font, Component.literal("Войди в аккаунт в главном меню"), cx, midY, McGui.MC_GRAY);
            return;
        }
        if (selected == null) {
            g.drawCenteredString(font, Component.literal("Выбери друга слева, чтобы открыть чат"), cx, midY, McGui.MC_GRAY);
            return;
        }
        List<ChatLine> lines = chatLines(cX2 - cX1 - 12);
        if (lines.isEmpty()) {
            g.drawCenteredString(font, Component.literal("Сообщений пока нет. Напиши первым"), cx, midY, McGui.MC_GRAY);
            return;
        }
        int vis = chatVisibleLines();
        chatScroll = clamp(chatScroll, 0, Math.max(0, lines.size() - vis));
        int end = lines.size() - chatScroll;
        int start = Math.max(0, end - vis);
        int y = msgY2 - 4 - (end - start) * 10;   // прижимаем к низу, как чат в игре
        for (int i = start; i < end; i++) {
            ChatLine l = lines.get(i);
            int x = cX1 + 6;
            if (!l.name().isEmpty()) {
                g.drawString(font, Component.literal(l.name()), x, y, l.nameColor());
                x += font.width(l.name());
            }
            g.drawString(font, Component.literal(l.text()), x, y, McGui.WHITE);
            y += 10;
        }
        if (chatScroll > 0) {
            String more = "\u25BC ниже ещё " + chatScroll;   // отмотано вверх — показываем, сколько строк ниже
            g.drawString(font, Component.literal(more), cX2 - 6 - font.width(more), msgY1 + 4, McGui.MC_GRAY);
        }
    }

    // ── ввод ──
    private boolean in(int[] r, double x, double y) { return x >= r[0] && x < r[2] && y >= r[1] && y < r[3]; }

    @Override
    public boolean mouseClicked(MouseButtonEvent event, boolean doubleClick) {
        double mx = event.x(), my = event.y();
        for (int[] r : acceptRects) if (in(r, mx, my)) { accept(r[4]); return true; }
        for (int[] r : declineRects) if (in(r, mx, my)) { decline(r[4]); return true; }
        for (int[] r : friendRects) if (in(r, mx, my)) { openChat(data.friends().get(r[4])); return true; }
        return super.mouseClicked(event, doubleClick);
    }

    /**
     * Колесо: над списком — листает друзей, над чатом — историю сообщений.
     * Без @Override намеренно (см. WardrobeScreen.mouseScrolled).
     */
    public boolean mouseScrolled(double mouseX, double mouseY, double scrollX, double scrollY) {
        int dir = (int) Math.signum(scrollY);
        if (mouseX >= rX1 && mouseX < rX2 && mouseY >= listY1 && mouseY < listY2) {
            railScroll = Math.max(0, railScroll - dir);
            return true;
        }
        if (mouseX >= cX1 && mouseX < cX2 && mouseY >= msgY1 && mouseY < msgY2) {
            chatScroll = Math.max(0, chatScroll + dir * 3);
            return true;
        }
        return false;
    }

    @Override
    public void onClose() {
        running = false;
        if (minecraft != null) minecraft.setScreen(parent);
    }
}
