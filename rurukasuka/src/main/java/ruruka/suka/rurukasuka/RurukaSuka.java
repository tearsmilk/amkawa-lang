package ruruka.suka.rurukasuka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class RurukaSuka {
    public static final String MOD_ID = "rurukasuka";
    public static final Logger LOGGER = LoggerFactory.getLogger("RurukaSuka");

    /** База сайта (API входа, баланса и косметики). Лаунчер Эта может переопределить через
     *  config/rurukasuka_launcher.json — см. {@link ruruka.suka.rurukasuka.account.SessionStore}. */
    public static volatile String SITE_URL = "https://mc-ru.org";

    /** Абсолютный URL: сайт отдаёт и полные ссылки (https://…), и относительные (/api/…). */
    public static String abs(String url) {
        if (url == null) return null;
        return url.startsWith("http://") || url.startsWith("https://") ? url : SITE_URL + url;
    }

    private RurukaSuka() {}
}
