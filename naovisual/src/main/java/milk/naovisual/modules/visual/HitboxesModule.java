package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.MultiSelectSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Friends;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

import java.util.List;

/** Хитбоксы сущностей: рамка, заливка, линия взгляда. */
public class HitboxesModule extends Module {
    private final MultiSelectSetting targets = add(new MultiSelectSetting("Кого", "", List.of("Игроки", "Мобы", "Предметы", "Остальное"), "Игроки", "Мобы"));
    private final BooleanSetting fill = add(new BooleanSetting("Заливка", "", true));
    private final BooleanSetting eyeLine = add(new BooleanSetting("Линия взгляда", "", false));
    private final NumberSetting range = add(new NumberSetting("Дальность", "", 48, 8, 128, 1, " бл"));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xFFFFFFFF));
    private final ColorSetting friendColor = add(new ColorSetting("Цвет друзей", "", 0xFF5FB36A));
    private final NumberSetting fillAlpha = add(new NumberSetting("Прозрачность заливки", "", 40, 0, 255, 1).visibleWhen(fill::on));

    public HitboxesModule() {
        super("Hitboxes", "Хитбоксы", "Рамки вокруг сущностей с заливкой и линией взгляда", ModuleCategory.VISUALS);
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        if (mc().level == null || mc().player == null) return;
        float partial = Render3D.partial();
        double r2 = range.get() * range.get();
        Render3D.begin(ctx);
        var ps = ctx.matrices();
        var lines = Render3D.lines(ctx);
        var quads = Render3D.quads(ctx);
        for (Entity e : mc().level.entitiesForRendering()) {
            if (e == mc().player && mc().options.getCameraType().isFirstPerson()) continue;
            if (!matches(e) || mc().player.distanceToSqr(e) > r2) continue;
            int c = Friends.isFriend(e) ? friendColor.color() : color.color();
            AABB box = Render3D.lerpBox(e, partial);
            Render3D.lineBox(ps, lines, box, c);
            if (fill.on()) Render3D.filledBox(ps, quads, box, ColorUtil.withAlpha(c, fillAlpha.getInt()));
            if (eyeLine.on() && e instanceof LivingEntity le) {
                Vec3 eye = Render3D.lerpPos(e, partial).add(0, le.getEyeHeight(), 0);
                Vec3 look = le.getViewVector(partial).scale(2);
                Render3D.line(ps, lines, eye.x, eye.y, eye.z, eye.x + look.x, eye.y + look.y, eye.z + look.z, 0xFFE05A4F);
            }
        }
        Render3D.end(ctx);
    }

    private boolean matches(Entity e) {
        if (e instanceof Player) return targets.has("Игроки");
        if (e instanceof LivingEntity) return targets.has("Мобы");
        if (e instanceof ItemEntity) return targets.has("Предметы");
        return targets.has("Остальное");
    }
}
