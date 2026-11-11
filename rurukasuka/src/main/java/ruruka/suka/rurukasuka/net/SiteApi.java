package ruruka.suka.rurukasuka.net;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import ruruka.suka.rurukasuka.RurukaSuka;
import ruruka.suka.rurukasuka.cosmetic.Cosmetic;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Клиент к API сайта: вход, баланс, каталог косметики, покупка. Вызывать в фоновом потоке. */
public final class SiteApi {

    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10)).build();

    public record Session(String token, String uuid, String nick, int balance, String skin, String skinModel, List<Integer> owned, List<Integer> equipped, Map<Integer,Integer> variants) {}
    public record CatalogItem(int id, String name, String category, int price, float scale, float offX, float offY, float offZ, List<Cosmetic.Variant> variants) {}
    public record PurchaseResult(int balance, List<Integer> owned) {}

    public static Session login(String email, String password) throws Exception {
        JsonObject body = new JsonObject();
        body.addProperty("email", email);
        body.addProperty("password", password);
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/login"))
                .timeout(Duration.ofSeconds(15))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body.toString())).build());
        if (res.statusCode() != 200) throw new ApiException(parseError(res.body(), res.statusCode()));
        return session(obj(res.body()), null);
    }

    public static Session me(String token) throws Exception {
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/me"))
                .timeout(Duration.ofSeconds(15))
                .header("Authorization", "Bearer " + token).GET().build());
        if (res.statusCode() != 200) throw new ApiException("Сессия истекла, войди заново");
        return session(obj(res.body()), token);
    }

    public static List<CatalogItem> cosmetics() throws Exception {
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/cosmetics"))
                .timeout(Duration.ofSeconds(15)).GET().build());
        if (res.statusCode() != 200) throw new ApiException("Каталог недоступен");
        List<CatalogItem> list = new ArrayList<>();
        JsonArray arr = obj(res.body()).getAsJsonArray("cosmetics");
        for (JsonElement e : arr) {
            JsonObject c = e.getAsJsonObject();
            List<Cosmetic.Variant> vars = new ArrayList<>();
            if (c.has("variants") && c.get("variants").isJsonArray()) {
                for (JsonElement ve : c.getAsJsonArray("variants")) {
                    JsonObject v = ve.getAsJsonObject();
                    vars.add(new Cosmetic.Variant(v.get("id").getAsInt(), str(v, "name"), str(v, "texture_url")));
                }
            }
            list.add(new CatalogItem(c.get("id").getAsInt(), c.get("name").getAsString(),
                    c.get("category").getAsString(), c.get("price").getAsInt(),
                    fnum(c, "scale", 1f), fnum(c, "off_x", 0f), fnum(c, "off_y", 0f), fnum(c, "off_z", 0f), vars));
        }
        return list;
    }

    public static PurchaseResult purchase(String token, int cosmeticId) throws Exception {
        JsonObject body = new JsonObject();
        body.addProperty("cosmetic_id", cosmeticId);
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/purchase"))
                .timeout(Duration.ofSeconds(15))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + token)
                .POST(HttpRequest.BodyPublishers.ofString(body.toString())).build());
        JsonObject o = obj(res.body());
        if (res.statusCode() != 200) throw new ApiException(purchaseError(o, res.statusCode()));
        return new PurchaseResult(o.get("balance").getAsInt(), intList(o.getAsJsonArray("owned")));
    }

    public static List<Integer> equip(String token, int cosmeticId, boolean equipped) throws Exception {
        JsonObject body = new JsonObject();
        body.addProperty("cosmetic_id", cosmeticId);
        body.addProperty("equipped", equipped);
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/equip"))
                .timeout(Duration.ofSeconds(15))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + token)
                .POST(HttpRequest.BodyPublishers.ofString(body.toString())).build());
        JsonObject o = obj(res.body());
        if (res.statusCode() != 200)
            throw new ApiException(o.has("error") ? o.get("error").getAsString() : "Ошибка " + res.statusCode());
        return intList(o.getAsJsonArray("equipped"));
    }

    public static Map<Integer,Integer> setVariant(String token, int cosmeticId, int variantId) throws Exception {
        JsonObject body = new JsonObject();
        body.addProperty("cosmetic_id", cosmeticId);
        if (variantId > 0) body.addProperty("variant_id", variantId);
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/variant"))
                .timeout(Duration.ofSeconds(15))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + token)
                .POST(HttpRequest.BodyPublishers.ofString(body.toString())).build());
        JsonObject o = obj(res.body());
        if (res.statusCode() != 200)
            throw new ApiException(o.has("error") ? o.get("error").getAsString() : "Ошибка " + res.statusCode());
        Map<Integer,Integer> map = new HashMap<>();
        if (o.has("variants") && o.get("variants").isJsonObject())
            for (Map.Entry<String,com.google.gson.JsonElement> en : o.getAsJsonObject("variants").entrySet()) {
                try { map.put(Integer.parseInt(en.getKey()), en.getValue().getAsInt()); } catch (Exception ignored) {}
            }
        return map;
    }

    // ── helpers ──
    // ── друзья / чат ──
    public record Friend(int id, String nick) {}
    public record Friends(List<Friend> friends, List<Friend> incoming, List<Friend> outgoing) {}
    public record Msg(int id, int from, String text, long ts) {}

    public static Friends friends(String token) throws Exception {
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/friends"))
                .timeout(Duration.ofSeconds(15))
                .header("Authorization", "Bearer " + token).GET().build());
        JsonObject o = obj(res.body());
        if (res.statusCode() != 200) throw new ApiException(apiErr(o, res.statusCode()));
        return new Friends(parseFriends(o, "friends"), parseFriends(o, "incoming"), parseFriends(o, "outgoing"));
    }

    private static List<Friend> parseFriends(JsonObject o, String key) {
        List<Friend> list = new ArrayList<>();
        if (o.has(key) && o.get(key).isJsonArray())
            for (JsonElement e : o.getAsJsonArray(key)) {
                JsonObject f = e.getAsJsonObject();
                list.add(new Friend(f.get("id").getAsInt(), str(f, "nick")));
            }
        return list;
    }

    public static void requestFriend(String token, String nick) throws Exception {
        JsonObject b = new JsonObject(); b.addProperty("nick", nick);
        postAuth("/api/friends/request", token, b);
    }

    public static void acceptFriend(String token, int userId) throws Exception {
        JsonObject b = new JsonObject(); b.addProperty("user_id", userId);
        postAuth("/api/friends/accept", token, b);
    }

    public static void removeFriend(String token, int userId) throws Exception {
        JsonObject b = new JsonObject(); b.addProperty("user_id", userId);
        postAuth("/api/friends/remove", token, b);
    }

    public static List<Msg> messages(String token, int withId, int after) throws Exception {
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri("/api/messages?with=" + withId + "&after=" + after))
                .timeout(Duration.ofSeconds(15))
                .header("Authorization", "Bearer " + token).GET().build());
        JsonObject o = obj(res.body());
        if (res.statusCode() != 200) throw new ApiException(apiErr(o, res.statusCode()));
        List<Msg> list = new ArrayList<>();
        if (o.has("messages") && o.get("messages").isJsonArray())
            for (JsonElement e : o.getAsJsonArray("messages")) {
                JsonObject m = e.getAsJsonObject();
                list.add(new Msg(m.get("id").getAsInt(), m.get("from").getAsInt(), str(m, "text"),
                        m.has("ts") ? m.get("ts").getAsLong() : 0));
            }
        return list;
    }

    public static int sendMessage(String token, int to, String text) throws Exception {
        JsonObject b = new JsonObject(); b.addProperty("to", to); b.addProperty("text", text);
        JsonObject o = postAuth("/api/messages", token, b);
        return o.has("id") ? o.get("id").getAsInt() : 0;
    }

    private static JsonObject postAuth(String path, String token, JsonObject body) throws Exception {
        HttpResponse<String> res = send(HttpRequest.newBuilder(uri(path))
                .timeout(Duration.ofSeconds(15))
                .header("Content-Type", "application/json")
                .header("Authorization", "Bearer " + token)
                .POST(HttpRequest.BodyPublishers.ofString(body.toString())).build());
        JsonObject o = obj(res.body());
        if (res.statusCode() != 200) throw new ApiException(apiErr(o, res.statusCode()));
        return o;
    }

    private static String apiErr(JsonObject o, int code) {
        return o.has("error") ? o.get("error").getAsString() : "Ошибка " + code;
    }

    private static Session session(JsonObject o, String tokenOverride) {
        String token = tokenOverride != null ? tokenOverride : str(o, "token");
        String nick = (o.has("nick") && !o.get("nick").isJsonNull()) ? o.get("nick").getAsString() : null;
        List<Integer> owned = (o.has("owned") && o.get("owned").isJsonArray())
                ? intList(o.getAsJsonArray("owned")) : new ArrayList<>();
        List<Integer> equipped = (o.has("equipped") && o.get("equipped").isJsonArray())
                ? intList(o.getAsJsonArray("equipped")) : new ArrayList<>();
        Map<Integer,Integer> variants = new HashMap<>();
        if (o.has("variants") && o.get("variants").isJsonObject()) {
            for (Map.Entry<String,com.google.gson.JsonElement> en : o.getAsJsonObject("variants").entrySet()) {
                try { variants.put(Integer.parseInt(en.getKey()), en.getValue().getAsInt()); } catch (Exception ignored) {}
            }
        }
        return new Session(token, str(o, "uuid"), nick, o.get("balance").getAsInt(), str(o, "skin"), str(o, "skin_model"), owned, equipped, variants);
    }

    private static List<Integer> intList(JsonArray arr) {
        List<Integer> out = new ArrayList<>();
        if (arr != null) for (JsonElement e : arr) out.add(e.getAsInt());
        return out;
    }

    private static float fnum(JsonObject o, String k, float def) {
        return (o.has(k) && !o.get(k).isJsonNull()) ? o.get(k).getAsFloat() : def;
    }

    private static String str(JsonObject o, String k) {
        return (o.has(k) && !o.get(k).isJsonNull()) ? o.get(k).getAsString() : null;
    }

    private static JsonObject obj(String body) { return JsonParser.parseString(body).getAsJsonObject(); }
    private static URI uri(String path) { return URI.create(RurukaSuka.SITE_URL + path); }
    private static HttpResponse<String> send(HttpRequest req) throws Exception {
        return HTTP.send(req, HttpResponse.BodyHandlers.ofString());
    }

    public static byte[] download(String url) throws Exception {
        HttpResponse<byte[]> res = HTTP.send(
                HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(20)).GET().build(),
                HttpResponse.BodyHandlers.ofByteArray());
        if (res.statusCode() != 200) throw new ApiException("Файл недоступен (" + res.statusCode() + ")");
        return res.body();
    }

    private static String parseError(String body, int code) {
        try {
            JsonObject o = obj(body);
            if (o.has("error")) {
                String e = o.get("error").getAsString();
                return e.equals("invalid_credentials") ? "Неверная почта или пароль" : e;
            }
        } catch (Exception ignored) {}
        return "Ошибка сервера (" + code + ")";
    }

    private static String purchaseError(JsonObject o, int code) {
        String e = o.has("error") ? o.get("error").getAsString() : "";
        return switch (e) {
            case "insufficient_funds" -> "Недостаточно руров";
            case "already_owned" -> "Уже куплено";
            case "unauthorized" -> "Войди в аккаунт";
            case "not_found" -> "Косметика не найдена";
            default -> "Ошибка сервера (" + code + ")";
        };
    }

    public static final class ApiException extends RuntimeException {
        public ApiException(String m) { super(m); }
    }

    private SiteApi() {}
}
