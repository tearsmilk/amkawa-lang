package milk.naovisual.modules.world;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;

/** Выброшенные предметы лежат на земле плашмя и не крутятся (рендер — ItemEntityRendererMixin). */
public class ItemPhysicsModule extends Module {
    public ItemPhysicsModule() {
        super("ItemPhysics", "Физика предметов", "Предметы на земле лежат плашмя, без вращения и подпрыгивания", ModuleCategory.WORLD);
    }
}
