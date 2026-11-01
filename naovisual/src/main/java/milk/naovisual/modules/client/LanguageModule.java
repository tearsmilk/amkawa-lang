package milk.naovisual.modules.client;

import milk.naovisual.core.module.Language;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.SelectSetting;

/** Язык названий модулей и категорий. */
public class LanguageModule extends Module {
    private final SelectSetting language = add(new SelectSetting("Язык названий", "Названия модулей и категорий", "Русский", "Русский", "English").onChange(v -> Language.setEnglish(v.equals("English"))));

    public LanguageModule() {
        super("Language", "Язык", "Русские или английские названия модулей", ModuleCategory.CLIENT);
    }

    @Override public boolean defaultEnabled() { return true; }
    @Override public void onEnable() { Language.setEnglish(language.is("English")); }
    @Override public void onDisable() { Language.setEnglish(false); }
}
