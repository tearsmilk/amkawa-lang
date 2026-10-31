package milk.naovisual.core.discord;

import com.google.gson.JsonObject;
import milk.naovisual.NaoVisual;

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
import java.nio.file.Paths;
import java.util.UUID;

/**
 * Минимальный клиент Discord IPC (без сторонних библиотек): рукопожатие и SET_ACTIVITY.
 * Linux/macOS — unix-сокет discord-ipc-N, Windows — именованный канал \\.\pipe\discord-ipc-N.
 */
public final class DiscordRpc {
    private static final int OP_HANDSHAKE = 0, OP_FRAME = 1, OP_CLOSE = 2;
    private SocketChannel socket;
    private RandomAccessFile pipe;
    private boolean connected;
    private long lastAttempt;
    private String clientId;

    public boolean isConnected() { return connected; }

    public synchronized void connect(String clientId) {
        if (connected && clientId.equals(this.clientId)) return;
        close();
        if (System.currentTimeMillis() - lastAttempt < 10_000) return;
        lastAttempt = System.currentTimeMillis();
        this.clientId = clientId;
        try {
            open();
            JsonObject hs = new JsonObject();
            hs.addProperty("v", 1);
            hs.addProperty("client_id", clientId);
            write(OP_HANDSHAKE, hs.toString());
            connected = true;
            NaoVisual.LOGGER.info("Discord RPC подключён");
        } catch (Exception e) {
            NaoVisual.LOGGER.debug("Discord RPC недоступен: {}", e.toString());
            close();
        }
    }

    private void open() throws IOException {
        String os = System.getProperty("os.name", "").toLowerCase();
        if (os.contains("win")) {
            IOException last = null;
            for (int i = 0; i < 10; i++) {
                try {
                    pipe = new RandomAccessFile("\\\\.\\pipe\\discord-ipc-" + i, "rw");
                    return;
                } catch (IOException e) { last = e; }
            }
            throw last == null ? new IOException("нет канала discord-ipc") : last;
        }
        String[] dirs = {System.getenv("XDG_RUNTIME_DIR"), System.getenv("TMPDIR"), System.getenv("TMP"), System.getenv("TEMP"), "/tmp"};
        for (String d : dirs) {
            if (d == null || d.isBlank()) continue;
            for (String sub : new String[]{"", "app/com.discordapp.Discord/", "snap.discord/"}) {
                for (int i = 0; i < 10; i++) {
                    Path p = Paths.get(d, sub + "discord-ipc-" + i);
                    if (!Files.exists(p)) continue;
                    try {
                        SocketChannel ch = SocketChannel.open(StandardProtocolFamily.UNIX);
                        ch.connect(UnixDomainSocketAddress.of(p));
                        socket = ch;
                        return;
                    } catch (IOException ignored) {}
                }
            }
        }
        throw new IOException("сокет discord-ipc не найден");
    }

    private void write(int op, String json) throws IOException {
        byte[] data = json.getBytes(StandardCharsets.UTF_8);
        ByteBuffer buf = ByteBuffer.allocate(8 + data.length).order(ByteOrder.LITTLE_ENDIAN);
        buf.putInt(op).putInt(data.length).put(data).flip();
        if (socket != null) {
            while (buf.hasRemaining()) socket.write(buf);
        } else if (pipe != null) {
            pipe.write(buf.array());
        } else throw new IOException("не подключено");
    }

    /** Обновить активность. Любое из полей может быть null. */
    public synchronized void setActivity(String details, String state, String largeImage, String largeText, String smallImage, String smallText, long startMs) {
        if (!connected) return;
        try {
            JsonObject activity = new JsonObject();
            if (details != null && !details.isBlank()) activity.addProperty("details", details);
            if (state != null && !state.isBlank()) activity.addProperty("state", state);
            if (startMs > 0) {
                JsonObject ts = new JsonObject();
                ts.addProperty("start", startMs / 1000);
                activity.add("timestamps", ts);
            }
            JsonObject assets = new JsonObject();
            if (largeImage != null && !largeImage.isBlank()) assets.addProperty("large_image", largeImage);
            if (largeText != null && !largeText.isBlank()) assets.addProperty("large_text", largeText);
            if (smallImage != null && !smallImage.isBlank()) assets.addProperty("small_image", smallImage);
            if (smallText != null && !smallText.isBlank()) assets.addProperty("small_text", smallText);
            if (!assets.isEmpty()) activity.add("assets", assets);

            JsonObject args = new JsonObject();
            args.addProperty("pid", (int) ProcessHandle.current().pid());
            args.add("activity", activity);
            JsonObject cmd = new JsonObject();
            cmd.addProperty("cmd", "SET_ACTIVITY");
            cmd.add("args", args);
            cmd.addProperty("nonce", UUID.randomUUID().toString());
            write(OP_FRAME, cmd.toString());
        } catch (IOException e) {
            NaoVisual.LOGGER.debug("Discord RPC: соединение потеряно");
            close();
        }
    }

    public synchronized void clearActivity() {
        if (!connected) return;
        try {
            JsonObject args = new JsonObject();
            args.addProperty("pid", (int) ProcessHandle.current().pid());
            JsonObject cmd = new JsonObject();
            cmd.addProperty("cmd", "SET_ACTIVITY");
            cmd.add("args", args);
            cmd.addProperty("nonce", UUID.randomUUID().toString());
            write(OP_FRAME, cmd.toString());
        } catch (IOException ignored) {}
    }

    public synchronized void close() {
        if (connected) {
            try { write(OP_CLOSE, "{}"); } catch (IOException ignored) {}
        }
        connected = false;
        try { if (socket != null) socket.close(); } catch (IOException ignored) {}
        try { if (pipe != null) pipe.close(); } catch (IOException ignored) {}
        socket = null;
        pipe = null;
    }
}
