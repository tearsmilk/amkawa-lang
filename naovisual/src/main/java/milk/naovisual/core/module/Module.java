package milk.naovisual.core.module;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import milk.naovisual.NaoVisual;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.GroupSetting;
import milk.naovisual.core.setting.KeybindSetting;
import milk.naovisual.core.setting.Setting;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;

import java.util.ArrayList;
import java.util.List;

/** Модуль: имя, категория, набор настроек, клавиша и обработчики событий. */
public abstract class Module {
    private final String id;          // английское имя, ключ в конфиге
    private final String title;       // русское название
    private final String description;
    private final ModuleCategory category;
    private final List<Setting<?>> settings = new ArrayList<>();
    private boolean enabled;
    public final KeybindSetting bind = new KeybindSetting("Клавиша", "Клавиша включения модуля", KeybindSetting.NONE);
    public final BooleanSetting hideInList = new BooleanSetting("Скрыть в списке", "Не показывать в списке модулей", false);

    protected Module(String id, String title, String description, ModuleCategory category) {
        this.id = id;
        this.title = title;
        this.description = description;
        this.category = category;
    }

    public String id() { return id; }
    public String title() { return title; }
    public String displayName() { return Language.english() ? id : title; }
    public String description() { return description; }
    public ModuleCategory category() { return category; }
    public List<Setting<?>> settings() { return settings; }
    public boolean isEnabled() { return enabled; }

    protected <S extends Setting<?>> S add(S s) {
        settings.add(s);
        return s;
    }

    public static Minecraft mc() { return NaoVisual.mc(); }

    protected static boolean inGame() {
        Minecraft mc = mc();
        return mc.player != null && mc.level != null;
    }

    public void setEnabled(boolean on) {
        if (enabled == on) return;
        enabled = on;
        try {
            if (on) onEnable(); else onDisable();
        } catch (Exception e) {
            NaoVisual.LOGGER.error("Модуль {}: ошибка при {}", id, on ? "включении" : "выключении", e);
        }
    }

    public void toggle() {
        setEnabled(!enabled);
        milk.naovisual.core.hud.Notifications.moduleToggled(this);
    }

    /** Включён ли модуль по умолчанию в новом профиле. */
    public boolean defaultEnabled() { return false; }

    // --- события -------------------------------------------------------------------------------------
    public void onEnable() {}
    public void onDisable() {}
    public void onTick() {}
    public void onRenderWorld(WorldRenderContext ctx) {}
    /** Отрисовка поверх HUD (не для HudModule, у тех свой renderHud с позицией). */
    public void onRenderOverlay(GuiGraphics g, DeltaTracker delta) {}
    public void onAttack(Entity target) {}
    public void onTotemPop(LivingEntity entity) {}
    public void onDamage(LivingEntity entity) {}
    public void onJump(LivingEntity entity) {}
    public void onJoinWorld() {}
    public void onDisconnect() {}
    /** Нажатие клавиши в игре (не в меню). Вернуть true, чтобы поглотить. */
    public boolean onKey(int key) { return false; }

    // --- сериализация ----------------------------------------------------------------------------
    public JsonObject save() {
        JsonObject o = new JsonObject();
        o.addProperty("enabled", enabled);
        o.add("bind", bind.save());
        o.add("hide_in_list", hideInList.save());
        JsonObject s = new JsonObject();
        for (Setting<?> st : settings) s.add(st.key(), st.save());
        o.add("settings", s);
        saveExtra(o);
        return o;
    }

    public void load(JsonObject o) {
        if (o == null) return;
        if (o.has("bind")) bind.load(o.get("bind"));
        if (o.has("hide_in_list")) hideInList.load(o.get("hide_in_list"));
        if (o.has("settings") && o.get("settings").isJsonObject()) {
            JsonObject s = o.getAsJsonObject("settings");
            for (Setting<?> st : settings) {
                JsonElement e = s.get(st.key());
                if (e != null) st.load(e);
            }
        }
        loadExtra(o);
        setEnabled(o.has("enabled") && o.get("enabled").getAsBoolean());
    }

    protected void saveExtra(JsonObject o) {}
    protected void loadExtra(JsonObject o) {}

    public void resetSettings() {
        for (Setting<?> s : settings) s.reset();
        bind.reset();
        hideInList.reset();
    }

    /** Все настройки включая вложенные в группы — для поиска и проверки. */
    public List<Setting<?>> allSettings() {
        List<Setting<?>> out = new ArrayList<>();
        collect(settings, out);
        return out;
    }

    private static void collect(List<Setting<?>> in, List<Setting<?>> out) {
        for (Setting<?> s : in) {
            out.add(s);
            if (s instanceof GroupSetting g) collect(g.children(), out);
        }
    }

    @Override public String toString() { return id; }
}
