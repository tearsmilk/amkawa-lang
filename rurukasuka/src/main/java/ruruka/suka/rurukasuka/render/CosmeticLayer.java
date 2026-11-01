package ruruka.suka.rurukasuka.render;

import com.mojang.blaze3d.vertex.PoseStack;
import ruruka.suka.rurukasuka.account.RurukaAccount;
import ruruka.suka.rurukasuka.cosmetic.CosmeticCategory;
import net.minecraft.client.Minecraft;
import net.minecraft.client.model.player.PlayerModel;
import net.minecraft.resources.Identifier;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.entity.LivingEntityRenderer;
import net.minecraft.client.renderer.entity.RenderLayerParent;
import net.minecraft.client.renderer.entity.layers.RenderLayer;
import net.minecraft.client.renderer.entity.state.AvatarRenderState;
import net.minecraft.client.renderer.rendertype.RenderTypes;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;

/**
 * Слой рендера косметики на игроке (submit-система 1.21.11).
 * Пока — только свой игрок (чужие через /api/equipped — этап 5).
 */
public class CosmeticLayer extends RenderLayer<AvatarRenderState, PlayerModel> {

    public CosmeticLayer(RenderLayerParent<AvatarRenderState, PlayerModel> parent) {
        super(parent);
    }

    @Override
    public void submit(PoseStack pose, SubmitNodeCollector collector, int light,
                       AvatarRenderState state, float yRot, float xRot) {
        if (state.isInvisible) return;
        var level = Minecraft.getInstance().level;
        if (level == null) return;
        Entity e = level.getEntity(state.id);
        if (!(e instanceof Player player)) return;
        if (player != Minecraft.getInstance().player) return; // пока только сам игрок

        int overlay = LivingEntityRenderer.getOverlayCoords(state, 0.0F);
        for (int id : RurukaAccount.LOCAL.equippedIds()) {
            CosmeticManager.ensure(id);
            BakedCosmetic baked = CosmeticManager.get(id);
            if (baked == null) continue;
            Identifier tex = CosmeticManager.textureFor(id);   // вариант-цвет или базовая текстура
            if (tex == null) continue;
            pose.pushPose();
            attach(pose, baked.category());
            final BbModel bb = baked.model();
            float[] tf = CosmeticManager.transformOf(id);   // живой трансформ из каталога (real-time)
            final float scaleF = tf[0], oxF = tf[1], oyF = tf[2], ozF = tf[3];
            final int lightF = light, overlayF = overlay;
            collector.submitCustomGeometry(pose, RenderTypes.entityCutoutNoCull(tex),
                    (p, vc) -> CosmeticRenderer.emit(bb, p, vc, lightF, overlayF, scaleF, oxF, oyF, ozF));
            pose.popPose();
        }
    }

    private void attach(PoseStack pose, CosmeticCategory cat) {
        // Ауры — вокруг игрока (корень модели): не привязываем к части тела,
        // иначе поза приседа/сидения (body) тянет ауру за собой.
        if (cat == CosmeticCategory.AURAS) return;
        PlayerModel m = getParentModel();
        ModelPart part = switch (cat) {
            case HATS, PETS -> m.head;
            case WINGS, BACK, COSTUMES, AURAS -> m.body;   // AURAS сюда не дойдёт (обработано выше)
            case ARMS -> m.rightArm;
            case LEGS -> m.rightLeg;
        };
        part.translateAndRotate(pose);
    }
}
