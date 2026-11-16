import Shell from 'gi://Shell';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {AuroraLauncher} from './launcher.js';

// Dock buttons always launch existing apps. Optional apps only appear when
// actually installed; there are no placeholders or inert icons.
const PINNED = [
    ['org.gnome.Epiphany.desktop', 'browser'],
    ['org.gnome.Nautilus.desktop', 'files'],
    ['org.gnome.Ptyxis.desktop', 'terminal'],
    ['org.gnome.Settings.desktop', 'settings'],
];

export class LocalzetDock {
    constructor(path) {
        this._path = path;
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._contrastId = this._settings.connect('changed::high-contrast', () => this._rebuild());
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
            'showing', () => { this._launcher?.close(); this._actor?.hide(); });
        this._overviewHidden = Main.overview.connect(
            'hidden', () => this._actor?.show());

        Main.layoutManager.addChrome(this._actor, {
            affectsStruts: false,
            trackFullscreen: true,
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
        return button;
    }

    _icon(name, fallback) {
        if (this._settings.get_boolean('high-contrast'))
            return fallback();
        const file = Gio.File.new_for_path(GLib.build_filenamev([this._path, 'icons', name + '.svg']));
        if (!file.query_exists(null))
            return fallback();
        return new St.Icon({gicon: new Gio.FileIcon({file}), icon_size: 25});
    }

    _rebuild() {
        if (!this._actor)
            return;
        this._launcher?.destroy();
        this._launcher = null;
        this._actor.destroy_all_children();
        const anchor = this._addButton(this._icon('launcher', () => new St.Icon({
            icon_name: 'view-app-grid-symbolic', icon_size: 25,
        })), () => this._launcher.toggle(), 'Приложения');
        this._launcher = new AuroraLauncher(anchor);

        const installed = new Set();
        for (const [id, icon] of PINNED) {
            const app = this._appSystem.lookup_app(id);
            if (!app || !app.get_app_info().should_show() || installed.has(app.get_id()))
                continue;
            installed.add(app.get_id());
            this._addButton(this._icon(icon, () => app.create_icon_texture(25)),
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
        const width = Math.min(monitor.width - 24, Math.max(64, 16 + count * 46));
        const height = 48;
        this._actor.set_size(width, height);
        const x = monitor.x + Math.round((monitor.width - width) / 2);
        const y = monitor.y + monitor.height - height - 12;
        this._actor.set_position(x, y);
        if (GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1')
            console.log('Localzet Launcher: dock=' + x + ',' + y);
    }

    destroy() {
        this._launcher?.destroy();
        this._launcher = null;
        this._settings.disconnect(this._contrastId);
        this._settings = null;
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
