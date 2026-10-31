package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.theme.ThemeManager;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.world.scores.DisplaySlot;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.PlayerScoreEntry;
import net.minecraft.world.scores.PlayerTeam;
import net.minecraft.world.scores.Scoreboard;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Боковой скорборд в своём стиле; можно скрыть красные числа. */
public class ScoreBoardModule extends HudModule {
    private final BooleanSetting hideNumbers = add(new BooleanSetting("Скрыть числа", "Убрать красные очки справа", true));
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final BooleanSetting shadow = add(new BooleanSetting("Тень текста", "", false));

    public ScoreBoardModule() {
        super("ScoreBoard", "Скорборд", "Боковой скорборд сервера в стиле клиента", 0.985, 0.4);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        List<Component> lines = new ArrayList<>();
        List<Component> scores = new ArrayList<>();
        Component title = Component.literal("Скорборд");
        if (mc().level != null) {
            Scoreboard sb = mc().level.getScoreboard();
            Objective obj = sb.getDisplayObjective(DisplaySlot.SIDEBAR);
            if (obj != null) {
                title = obj.getDisplayName();
                List<PlayerScoreEntry> entries = new ArrayList<>(sb.listPlayerScores(obj));
                entries.removeIf(PlayerScoreEntry::isHidden);
                entries.sort(Comparator.comparingInt(PlayerScoreEntry::value).reversed().thenComparing(PlayerScoreEntry::owner, Comparator.reverseOrder()));
                if (entries.size() > 15) entries = entries.subList(0, 15);
                for (PlayerScoreEntry e : entries) {
                    PlayerTeam team = sb.getPlayersTeam(e.owner());
                    lines.add(PlayerTeam.formatNameForTeam(team, e.ownerName()));
                    scores.add(e.formatValue(obj.numberFormatOrDefault(net.minecraft.network.chat.numbers.StyledFormat.SIDEBAR_DEFAULT)));
                }
            }
        }
        if (lines.isEmpty() && !editor) { setSize(10, 10); return; }
        if (lines.isEmpty()) { lines.add(Component.literal("Пример строки")); scores.add(Component.literal("1")); }
        int w = Render2D.width(title.getString()) + 10;
        for (int i = 0; i < lines.size(); i++) w = Math.max(w, mc().font.width(lines.get(i)) + (hideNumbers.on() ? 0 : mc().font.width(scores.get(i)) + 6) + 10);
        int rowH = 10, h = 14 + lines.size() * rowH + 3;
        setSize(w, h);
        var t = ThemeManager.current();
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.8f);
        g.drawString(mc().font, title, w / 2 - mc().font.width(title) / 2, 3, t.text, shadow.on());
        Render2D.rect(g, 5, 13, w - 10, 1, t.border);
        int y = 16;
        for (int i = 0; i < lines.size(); i++) {
            g.drawString(mc().font, lines.get(i), 5, y, t.text, shadow.on());
            if (!hideNumbers.on()) g.drawString(mc().font, scores.get(i), w - 5 - mc().font.width(scores.get(i)), y, t.danger, shadow.on());
            y += rowH;
        }
    }
}
