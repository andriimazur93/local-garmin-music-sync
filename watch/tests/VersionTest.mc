import Toybox.Application;
import Toybox.WatchUi;

(:test)
function testSettingsShowsReadOnlyBuildVersion(logger) {
    var menu = new ProviderSettingsMenu();
    var item = menu.getItem(2);
    if (!item.getLabel().equals("Version") ||
        !item.getSubLabel().equals(Application.loadResource(Rez.Strings.AppVersion))) {
        logger.error("Settings must show the generated app version");
        return false;
    }
    new ProviderSettingsDelegate().onSelect(item);
    return true;
}
