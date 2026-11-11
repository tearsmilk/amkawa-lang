package ruruka.suka.rurukasuka.render;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.util.HashMap;
import java.util.Map;

/** Парсер формата Blockbench .bbmodel в {@link BbModel}. */
public final class BbParser {

    public static BbModel parse(String json) {
        JsonObject root = JsonParser.parseString(json).getAsJsonObject();
        BbModel model = new BbModel();

        if (root.has("resolution")) {
            JsonObject res = root.getAsJsonObject("resolution");
            model.texWidth = getInt(res, "width", 16);
            model.texHeight = getInt(res, "height", 16);
        }

        // текстура: первый источник data:...;base64,
        if (root.has("textures") && root.get("textures").isJsonArray()) {
            for (JsonElement te : root.getAsJsonArray("textures")) {
                JsonObject t = te.getAsJsonObject();
                String src = getStr(t, "source", "");
                if (src.startsWith("data:") && src.contains(",")) {
                    model.textureBase64 = src.substring(src.indexOf(',') + 1);
                    break;
                }
            }
        }

        // элементы по uuid
        Map<String, JsonObject> elements = new HashMap<>();
        if (root.has("elements") && root.get("elements").isJsonArray()) {
            for (JsonElement ee : root.getAsJsonArray("elements")) {
                JsonObject e = ee.getAsJsonObject();
                if (e.has("uuid")) elements.put(e.get("uuid").getAsString(), e);
            }
        }

        // группы (кости): в формате 5.0 их трансформы (origin/rotation/name) лежат в отдельном
        // массиве "groups", а outliner хранит только иерархию. Читаем отсюда по uuid.
        Map<String, JsonObject> groups = new HashMap<>();
        if (root.has("groups") && root.get("groups").isJsonArray()) {
            for (JsonElement ge : root.getAsJsonArray("groups")) {
                if (ge.isJsonObject() && ge.getAsJsonObject().has("uuid"))
                    groups.put(ge.getAsJsonObject().get("uuid").getAsString(), ge.getAsJsonObject());
            }
        }

        // дерево outliner
        if (root.has("outliner") && root.get("outliner").isJsonArray()) {
            for (JsonElement node : root.getAsJsonArray("outliner")) {
                if (node.isJsonObject()) {
                    model.roots.add(parseBone(node.getAsJsonObject(), elements, groups));
                } else if (node.isJsonPrimitive()) {
                    // куб прямо в корне — заворачиваем в неявную кость
                    JsonObject e = elements.get(node.getAsString());
                    if (e != null) {
                        BbModel.Bone b = new BbModel.Bone();
                        b.name = "root";
                        BbModel.Cube c = parseCube(e);
                        if (c != null) b.cubes.add(c);
                        model.roots.add(b);
                    }
                }
            }
        }
        parseAnimations(root, model);
        return model;
    }

    private static void parseAnimations(JsonObject root, BbModel model) {
        if (!root.has("animations") || !root.get("animations").isJsonArray()) return;
        for (JsonElement ae : root.getAsJsonArray("animations")) {
            if (!ae.isJsonObject()) continue;
            JsonObject a = ae.getAsJsonObject();
            BbAnimation anim = new BbAnimation();
            anim.name = getStr(a, "name", "anim");
            anim.length = (float) getDouble(a, "length", 0);
            anim.loop = !"once".equals(getStr(a, "loop", "loop"));
            if (a.has("animators") && a.get("animators").isJsonObject()) {
                for (Map.Entry<String, JsonElement> en : a.getAsJsonObject("animators").entrySet()) {
                    if (!en.getValue().isJsonObject()) continue;
                    JsonObject animator = en.getValue().getAsJsonObject();
                    BbAnimation.BoneAnim ba = new BbAnimation.BoneAnim();
                    if (animator.has("keyframes") && animator.get("keyframes").isJsonArray()) {
                        for (JsonElement ke : animator.getAsJsonArray("keyframes")) {
                            if (!ke.isJsonObject()) continue;
                            JsonObject kf = ke.getAsJsonObject();
                            BbAnimation.Keyframe k = new BbAnimation.Keyframe();
                            k.time = (float) getDouble(kf, "time", 0);
                            k.interp = getStr(kf, "interpolation", "linear");
                            if (kf.has("data_points") && kf.get("data_points").isJsonArray()
                                    && kf.getAsJsonArray("data_points").size() > 0
                                    && kf.getAsJsonArray("data_points").get(0).isJsonObject()) {
                                JsonObject dp = kf.getAsJsonArray("data_points").get(0).getAsJsonObject();
                                k.x = parseVal(dp, "x");
                                k.y = parseVal(dp, "y");
                                k.z = parseVal(dp, "z");
                            }
                            switch (getStr(kf, "channel", "")) {
                                case "rotation" -> ba.rotation.add(k);
                                case "position" -> ba.position.add(k);
                                case "scale" -> ba.scale.add(k);
                                default -> {}
                            }
                        }
                    }
                    ba.rotation.sort(java.util.Comparator.comparingDouble(x -> x.time));
                    ba.position.sort(java.util.Comparator.comparingDouble(x -> x.time));
                    ba.scale.sort(java.util.Comparator.comparingDouble(x -> x.time));
                    anim.bones.put(en.getKey(), ba);
                }
            }
            model.animations.add(anim);
        }
    }

    private static float parseVal(JsonObject o, String key) {
        if (!o.has(key) || o.get(key).isJsonNull()) return 0f;
        JsonElement e = o.get(key);
        try {
            if (e.isJsonPrimitive() && e.getAsJsonPrimitive().isString()) {
                String str = e.getAsString().trim();
                return str.isEmpty() ? 0f : Float.parseFloat(str);
            }
            return e.getAsFloat();
        } catch (Exception ex) {
            return 0f; // molang-выражение — пока 0
        }
    }

    private static BbModel.Bone parseBone(JsonObject node, Map<String, JsonObject> elements, Map<String, JsonObject> groups) {
        BbModel.Bone bone = new BbModel.Bone();
        bone.uuid = getStr(node, "uuid", "");
        JsonObject src = groups.getOrDefault(bone.uuid, node); // трансформ группы из массива groups[]
        bone.name = getStr(src, "name", "bone");
        readVec(src, "origin", bone.origin);
        readVec(src, "rotation", bone.rotation);
        if (node.has("children") && node.get("children").isJsonArray()) {
            for (JsonElement ch : node.getAsJsonArray("children")) {
                if (ch.isJsonObject()) {
                    bone.children.add(parseBone(ch.getAsJsonObject(), elements, groups));
                } else if (ch.isJsonPrimitive()) {
                    JsonObject e = elements.get(ch.getAsString());
                    BbModel.Cube c = e != null ? parseCube(e) : null;
                    if (c != null) bone.cubes.add(c);
                }
            }
        }
        return bone;
    }

    private static BbModel.Cube parseCube(JsonObject e) {
        BbModel.Cube c = new BbModel.Cube();
        readVec(e, "from", c.from);
        readVec(e, "to", c.to);
        readVec(e, "origin", c.origin);
        readVec(e, "rotation", c.rotation);
        c.inflate = (float) getDouble(e, "inflate", 0);
        readVec(e, "uv_offset", c.uvOffset);
        if (e.has("faces") && e.get("faces").isJsonObject()) {
            JsonObject faces = e.getAsJsonObject("faces");
            for (Map.Entry<String, JsonElement> fe : faces.entrySet()) {
                if (!fe.getValue().isJsonObject()) continue;
                JsonObject fo = fe.getValue().getAsJsonObject();
                BbModel.Face face = new BbModel.Face();
                if (fo.has("uv") && fo.get("uv").isJsonArray()) {
                    JsonArray uv = fo.getAsJsonArray("uv");
                    for (int i = 0; i < 4 && i < uv.size(); i++) face.uv[i] = uv.get(i).getAsFloat();
                }
                face.texture = getInt(fo, "texture", 0);
                c.faces.put(fe.getKey(), face);
            }
        }
        return c;
    }

    private static void readVec(JsonObject o, String key, float[] out) {
        if (o.has(key) && o.get(key).isJsonArray()) {
            JsonArray a = o.getAsJsonArray(key);
            for (int i = 0; i < out.length && i < a.size(); i++) out[i] = a.get(i).getAsFloat();
        }
    }

    private static int getInt(JsonObject o, String k, int def) {
        return (o.has(k) && !o.get(k).isJsonNull()) ? o.get(k).getAsInt() : def;
    }

    private static double getDouble(JsonObject o, String k, double def) {
        return (o.has(k) && !o.get(k).isJsonNull()) ? o.get(k).getAsDouble() : def;
    }

    private static String getStr(JsonObject o, String k, String def) {
        return (o.has(k) && !o.get(k).isJsonNull()) ? o.get(k).getAsString() : def;
    }

    private BbParser() {}
}
