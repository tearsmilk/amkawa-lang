package milk.naovisual.core.setting;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.List;

/** Сворачиваемая группа вложенных настроек. Значение — развёрнута ли группа в меню. */
public class GroupSetting extends Setting<Boolean> {
    private final List<Setting<?>> children = new ArrayList<>();

    public GroupSetting(String name, String description, Setting<?>... children) {
        super(name, description, false);
        this.children.addAll(List.of(children));
    }

    public <S extends Setting<?>> S add(S s) { children.add(s); return s; }
    public List<Setting<?>> children() { return children; }
    public boolean expanded() { return value; }
    public void toggleExpanded() { set(!value); }

    @Override public JsonElement save() {
        JsonObject o = new JsonObject();
        o.addProperty("expanded", value);
        for (Setting<?> s : children) o.add(s.key(), s.save());
        return o;
    }

    @Override public void load(JsonElement json) {
        if (json == null || !json.isJsonObject()) return;
        JsonObject o = json.getAsJsonObject();
        if (o.has("expanded")) set(o.get("expanded").getAsBoolean());
        for (Setting<?> s : children) if (o.has(s.key())) s.load(o.get(s.key()));
    }

    @Override public void reset() {
        super.reset();
        for (Setting<?> s : children) s.reset();
    }
}
