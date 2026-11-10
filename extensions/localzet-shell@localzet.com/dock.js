import Clutter from 'gi://Clutter';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Dock buttons always launch existing apps. Optional apps only appear when
// actually installed; there are no placeholders or inert icons.
const PINNED = [
    'com.microsoft.Edge.desktop',
    'microsoft-edge.desktop',
    'org.gnome.Nautilus.desktop',
    'org.gnome.Ptyxis.desktop',
    'com.localzet.Settings.desktop',
];

export class LocalzetDock {
    constructor() {
        this._appSystem = Shell.AppSystem.get_default();
        this._actor = new St.BoxLayout({
            style_class: 'localzet-dock',
            vertical: false,
            reactive: true,
            track_hover: true,
        });

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

    _addButton(icon, callback, title) {
        const button = new St.Button({
            style_class: 'localzet-dock-button',
            can_focus: true,
            reactive: true,
            track_hover: true,
            child: icon,
        });
        button.accessible_name = title;
        button.connect('clicked', () => {
            try {
                callback();
            } catch (error) {
                console.error('Localzet Dock: ' + title + ': ' + error);
            }
        });
        this._actor.add_child(button);
    }

    _rebuild() {
        if (!this._actor)
            return;
        this._actor.destroy_all_children();
        this._addButton(new St.Icon({
            icon_name: 'view-app-grid-symbolic', icon_size: 32,
        }), () => Main.overview.show(), 'Приложения');

        const installed = new Set();
        for (const id of PINNED) {
            const app = this._appSystem.lookup_app(id);
            if (!app || !app.get_app_info().should_show() || installed.has(app.get_id()))
                continue;
            installed.add(app.get_id());
            this._addButton(app.create_icon_texture(32),
                () => app.activate(), app.get_name());
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
        const width = Math.min(monitor.width - 24, Math.max(90, 18 + count * 53));
        const height = 66;
        this._actor.set_size(width, height);
        this._actor.set_position(
            monitor.x + Math.round((monitor.width - width) / 2),
            monitor.y + monitor.height - height - 16,
        );
    }

    destroy() {
        if (this._monitorsChanged) {
            Main.layoutManager.disconnect(this._monitorsChanged);
            this._monitorsChanged = 0;
        }
        if (this._appsChanged) {
            this._appSystem.disconnect(this._appsChanged);
            this._appsChanged = 0;
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
    }
}
