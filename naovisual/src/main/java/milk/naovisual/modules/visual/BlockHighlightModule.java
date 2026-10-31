package milk.naovisual.modules.visual;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.render.Render3D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.NumberSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.util.ColorUtil;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Подсветка блока под прицелом: заливка, рамка, грань. */
public class BlockHighlightModule extends Module {
    private final SelectSetting mode = add(new SelectSetting("Режим", "", "Блок", "Блок", "Грань"));
    private final BooleanSetting fill = add(new BooleanSetting("Заливка", "", true));
    private final BooleanSetting outline = add(new BooleanSetting("Рамка", "", true));
    private final NumberSetting expand = add(new NumberSetting("Отступ", "Насколько увеличить рамку", 0.002, 0.0, 0.05, 0.001));
    private final ColorSetting color = add(new ColorSetting("Цвет", "", 0x66D97757));
    private final BooleanSetting pulse = add(new BooleanSetting("Пульсация", "", true));

    public BlockHighlightModule() {
        super("BlockHighlight", "Подсветка блока", "Подсвечивает блок под прицелом заливкой и рамкой", ModuleCategory.VISUALS);
        color.setMode(ColorSetting.Mode.THEME);
    }

    @Override
    public void onRenderWorld(WorldRenderContext ctx) {
        HitResult hit = mc().hitResult;
        if (!(hit instanceof BlockHitResult bh) || hit.getType() != HitResult.Type.BLOCK || mc().level == null) return;
        BlockPos pos = bh.getBlockPos();
        VoxelShape shape = mc().level.getBlockState(pos).getShape(mc().level, pos);
        if (shape.isEmpty()) return;
        AABB box = shape.bounds().move(pos).inflate(expand.getFloat());
        if (mode.is("Грань")) {
            double e = 0.002;
            box = switch (bh.getDirection()) {
                case UP -> new AABB(box.minX, box.maxY - e, box.minZ, box.maxX, box.maxY + e, box.maxZ);
                case DOWN -> new AABB(box.minX, box.minY - e, box.minZ, box.maxX, box.minY + e, box.maxZ);
                case NORTH -> new AABB(box.minX, box.minY, box.minZ - e, box.maxX, box.maxY, box.minZ + e);
                case SOUTH -> new AABB(box.minX, box.minY, box.maxZ - e, box.maxX, box.maxY, box.maxZ + e);
                case WEST -> new AABB(box.minX - e, box.minY, box.minZ, box.minX + e, box.maxY, box.maxZ);
                case EAST -> new AABB(box.maxX - e, box.minY, box.minZ, box.maxX + e, box.maxY, box.maxZ);
            };
        }
        int c = color.color();
        if (pulse.on()) {
            float f = 0.75f + 0.25f * (float) Math.sin(System.currentTimeMillis() / 300.0);
            c = ColorUtil.withAlpha(c, Math.round(ColorUtil.alpha(c) * f));
        }
        Render3D.begin(ctx);
        if (fill.on()) Render3D.filledBox(ctx.matrices(), Render3D.quads(ctx), box, c);
        if (outline.on()) Render3D.lineBox(ctx.matrices(), Render3D.lines(ctx), box, ColorUtil.withAlpha(c, 255));
        Render3D.end(ctx);
    }
}
