package ruruka.suka.rurukasuka.render;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Разобранная геометрия .bbmodel (Blockbench): дерево костей с кубами, UV и встроенная текстура.
 * Чистые данные — без классов Minecraft. Рендер (сборка ModelPart + слой на игроке) — отдельным шагом.
 */
public final class BbModel {
    public int texWidth = 16;
    public int texHeight = 16;
    /** base64 PNG (без префикса data:...;base64,), либо null. */
    public String textureBase64;
    public final List<Bone> roots = new ArrayList<>();
    public final List<BbAnimation> animations = new ArrayList<>();

    public static final class Bone {
        public String name = "bone";
        public String uuid = "";
        public final float[] origin = {0, 0, 0};    // точка вращения кости
        public final float[] rotation = {0, 0, 0};  // градусы
        public final List<Cube> cubes = new ArrayList<>();
        public final List<Bone> children = new ArrayList<>();
    }

    public static final class Cube {
        public final float[] from = new float[3];
        public final float[] to = new float[3];
        public final float[] origin = {0, 0, 0};
        public final float[] rotation = {0, 0, 0};
        public float inflate = 0f;
        public final float[] uvOffset = {0, 0}; // box-UV смещение
        public final Map<String, Face> faces = new HashMap<>();
    }

    public static final class Face {
        public final float[] uv = new float[4]; // u1, v1, u2, v2
        public int texture = 0;
    }
}
