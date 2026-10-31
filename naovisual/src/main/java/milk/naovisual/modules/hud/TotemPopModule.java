package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Notifications;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.theme.ThemeManager;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Счётчик сломанных тотемов по игрокам + сообщения в чат. */
public class TotemPopModule extends HudModule {
    private final BooleanSetting chat = add(new BooleanSetting("Сообщение в чат", "", true));
    private final BooleanSetting notify = add(new BooleanSetting("Уведомление", "", true));
    private final BooleanSetting self = add(new BooleanSetting("Свои тотемы", "Считать и свои", true));
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final Map<String, Integer> pops = new LinkedHashMap<>();

    public TotemPopModule() {
        super("TotemPop", "Тотемы", "Считает, сколько тотемов сломал каждый игрок", 0.012, 0.6);
    }

    @Override
    public void onTotemPop(LivingEntity e) {
        if (!(e instanceof Player p)) return;
        if (p == mc().player && !self.on()) return;
        String name = p.getGameProfile().name();
        int n = pops.merge(name, 1, Integer::sum);
        if (chat.on() && mc().player != null) mc().gui.getChat().addMessage(Component.literal("§7[§6Nao§7] §f" + name + " §7сломал тотем §f#" + n));
        if (notify.on()) Notifications.push("Тотем", name + " — " + n, Notifications.Type.WARNING, 2500);
    }

    @Override public void onDisconnect() { pops.clear(); }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        List<Map.Entry<String, Integer>> rows = new ArrayList<>(pops.entrySet());
        if (editor && rows.isEmpty()) rows.add(Map.entry("Игрок", 3));
        rows.sort((a, b) -> b.getValue() - a.getValue());
        if (rows.size() > 8) rows = rows.subList(0, 8);
        int w = 110, h = 16 + rows.size() * 12 + 2;
        setSize(w, h);
        if (rows.isEmpty()) return;
        var t = ThemeManager.current();
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        g.renderItem(new ItemStack(Items.TOTEM_OF_UNDYING), 2, 0);
        Render2D.text(g, "Тотемы", 20, 4, t.text);
        int y = 16;
        for (var r : rows) {
            Render2D.text(g, Render2D.trim(r.getKey(), w - 30), 5, y, t.textMuted);
            Render2D.textRight(g, String.valueOf(r.getValue()), w - 5, y, t.accent, false);
            y += 12;
        }
    }
}
