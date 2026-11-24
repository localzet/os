import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Dock buttons always launch existing apps. Optional apps only appear when
// actually installed; there are no placeholders or inert icons.
export class LocalzetDock {
    constructor(settings) {
        this._appSystem = Shell.AppSystem.get_default();
        this._settings = settings;
        this._pinnedAppsChanged = settings?.connect(
            'changed::pinned-apps', () => this._rebuild()) || 0;
        this._appStateSignals = [];
        this._actor = new St.BoxLayout({
            style_class: 'localzet-dock',
            vertical: false,
            reactive: true,
            track_hover: true,
        });
        const backgroundMode = Shell.BlurMode?.BACKGROUND;
        if (typeof Shell.BlurEffect === 'function' && backgroundMode !== undefined) {
            try {
                this._actor.add_effect_with_name('localzet-dock-blur', new Shell.BlurEffect({
                    mode: backgroundMode,
                    radius: 18,
                }));
            } catch (error) {
                console.warn('Localzet Dock: background blur unavailable: ' + error);
            }
        }

        this._monitorsChanged = Main.layoutManager.connect(
            'monitors-changed', () => this._place());
        this._appsChanged = this._appSystem.connect(
            'installed-changed', () => this._rebuild());
        this._overviewShowing = Main.overview.connect(
            'showing', () => this._actor?.hide());
        this._overviewHidden = Main.overview.connect(
            'hidden', () => this._actor?.show());

        Main.layoutManager.addChrome(this._actor, {
            affectsStruts: false,
            trackFullscreen: false,
        });
        this._rebuild();
        if (Main.overview.visible)
            this._actor.hide();
    }

    _addButton(icon, callback, title, app = null) {
        const content = new St.BoxLayout({
            style_class: 'localzet-dock-content',
            vertical: true,
            x_align: Clutter.ActorAlign.CENTER,
        });
        content.add_child(icon);
        const indicator = new St.Widget({
            style_class: 'localzet-dock-indicator',
            visible: false,
            x_align: Clutter.ActorAlign.CENTER,
        });
        content.add_child(indicator);
        const button = new St.Button({
            style_class: 'localzet-dock-button',
            can_focus: true,
            reactive: true,
            track_hover: true,
            child: content,
        });
        button.accessible_name = title;
        button.connect('clicked', () => {
            try {
                callback();
            } catch (error) {
                console.error('Localzet Dock: ' + title + ': ' + error);
            }
        });
        if (app) {
            const updateState = () => {
                const running = app.state === Shell.AppState.RUNNING;
                indicator.visible = running;
                button.accessible_name = running ? `${title}, запущено` : title;
            };
            this._appStateSignals.push([app, app.connect('notify::state', updateState)]);
            updateState();
        }
        this._actor.add_child(button);
    }

    _rebuild() {
        if (!this._actor)
            return;
        this._clearAppStateSignals();
        this._actor.destroy_all_children();
        this._addButton(new St.Icon({
            icon_name: 'view-app-grid-symbolic', icon_size: 38,
        }), () => Main.overview.show(), 'Приложения');

        const installed = new Set();
        const pinned = this._settings?.get_strv('pinned-apps') || [];
        for (const id of pinned) {
            const app = this._appSystem.lookup_app(id);
            if (!app || !app.get_app_info().should_show() || installed.has(app.get_id()))
                continue;
            installed.add(app.get_id());
            this._addButton(app.create_icon_texture(38),
                () => app.activate(), app.get_name(), app);
        }
        this._place();
    }

    _place() {
        if (!this._actor)
            return;
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        const count = this._actor.get_n_children();
        const width = Math.min(monitor.width - 24, Math.max(90, 20 + count * 60));
        const height = 70;
        this._actor.set_size(width, height);
        this._actor.set_position(
            monitor.x + Math.round((monitor.width - width) / 2),
            monitor.y + monitor.height - height - 16,
        );
    }

    destroy() {
        this._clearAppStateSignals();
        if (this._monitorsChanged) {
            Main.layoutManager.disconnect(this._monitorsChanged);
            this._monitorsChanged = 0;
        }
        if (this._appsChanged) {
            this._appSystem.disconnect(this._appsChanged);
            this._appsChanged = 0;
        }
        if (this._pinnedAppsChanged) {
            this._settings.disconnect(this._pinnedAppsChanged);
            this._pinnedAppsChanged = 0;
        }
        if (this._overviewShowing) {
            Main.overview.disconnect(this._overviewShowing);
            this._overviewShowing = 0;
        }
        if (this._overviewHidden) {
            Main.overview.disconnect(this._overviewHidden);
            this._overviewHidden = 0;
        }
        this._actor?.destroy();
        this._actor = null;
        this._settings = null;
    }

    _clearAppStateSignals() {
        for (const [app, signal] of this._appStateSignals) {
            app.disconnect(signal);
        }
        this._appStateSignals = [];
    }
}
