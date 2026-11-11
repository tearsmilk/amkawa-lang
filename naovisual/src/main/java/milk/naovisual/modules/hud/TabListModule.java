package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.Friends;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.PlayerFaceRenderer;
import net.minecraft.client.multiplayer.PlayerInfo;
import net.minecraft.network.chat.Component;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Список игроков по Tab: головы, ники, пинг, друзья подсвечены. */
public class TabListModule extends Module {
    private final BooleanSetting heads = add(new BooleanSetting("Головы", "", true));
    private final BooleanSetting ping = add(new BooleanSetting("Пинг", "Числом вместо полосок", true));
    private final NumberSetting columns = add(new NumberSetting("Колонок максимум", "", 4, 1, 8, 1));
    private final NumberSetting rows = add(new NumberSetting("Строк в колонке", "", 20, 5, 40, 1));
    private final BooleanSetting highlightFriends = add(new BooleanSetting("Подсветка друзей", "", true));

    public TabListModule() {
        super("TabList", "Таб", "Список игроков по Tab в стиле клиента", ModuleCategory.HUD);
    }

    @Override
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {
        var mc = mc();
        if (mc.player == null || mc.getConnection() == null || mc.options.hideGui) return;
        boolean show = mc.options.keyPlayerList.isDown() && (mc.isLocalServer() ? mc.getConnection().getListedOnlinePlayers().size() > 1 : true);
        if (!show || mc.screen != null) return;
        List<PlayerInfo> players = new ArrayList<>(mc.getConnection().getListedOnlinePlayers());
        players.sort(Comparator.comparing((PlayerInfo i) -> i.getGameMode() == net.minecraft.world.level.GameType.SPECTATOR)
                .thenComparing(i -> i.getTeam() == null ? "" : i.getTeam().getName())
                .thenComparing(i -> i.getProfile().name().toLowerCase()));
        if (players.size() > 80) players = players.subList(0, 80);
        int perCol = rows.getInt();
        int cols = Math.max(1, Math.min(columns.getInt(), (players.size() + perCol - 1) / perCol));
        int rowsUsed = (players.size() + cols - 1) / cols;
        int colW = 10;
        for (PlayerInfo i : players) colW = Math.max(colW, mc.font.width(mc.gui.getTabList().getNameForDisplay(i)) + (heads.on() ? 12 : 0) + (ping.on() ? 32 : 24) + 6);
        var t = ThemeManager.current();
        int rowH = 10, pad = 6;
        String header = mc.getCurrentServer() != null ? mc.getCurrentServer().name : "Игроки";
        int w = cols * colW + (cols - 1) * 4 + pad * 2, h = pad * 2 + 14 + rowsUsed * rowH;
        int x = g.guiWidth() / 2 - w / 2, y = 12;
        Panels.panel(g, x, y, w, h, 0.9f);
        Render2D.textCentered(g, header + "  •  " + players.size(), x + w / 2, y + 4, t.text, false);
        Render2D.rect(g, x + pad, y + 15, w - pad * 2, 1, t.border);
        for (int idx = 0; idx < players.size(); idx++) {
            PlayerInfo info = players.get(idx);
            int col = idx / rowsUsed, row = idx % rowsUsed;
            int px = x + pad + col * (colW + 4), py = y + pad + 14 + row * rowH;
            boolean friend = highlightFriends.on() && Friends.contains(info.getProfile().name());
            boolean self = info.getProfile().id().equals(mc.player.getUUID());
            if (friend || self) Render2D.roundedRect(g, px - 1, py - 1, colW + 2, rowH, 2, self ? t.accentSoft : 0x3355AA55);
            int tx = px;
            if (heads.on()) { PlayerFaceRenderer.draw(g, info.getSkin(), px, py, 8); tx += 11; }
            Component name = mc.gui.getTabList().getNameForDisplay(info);
            int nameColor = info.getGameMode() == net.minecraft.world.level.GameType.SPECTATOR ? t.textMuted : t.text;
            g.drawString(mc.font, name, tx, py, nameColor, false);
            int lat = info.getLatency();
            int pc = lat < 100 ? t.success : lat < 250 ? 0xFFE8B84A : t.danger;
            if (ping.on()) Render2D.textRight(g, lat + "ms", px + colW - 2, py, pc, false);
            else {
                int bars = lat < 150 ? 5 : lat < 300 ? 4 : lat < 600 ? 3 : lat < 1000 ? 2 : 1;
                for (int b = 0; b < 5; b++) Render2D.rect(g, px + colW - 12 + b * 2, py + 7 - b, 1, 1 + b, b < bars ? pc : 0x33000000);
            }
        }
    }
}
