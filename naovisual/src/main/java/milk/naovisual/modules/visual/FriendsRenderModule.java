package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Friends;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Друзья в мире: рамка, кольцо под ногами или маркер над головой. */
public class FriendsRenderModule extends Module {
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Кольцо", "Кольцо", "Рамка", "Маркер"));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0xCC5FB36A));

    public FriendsRenderModule() {
        super("FriendsRender", "Друзья", "Подсветка друзей в мире: кольцо, рамка или маркер", ModuleCategory.VISUALS);
    }

    @Override public boolean defaultEnabled() { return true; }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        if (mc().level == null) return;
        float partial = Render3D.partial();
        Render3D.begin(ctx);
        var ps = ctx.matrices();
        for (Player p : mc().level.players()) {
            if (p == mc().player || !Friends.isFriend(p) || !p.isAlive()) continue;
            int c = color.color();
            Vec3 pos = Render3D.lerpPos(p, partial);
            switch (style.get()) {
                case "Рамка" -> {
                    AABB b = Render3D.lerpBox(p, partial).inflate(0.05);
                    Render3D.lineBox(ps, Render3D.lines(ctx), b, c);
                    Render3D.filledBox(ps, Render3D.quads(ctx), b, ColorUtil.withAlpha(c, ColorUtil.alpha(c) / 5));
                }
                case "Маркер" -> {
                    double y = pos.y + p.getBbHeight() + 0.4 + Math.sin(System.currentTimeMillis() / 400.0) * 0.08;
                    Render3D.billboard(ps, Render3D.quads(ctx), ctx, pos.x, y, pos.z, 0.25f, c);
                    Render3D.billboard(ps, Render3D.quads(ctx), ctx, pos.x, y - 0.18, pos.z, 0.12f, c);
                }
                default -> {
                    double spin = (System.currentTimeMillis() % 2000) / 2000.0;
                    Render3D.filledRing(ps, Render3D.quads(ctx), pos.x, pos.y + 0.02, pos.z, 0.45, 0.6, 32, ColorUtil.withAlpha(c, 40), c);
                    double a = spin * Math.PI * 2;
                    Render3D.billboard(ps, Render3D.quads(ctx), ctx, pos.x + Math.cos(a) * 0.55, pos.y + 0.05, pos.z + Math.sin(a) * 0.55, 0.1f, ColorUtil.withAlpha(c, 255));
                }
            }
        }
        Render3D.end(ctx);
    }
}
