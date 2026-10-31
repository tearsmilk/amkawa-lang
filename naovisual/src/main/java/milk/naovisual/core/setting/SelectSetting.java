package milk.naovisual.core.setting;

import com.google.gson.JsonElement;
import com.google.gson.JsonPrimitive;

import java.util.List;

/** Выбор одного варианта из списка. */
public class SelectSetting extends Setting<String> {
    private final List<String> options;

    public SelectSetting(String name, String description, String defaultValue, String... options) {
        super(name, description, defaultValue);
        this.options = List.of(options);
        if (!this.options.contains(defaultValue)) throw new IllegalArgumentException("default not in options: " + defaultValue);
    }

    public List<String> options() { return options; }
    public boolean is(String option) { return value.equals(option); }
    public int index() { return options.indexOf(value); }

    public void next() { set(options.get((index() + 1) % options.size())); }
    public void previous() { set(options.get((index() - 1 + options.size()) % options.size())); }

    @Override public void set(String v) {
        if (v != null && options.contains(v)) super.set(v);
    }

    @Override public JsonElement save() { return new JsonPrimitive(value); }

    @Override public void load(JsonElement json) {
        if (json != null && json.isJsonPrimitive()) set(json.getAsString());
    }
}
