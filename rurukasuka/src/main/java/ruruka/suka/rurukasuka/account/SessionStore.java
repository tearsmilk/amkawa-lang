package ruruka.suka.rurukasuka.account;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import ruruka.suka.rurukasuka.RurukaSuka;
import net.fabricmc.loader.api.FabricLoader;

import java.nio.file.Files;
import java.nio.file.Path;

/** Хранит токен входа между запусками игры (config/rurukasuka_session.txt).
 *  Лаунчер Эта перед каждым запуском пишет config/rurukasuka_launcher.json
 *  ({"token","site","nick"}) — его токен важнее сохранённой сессии, а site переопределяет адрес сайта. */
public final class SessionStore {

    private static Path file() {
        return FabricLoader.getInstance().getConfigDir().resolve("rurukasuka_session.txt");
    }

    private static Path launcherFile() {
        return FabricLoader.getInstance().getConfigDir().resolve("rurukasuka_launcher.json");
    }

    /** Файл сессии от старой версии мода (CutieMi) — чтобы не разлогинивать игроков после ребренда. */
    private static Path legacyFile() {
        return FabricLoader.getInstance().getConfigDir().resolve("cutiemi_session.txt");
    }

    public static String load() {
        String fromLauncher = loadLauncher();
        if (fromLauncher != null) return fromLauncher;
        try {
            Path f = file();
            Path legacy = legacyFile();
            if (!Files.exists(f) && Files.exists(legacy)) {
                Files.move(legacy, f); // разовая миграция токена
            }
            if (Files.exists(f)) {
                String t = Files.readString(f).trim();
                return t.isEmpty() ? null : t;
            }
        } catch (Exception e) {
            RurukaSuka.LOGGER.warn("RurukaSuka: session read failed", e);
        }
        return null;
    }

    /** Токен из файла лаунчера (или null). Побочно применяет "site", если он задан. */
    private static String loadLauncher() {
        try {
            Path f = launcherFile();
            if (!Files.exists(f)) return null;
            JsonObject o = JsonParser.parseString(Files.readString(f)).getAsJsonObject();
            if (o.has("site") && !o.get("site").isJsonNull()) {
                String site = o.get("site").getAsString().trim();
                while (site.endsWith("/")) site = site.substring(0, site.length() - 1);
                if (site.startsWith("http")) RurukaSuka.SITE_URL = site;
            }
            if (o.has("token") && !o.get("token").isJsonNull()) {
                String t = o.get("token").getAsString().trim();
                if (!t.isEmpty()) {
                    RurukaSuka.LOGGER.info("RurukaSuka: session from the Eta launcher");
                    return t;
                }
            }
        } catch (Exception e) {
            RurukaSuka.LOGGER.warn("RurukaSuka: launcher session read failed", e);
        }
        return null;
    }

    public static void save(String token) {
        try {
            Files.writeString(file(), token == null ? "" : token);
        } catch (Exception e) {
            RurukaSuka.LOGGER.warn("RurukaSuka: session save failed", e);
        }
    }

    public static void clear() {
        try {
            Files.deleteIfExists(file());
            Files.deleteIfExists(launcherFile());
        } catch (Exception e) {
            RurukaSuka.LOGGER.warn("RurukaSuka: session clear failed", e);
        }
    }

    private SessionStore() {}
}
