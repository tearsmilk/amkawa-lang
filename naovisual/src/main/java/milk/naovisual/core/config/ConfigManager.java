package milk.naovisual.core.config;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import milk.naovisual.NaoVisual;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.util.Friends;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

/**
 * Конфиг в config/naovisual/: client.json (активный профиль, друзья) и profiles/<имя>.json (модули и настройки).
 */
public final class ConfigManager {
    public static final int FORMAT = 1;
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
    private static Path root;
    private static String profile = "default";
    private static boolean dirty;

    private ConfigManager() {}

    public static void init(Path configDir) {
        root = configDir.resolve(NaoVisual.MOD_ID);
        try {
            Files.createDirectories(profilesDir());
        } catch (IOException e) {
            NaoVisual.LOGGER.error("Не удалось создать папку конфига", e);
        }
        loadClient();
        loadProfile(profile);
    }

    public static Path root() { return root; }
    public static Path profilesDir() { return root.resolve("profiles"); }
    public static String profile() { return profile; }
    public static void markDirty() { dirty = true; }

    /** Вызывается раз в тик: сохраняет отложенные изменения. */
    public static void tick() {
        if (dirty) {
            dirty = false;
            save();
        }
    }

    // --- client.json --------------------------------------------------------------------------------
    private static void loadClient() {
        Path f = root.resolve("client.json");
        if (!Files.exists(f)) return;
        try {
            JsonObject o = JsonParser.parseString(Files.readString(f, StandardCharsets.UTF_8)).getAsJsonObject();
            if (o.has("profile")) profile = o.get("profile").getAsString();
            if (o.has("friends") && o.get("friends").isJsonArray()) {
                List<String> names = new ArrayList<>();
                for (JsonElement e : o.getAsJsonArray("friends")) names.add(e.getAsString());
                Friends.setAll(names);
            }
        } catch (Exception e) {
            NaoVisual.LOGGER.error("client.json повреждён, используются значения по умолчанию", e);
        }
    }

    private static void saveClient() {
        JsonObject o = new JsonObject();
        o.addProperty("format", FORMAT);
        o.addProperty("profile", profile);
        JsonArray friends = new JsonArray();
        for (String n : Friends.all()) friends.add(n);
        o.add("friends", friends);
        write(root.resolve("client.json"), o);
    }

    // --- профили -------------------------------------------------------------------------------------
    public static JsonObject serializeProfile() {
        JsonObject o = new JsonObject();
        o.addProperty("format", FORMAT);
        o.addProperty("version", NaoVisual.version());
        JsonObject modules = new JsonObject();
        for (Module m : ModuleRegistry.all()) modules.add(m.id(), m.save());
        o.add("modules", modules);
        return o;
    }

    public static void applyProfile(JsonObject o) {
        if (o == null || !o.has("modules") || !o.get("modules").isJsonObject()) return;
        JsonObject modules = o.getAsJsonObject("modules");
        for (Module m : ModuleRegistry.all()) {
            m.resetSettings();
            if (modules.has(m.id()) && modules.get(m.id()).isJsonObject()) m.load(modules.getAsJsonObject(m.id()));
            else m.setEnabled(m.defaultEnabled());
        }
    }

    public static void save() {
        if (root == null) return;
        saveClient();
        write(profilesDir().resolve(profile + ".json"), serializeProfile());
    }

    public static boolean loadProfile(String name) {
        if (root == null) return false;
        name = sanitize(name);
        Path f = profilesDir().resolve(name + ".json");
        profile = name;
        if (!Files.exists(f)) {
            // новый профиль: значения по умолчанию
            for (Module m : ModuleRegistry.all()) { m.resetSettings(); m.setEnabled(m.defaultEnabled()); }
            save();
            return true;
        }
        try {
            JsonObject o = JsonParser.parseString(Files.readString(f, StandardCharsets.UTF_8)).getAsJsonObject();
            applyProfile(o);
            saveClient();
            return true;
        } catch (Exception e) {
            NaoVisual.LOGGER.error("Профиль {} повреждён", name, e);
            return false;
        }
    }

    public static List<String> profiles() {
        List<String> out = new ArrayList<>();
        if (root == null) return out;
        try (Stream<Path> s = Files.list(profilesDir())) {
            s.filter(p -> p.getFileName().toString().endsWith(".json"))
                    .map(p -> p.getFileName().toString().replaceFirst("\\.json$", ""))
                    .sorted().forEach(out::add);
        } catch (IOException ignored) {}
        if (!out.contains(profile)) out.add(0, profile);
        return out;
    }

    public static boolean deleteProfile(String name) {
        name = sanitize(name);
        if (name.equals(profile)) return false;
        try {
            return Files.deleteIfExists(profilesDir().resolve(name + ".json"));
        } catch (IOException e) {
            return false;
        }
    }

    /** Сохраняет текущие настройки как новый профиль и переключается на него. */
    public static void saveAs(String name) {
        profile = sanitize(name);
        save();
    }

    public static String sanitize(String name) {
        String s = name == null ? "" : name.trim().replaceAll("[^\\p{L}\\p{N}_\\- ]", "");
        if (s.isEmpty()) s = "default";
        return s.length() > 32 ? s.substring(0, 32) : s;
    }

    private static void write(Path f, JsonObject o) {
        try {
            Path tmp = f.resolveSibling(f.getFileName() + ".tmp");
            Files.writeString(tmp, GSON.toJson(o), StandardCharsets.UTF_8);
            Files.move(tmp, f, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) {
            try {
                Files.writeString(f, GSON.toJson(o), StandardCharsets.UTF_8);
            } catch (IOException e2) {
                NaoVisual.LOGGER.error("Не удалось сохранить {}", f, e2);
            }
        }
    }
}
