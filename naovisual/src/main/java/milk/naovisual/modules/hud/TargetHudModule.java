package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Projection;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Friends;
import milk.naovisual.core.util.Targets;
import milk.naovisual.core.util.TextUtil;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.PlayerFaceRenderer;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/** Карточка цели: голова, имя, здоровье с анимацией, дистанция; частицы при ударе; якорь над целью. */
public class TargetHudModule extends HudModule {
    private final SelectSetting anchor = add(new SelectSetting("Якорь", "Где рисовать карточку", "Экран", "Экран", "Над целью"));
    private final BooleanSetting particles = add(new BooleanSetting("Частицы", "Искры по карточке при ударе", true));
    private final BooleanSetting hurtFlash = add(new BooleanSetting("Вспышка урона", "Карточка краснеет при уроне", true));
    private final BooleanSetting showArmor = add(new BooleanSetting("Броня", "", true));
    private final BooleanSetting showDistance = add(new BooleanSetting("Дистанция", "", true));
    private final NumberSetting fadeTime = add(new NumberSetting("Время показа", "Секунд после последнего удара", 4, 1, 10, 0.5, " с"));
    private final ColorSetting healthColor = add(new ColorSetting("Цвет здоровья", "Пусто — по проценту", 0x00000000));
    private final Anim hp = new Anim(1f, 9f), appear = new Anim(0f, 12f);
    private final List<float[]> sparks = new ArrayList<>();
    private final Random rng = new Random();
    private LivingEntity shownTarget;
    private int lastHurt;

    public TargetHudModule() {
        super("TargetHud", "Цель", "Информация о цели: голова, ник, здоровье, дистанция, вспышка урона", 0.5 + 0.03, 0.5 + 0.05);
    }

    @Override public boolean defaultEnabled() { return true; }

    @Override
    public void onAttack(net.minecraft.world.entity.Entity e) {
        if (!particles.on()) return;
        for (int i = 0; i < 10; i++) sparks.add(new float[]{rng.nextFloat() * 120, rng.nextFloat() * 36, (rng.nextFloat() - 0.5f) * 3, -rng.nextFloat() * 3 - 1, 1f});
    }

    @Override
    public void onTick() {
        for (int i = sparks.size() - 1; i >= 0; i--) {
            float[] s = sparks.get(i);
            s[0] += s[2]; s[1] += s[3]; s[3] += 0.25f; s[4] -= 0.06f;
            if (s[4] <= 0) sparks.remove(i);
        }
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        LivingEntity target = Targets.current();
        if (target == null && Targets.lastAttacked() == null) shownTarget = editor ? mc().player : null;
        if (target != null) shownTarget = target;
        boolean visible = shownTarget != null && (editor || target != null);
        appear.to(visible ? 1f : 0f);
        float a = appear.get();
        int w = 120, h = 36;
        setSize(w, h);
        if (a < 0.02f || shownTarget == null) return;
        if (anchor.is("Над целью") && !editor) {
            float[] s = Projection.toScreen(new Vec3(shownTarget.getX(), shownTarget.getY() + shownTarget.getBbHeight() + 0.6, shownTarget.getZ()));
            if (s == null) return;
            // переносим в координаты над целью относительно нашей позиции
            g.pose().translate((s[0] - x()) / scale() - w / 2f, (s[1] - y()) / scale() - h);
        }
        var t = ThemeManager.current();
        int alpha = Math.round(255 * a);
        LivingEntity e = shownTarget;
        float frac = Math.max(0, Math.min(1, e.getHealth() / Math.max(1f, e.getMaxHealth())));
        hp.to(frac);
        boolean hurt = hurtFlash.on() && e.hurtTime > 0;
        int panel = hurt ? ColorUtil.lerp(t.panel, t.danger, 0.35f) : t.panel;
        Render2D.roundedRect(g, 0, 0, w, h, 5, ColorUtil.withAlpha(panel, Math.min(alpha, 235)));
        Render2D.roundedOutline(g, 0, 0, w, h, 5, ColorUtil.withAlpha(Friends.isFriend(e) ? t.success : t.border, alpha));
        if (e instanceof AbstractClientPlayer p) PlayerFaceRenderer.draw(g, p.getSkin(), 4, 4, 28);
        else {
            Render2D.roundedRect(g, 4, 4, 28, 28, 4, ColorUtil.withAlpha(t.panelAlt, alpha));
            Render2D.textCentered(g, e.getType().getDescription().getString().substring(0, 1), 18, 14, ColorUtil.withAlpha(t.text, alpha), false);
        }
        String name = e.getDisplayName().getString();
        Render2D.text(g, Render2D.trim(name, w - 40), 36, 4, ColorUtil.withAlpha(t.text, alpha));
        String hpText = TextUtil.fixed(e.getHealth() + e.getAbsorptionAmount(), 1) + " ♥";
        Render2D.textRight(g, hpText, w - 4, 4, ColorUtil.withAlpha(ColorUtil.health(frac), alpha), false);
        int barColor = ColorUtil.alpha(healthColor.get()) == 0 ? ColorUtil.health(hp.get()) : healthColor.color();
        Render2D.bar(g, 36, 15, w - 40, 5, hp.get(), ColorUtil.withAlpha(t.border, alpha / 2), ColorUtil.withAlpha(barColor, alpha));
        StringBuilder info = new StringBuilder();
        if (showDistance.on() && mc().player != null) info.append(TextUtil.fixed(mc().player.distanceTo(e), 1)).append(" м");
        if (showArmor.on() && e.getArmorValue() > 0) { if (!info.isEmpty()) info.append("  "); info.append("Броня ").append(e.getArmorValue()); }
        if (e.hurtTime > 0) { if (!info.isEmpty()) info.append("  "); info.append("Урон!"); }
        Render2D.text(g, info.toString(), 36, 24, ColorUtil.withAlpha(t.textMuted, alpha));
        if (particles.on()) {
            for (float[] s : sparks) {
                int c = ColorUtil.withAlpha(t.accent, Math.round(255 * Math.max(0, s[4]) * a));
                g.fill(Math.round(s[0]), Math.round(s[1]), Math.round(s[0]) + 2, Math.round(s[1]) + 2, c);
            }
        }
        lastHurt = e.hurtTime;
    }
}
