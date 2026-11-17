// Native, non-toggle entry points. Network state belongs to the real client.
import Atk from 'gi://Atk';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as QuickSettings from 'resource:///org/gnome/shell/ui/quickSettings.js';

const ACTIONS = [
    ['com.localzet.Network.desktop', 'Частная сеть', 'NetBird · UserNet', 'network-vpn-symbolic'],
    ['com.localzet.Connect.desktop', 'Телефон', 'NectarLink', 'phone-symbolic'],
];

export class ExecutiveQuickActions {
    constructor(quickSettings) {
        this._quickSettings = quickSettings;
        this._apps = Shell.AppSystem.get_default();
        this._indicator = null;
        this._debug = GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1';
        this._timer = 0;
        this._installedId = this._apps.connect('installed-changed', () => this._rebuild());
        this._openId = quickSettings.menu.connect('open-state-changed', (_menu, open) => {
            if (!open || !this._debug) return;
            if (this._timer) GLib.source_remove(this._timer);
            this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 450, () => {
                this._timer = 0;
                for (const item of this._indicator?.quickSettingsItems ?? []) {
                    if (!item.mapped) continue;
                    const [x, y] = item.get_transformed_position();
                    const [w, h] = item.get_transformed_size();
                    console.log('Localzet Quick Actions: bounds=' + item._localzetId + ':' +
                        [x, y, w, h].map(Math.round).join(','));
                }
                return GLib.SOURCE_REMOVE;
            });
        });
        this._rebuild();
    }

    _clear() {
        if (!this._indicator) return;
        for (const item of this._indicator.quickSettingsItems)
            item.destroy();
        this._indicator.destroy();
        this._indicator = null;
    }

    _rebuild() {
        this._clear();
        const indicator = new QuickSettings.SystemIndicator();
        for (const [id, title, subtitle, iconName] of ACTIONS) {
            const app = this._apps.lookup_app(id);
            if (!app?.get_app_info()?.should_show()) continue;
            const item = new QuickSettings.QuickToggle({
                title, subtitle, iconName, toggleMode: false,
                accessible_role: Atk.Role.PUSH_BUTTON,
                accessible_name: title + ' — открыть ' + subtitle,
            });
            item._localzetId = id;
            item.add_style_class_name('localzet-quick-action');
            item.connect('clicked', () => {
                if (Main.sessionMode.isLocked || !Main.sessionMode.allowSettings)
                    return;
                try {
                    this._quickSettings.menu.close();
                    app.activate();
                    console.log('Localzet Quick Actions: opened ' + id);
                } catch (error) {
                    console.error('Localzet Quick Actions: launch failed: ' + error);
                    Main.notify(title, 'Не удалось открыть приложение');
                }
            });
            indicator.quickSettingsItems.push(item);
        }
        this._indicator = indicator;
        if (indicator.quickSettingsItems.length)
            this._quickSettings.addExternalIndicator(indicator);
        console.log('Localzet Quick Actions: items=' + indicator.quickSettingsItems.length);
    }

    destroy() {
        if (this._timer) GLib.source_remove(this._timer);
        this._timer = 0;
        this._apps.disconnect(this._installedId);
        this._quickSettings.menu.disconnect(this._openId);
        this._clear();
    }
}
