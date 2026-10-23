package ruruka.suka.rurukasuka.render;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Анимация из .bbmodel: длина, цикл, и по костям (uuid) — кейфреймы каналов rotation/position/scale. */
public final class BbAnimation {
    public String name = "anim";
    public float length = 0f;
    public boolean loop = true;
    public final Map<String, BoneAnim> bones = new HashMap<>(); // bone uuid -> anim

    public static final class BoneAnim {
        public final List<Keyframe> rotation = new ArrayList<>();
        public final List<Keyframe> position = new ArrayList<>();
        public final List<Keyframe> scale = new ArrayList<>();
    }

    public static final class Keyframe {
        public float time;
        public float x, y, z;
        public String interp = "linear";
    }
}
