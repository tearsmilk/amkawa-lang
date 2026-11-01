package milk.naovisual.core.setting;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Несколько флажков из списка. */
public class MultiSelectSetting extends Setting<Set<String>> {
    private final List<String> options;

    public MultiSelectSetting(String name, String description, List<String> options, String... selected) {
        super(name, description, new LinkedHashSet<>(List.of(selected)));
        this.options = List.copyOf(options);
    }

    public List<String> options() { return options; }
    public boolean has(String option) { return value.contains(option); }

    public void toggle(String option) {
        if (!options.contains(option)) return;
        Set<String> copy = new LinkedHashSet<>(value);
        if (!copy.remove(option)) copy.add(option);
        set(copy);
    }

    @Override public void reset() { set(new LinkedHashSet<>(defaultValue)); }

    @Override public JsonElement save() {
        JsonArray a = new JsonArray();
        for (String o : options) if (value.contains(o)) a.add(o);
        return a;
    }

    @Override public void load(JsonElement json) {
        if (json == null || !json.isJsonArray()) return;
        Set<String> s = new LinkedHashSet<>();
        for (JsonElement e : json.getAsJsonArray()) if (e.isJsonPrimitive() && options.contains(e.getAsString())) s.add(e.getAsString());
        set(s);
    }
}
