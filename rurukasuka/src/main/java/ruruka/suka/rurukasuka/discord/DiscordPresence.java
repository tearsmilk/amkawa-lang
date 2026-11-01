package ruruka.suka.rurukasuka.discord;

import com.google.gson.JsonObject;
import ruruka.suka.rurukasuka.RurukaSuka;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.Minecraft;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.net.StandardProtocolFamily;
import java.net.UnixDomainSocketAddress;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.SocketChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;

/**
 * Минимальный Discord Rich Presence (IPC) без внешних библиотек.
 * App ID берётся из config/rurukasuka_discord.txt (первая строка; старый cutiemi_discord.txt
 * тоже читается) или из DEFAULT_APP_ID.
 * Ассет большой картинки — ключ "logo" (загружается в Rich Presence Art Assets приложения).
 */
public final class DiscordPresence {

    // TODO: замени на свой Application ID из discord.com/developers/applications
    private static final String DEFAULT_APP_ID = "1548766637686001734";

    private static volatile boolean running = false;
    private static volatile boolean connected = false;
    private static String appId = DEFAULT_APP_ID;

    private static SocketChannel unix;      // mac/linux
    private static RandomAccessFile winPipe; // windows
    private static final long START = System.currentTimeMillis() / 1000L;
    private static String lastKey = "";

    public static void start() {
        if (running) return;
        running = true;
        appId = readAppId();
        if (appId == null || appId.isBlank() || appId.startsWith("0000000000")) {
            RurukaSuka.LOGGER.info("RurukaSuka: Discord RPC отключён (не задан App ID в config/rurukasuka_discord.txt)");
            return;
        }
        Thread t = new Thread(DiscordPresence::loop, "RurukaSuka-discord");
        t.setDaemon(true);
        t.start();
    }

    public static void stop() {
        running = false;
        close();
    }

    private static String readAppId() {
        try {
            Path dir = FabricLoader.getInstance().getConfigDir();
            // новый файл, затем файл от старой версии (CutieMi)
            for (String name : new String[]{"rurukasuka_discord.txt", "cutiemi_discord.txt"}) {
                Path f = dir.resolve(name);
                if (Files.exists(f)) {
                    String s = Files.readString(f).trim();
                    if (!s.isEmpty()) return s.split("\\R")[0].trim();
                }
            }
        } catch (Exception ignored) {}
        return DEFAULT_APP_ID;
    }

    private static void loop() {
        while (running) {
            try {
                if (!connected) tryConnect();
                if (connected) updateFromGame();
            } catch (Exception e) {
                close();
            }
            try { Thread.sleep(3000); } catch (InterruptedException e) { return; }
        }
    }

    // ── подключение ──
    private static void tryConnect() {
        boolean win = System.getProperty("os.name", "").toLowerCase().contains("win");
        for (int i = 0; i < 10; i++) {
            try {
                if (win) {
                    winPipe = new RandomAccessFile("\\\\.\\pipe\\discord-ipc-" + i, "rw");
                } else {
                    Path p = unixSocketPath(i);
                    if (p == null || !Files.exists(p)) continue;
                    unix = SocketChannel.open(StandardProtocolFamily.UNIX);
                    unix.connect(UnixDomainSocketAddress.of(p));
                }
                // handshake
                JsonObject hs = new JsonObject();
                hs.addProperty("v", 1);
                hs.addProperty("client_id", appId);
                send(0, hs.toString());
                drainOnce(); // прочитать READY
                connected = true;
                lastKey = "";
                RurukaSuka.LOGGER.info("RurukaSuka: Discord RPC подключён (ipc-{})", i);
                return;
            } catch (Exception e) {
                close();
            }
        }
    }

    private static Path unixSocketPath(int i) {
        String[] bases = {
                System.getenv("XDG_RUNTIME_DIR"),
                System.getenv("TMPDIR"),
                "/tmp"
        };
        String[] sub = {"", "/app/com.discordapp.Discord", "/snap.discord-canary", "/snap.discord"};
        for (String base : bases) {
            if (base == null) continue;
            for (String sd : sub) {
                Path p = Path.of(base + sd, "discord-ipc-" + i);
                if (Files.exists(p)) return p;
            }
        }
        return null;
    }

    // ── обновление статуса ──
    private static void updateFromGame() throws IOException {
        String details, state;
        try {
            Minecraft mc = Minecraft.getInstance();
            if (mc.getCurrentServer() != null) {
                details = "На сервере";
                state = mc.getCurrentServer().ip;
            } else if (mc.level != null) {
                details = "Одиночная игра";
                state = "";
            } else {
                details = "В главном меню";
                state = "";
            }
        } catch (Throwable t) {
            details = "В игре";
            state = "";
        }

        String key = details + "|" + state;
        if (key.equals(lastKey)) return;
        lastKey = key;

        JsonObject activity = new JsonObject();
        activity.addProperty("details", details);
        if (!state.isEmpty()) activity.addProperty("state", state);
        JsonObject ts = new JsonObject();
        ts.addProperty("start", START);
        activity.add("timestamps", ts);
        JsonObject assets = new JsonObject();
        assets.addProperty("large_image", "logo");
        assets.addProperty("large_text", "RurukaSuka");
        activity.add("assets", assets);

        JsonObject args = new JsonObject();
        args.addProperty("pid", ProcessHandle.current().pid());
        args.add("activity", activity);
        JsonObject frame = new JsonObject();
        frame.addProperty("cmd", "SET_ACTIVITY");
        frame.add("args", args);
        frame.addProperty("nonce", UUID.randomUUID().toString());

        send(1, frame.toString());
        drainOnce();
    }

    // ── транспорт ──
    private static void send(int op, String json) throws IOException {
        byte[] data = json.getBytes(StandardCharsets.UTF_8);
        ByteBuffer buf = ByteBuffer.allocate(8 + data.length).order(ByteOrder.LITTLE_ENDIAN);
        buf.putInt(op);
        buf.putInt(data.length);
        buf.put(data);
        buf.flip();
        if (winPipe != null) {
            winPipe.write(buf.array());
        } else if (unix != null) {
            while (buf.hasRemaining()) unix.write(buf);
        } else {
            throw new IOException("no transport");
        }
    }

    /** Прочитать один ответ и выбросить (чтобы не забивать буфер пайпа). */
    private static void drainOnce() {
        try {
            ByteBuffer head = ByteBuffer.allocate(8).order(ByteOrder.LITTLE_ENDIAN);
            if (winPipe != null) {
                byte[] h = new byte[8];
                winPipe.readFully(h);
                head.put(h).flip();
            } else if (unix != null) {
                readFully(head);
                head.flip();
            } else return;
            head.getInt(); // op
            int len = head.getInt();
            if (len > 0 && len < 1_000_000) {
                if (winPipe != null) {
                    winPipe.readFully(new byte[len]);
                } else {
                    readFully(ByteBuffer.allocate(len));
                }
            }
        } catch (Exception e) {
            close();
        }
    }

    private static void readFully(ByteBuffer buf) throws IOException {
        while (buf.hasRemaining()) {
            int n = unix.read(buf);
            if (n < 0) throw new IOException("closed");
        }
    }

    private static void close() {
        connected = false;
        try { if (unix != null) unix.close(); } catch (Exception ignored) {}
        try { if (winPipe != null) winPipe.close(); } catch (Exception ignored) {}
        unix = null;
        winPipe = null;
    }

    private DiscordPresence() {}
}
