package milk.naovisual;

import net.minecraft.client.Minecraft;
import net.minecraft.resources.Identifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Общие константы и доступ к клиенту. */
public final class NaoVisual {
    public static final String MOD_ID = "naovisual";
    public static final String NAME = "NaoVisual";
    public static final Logger LOGGER = LoggerFactory.getLogger(NAME);

    private NaoVisual() {}

    public static Identifier id(String path) {
        return Identifier.fromNamespaceAndPath(MOD_ID, path);
    }

    public static Minecraft mc() {
        return Minecraft.getInstance();
    }

    public static String version() {
        return net.fabricmc.loader.api.FabricLoader.getInstance().getModContainer(MOD_ID)
                .map(c -> c.getMetadata().getVersion().getFriendlyString()).orElse("dev");
    }
}
