package milk.naovisual.modules.other;

import com.mojang.blaze3d.vertex.PoseStack;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.GroupSetting;
import milk.naovisual.core.setting.NumberSetting;
import net.minecraft.world.InteractionHand;

/** Положение, размер и скорость взмаха рук от первого лица. */
public class HandTweaksModule extends Module {
    private final NumberSetting mainX = new NumberSetting("X", "", 0, -1, 1, 0.01);
    private final NumberSetting mainY = new NumberSetting("Y", "", 0, -1, 1, 0.01);
    private final NumberSetting mainZ = new NumberSetting("Z", "", 0, -1, 1, 0.01);
    private final NumberSetting mainScale = new NumberSetting("Размер", "", 1, 0.3, 2, 0.05, "×");
    private final NumberSetting offX = new NumberSetting("X", "", 0, -1, 1, 0.01);
    private final NumberSetting offY = new NumberSetting("Y", "", 0, -1, 1, 0.01);
    private final NumberSetting offZ = new NumberSetting("Z", "", 0, -1, 1, 0.01);
    private final NumberSetting offScale = new NumberSetting("Размер", "", 1, 0.3, 2, 0.05, "×");
    private final GroupSetting main = add(new GroupSetting("Основная рука", "", mainX, mainY, mainZ, mainScale));
    private final GroupSetting off = add(new GroupSetting("Вторая рука", "", offX, offY, offZ, offScale));
    private final BooleanSetting customSwing = add(new BooleanSetting("Своя скорость взмаха", "", true));
    private final NumberSetting swing = add(new NumberSetting("Длительность взмаха", "Тиков (ваниль — 6)", 4, 1, 20, 1).visibleWhen(customSwing::on));
    private final BooleanSetting swingTilt = add(new BooleanSetting("Наклон при взмахе", "Лёгкий поворот руки во время удара", false));

    public HandTweaksModule() {
        super("HandTweaks", "Руки", "Положение, размер и скорость взмаха рук", ModuleCategory.OTHER);
    }

    public boolean customSwing() { return customSwing.on(); }
    public int swingDuration() { return swing.getInt(); }

    public void transform(PoseStack ps, InteractionHand hand, float swingProgress) {
        boolean mainHand = hand == InteractionHand.MAIN_HAND;
        float x = mainHand ? mainX.getFloat() : offX.getFloat();
        float y = mainHand ? mainY.getFloat() : offY.getFloat();
        float z = mainHand ? mainZ.getFloat() : offZ.getFloat();
        float s = mainHand ? mainScale.getFloat() : offScale.getFloat();
        ps.translate(x, y, z);
        if (s != 1f) ps.scale(s, s, s);
        if (swingTilt.on() && swingProgress > 0) {
            float a = (float) Math.sin(swingProgress * Math.PI) * 25f;
            ps.mulPose(new org.joml.Quaternionf().rotateZ((float) Math.toRadians(mainHand ? -a : a)));
        }
    }
}
