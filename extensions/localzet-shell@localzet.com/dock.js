import Shell from 'gi://Shell';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {AuroraLauncher} from './launcher.js';

export class LocalzetDock {
    constructor(path) {
        this._path = path;
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._favorites = new Gio.Settings({schema_id: 'org.gnome.shell'});
        this._appSystem = Shell.AppSystem.get_default();
        this._tracker = Shell.WindowTracker.get_default();
        this._rows = new Map();
        this._idle = 0;
        this._actor = new St.BoxLayout({
            style_class: 'localzet-dock', reactive: true, track_hover: true,
        });
        this._anchor = new St.Button({
            style_class: 'localzet-dock-button', can_focus: true, reactive: true,
            track_hover: true, accessible_name: 'Приложения',
        });
        this._anchor.set_child(this._launcherIcon());
        this._actor.add_child(this._anchor);
        this._launcher = new AuroraLauncher(this._anchor);
        this._anchor.connect('clicked', () => this._launcher.toggle());
        this._scroll = new St.ScrollView({style_class: 'localzet-dock-scroll',
            overlay_scrollbars: true, x_expand: true});
        this._apps = new St.BoxLayout({style_class: 'localzet-dock-apps'});
        this._scroll.set_child(this._apps);
        this._scroll.set_policy(St.PolicyType.AUTOMATIC, St.PolicyType.NEVER);
        this._actor.add_child(this._scroll);

        this._connections = [
            [this._settings, this._settings.connect('changed::high-contrast', () => {
                this._anchor.set_child(this._launcherIcon());
                this._schedule();
            })],
            [this._favorites, this._favorites.connect('changed::favorite-apps', () => this._schedule())],
            [this._appSystem, this._appSystem.connect('installed-changed', () => this._schedule())],
            [this._appSystem, this._appSystem.connect('app-state-changed', () => this._schedule())],
            [this._tracker, this._tracker.connect('notify::focus-app', () => this._schedule())],
            [global.display, global.display.connect('notify::focus-window', () => this._schedule())],
            [global.display, global.display.connect('window-created', () => this._schedule())],
            [Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => this._place())],
            [Main.overview, Main.overview.connect('showing', () => {
                this._launcher.close(); this._actor.hide();
            })],
            [Main.overview, Main.overview.connect('hidden', () => this._actor.show())],
        ];
        Main.layoutManager.addChrome(this._actor, {affectsStruts: false, trackFullscreen: true});
        this._reconcile();
        if (Main.overview.visible)
            this._actor.hide();
    }

    _launcherIcon() {
        const fallback = () => new St.Icon({icon_name: 'view-app-grid-symbolic', icon_size: 25});
        if (this._settings.get_boolean('high-contrast'))
            return fallback();
        const file = Gio.File.new_for_path(GLib.build_filenamev([this._path, 'icons', 'launcher.svg']));
        return file.query_exists(null) ? new St.Icon({gicon: new Gio.FileIcon({file}), icon_size: 25}) : fallback();
    }

    _schedule() {
        if (this._idle)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            this._reconcile();
            return GLib.SOURCE_REMOVE;
        });
    }

    _windows(app) {
        return app.get_windows().filter(window => !window.skip_taskbar);
    }

    _activate(app) {
        const windows = this._windows(app);
        const focus = global.display.focus_window;
        const index = windows.indexOf(focus);
        if (index >= 0 && windows.length > 1) {
            Main.activateWindow(windows[(index + 1) % windows.length]);
        } else {
            app.activate();
        }
    }

    _newRow(app) {
        const icon = app.create_icon_texture(34);
        const dot = new St.Widget({style_class: 'localzet-dock-indicator',
            x_align: Clutter.ActorAlign.CENTER});
        const content = new St.BoxLayout({vertical: true, style_class: 'localzet-dock-item-content',
            x_align: Clutter.ActorAlign.CENTER});
        content.add_child(icon);
        content.add_child(dot);
        const button = new St.Button({child: content, style_class: 'localzet-dock-button',
            reactive: true, can_focus: true, track_hover: true, accessible_name: app.get_name()});
        button.connect('clicked', () => {
            try {
                this._activate(app);
            } catch (error) {
                console.error('Localzet Dock: activate failed: ' + error);
            }
        });
        const windowsId = app.connect('windows-changed', () => this._schedule());
        this._apps.add_child(button);
        return {app, button, dot, windowsId};
    }

    _removeRow(id) {
        const row = this._rows.get(id);
        row.app.disconnect(row.windowsId);
        row.button.destroy();
        this._rows.delete(id);
    }

    _reconcile() {
        const wanted = new Map();
        const favorites = new Set(this._favorites.get_strv('favorite-apps'));
        for (const id of favorites) {
            const app = this._appSystem.lookup_app(id);
            if (app && app.get_app_info()?.should_show())
                wanted.set(id, app);
        }
        for (const app of this._appSystem.get_running()) {
            if (this._windows(app).length && app.get_app_info()?.should_show())
                wanted.set(app.get_id(), app);
        }
        for (const id of this._rows.keys()) {
            if (!wanted.has(id))
                this._removeRow(id);
        }
        let index = 0;
        for (const [id, app] of wanted) {
            if (!this._rows.has(id))
                this._rows.set(id, this._newRow(app));
            const row = this._rows.get(id);
            this._apps.set_child_at_index(row.button, index++);
            row.button[favorites.has(id) ? 'add_style_class_name' : 'remove_style_class_name']('localzet-dock-favorite');
        }
        this._updateIndicators();
        this._place();
    }

    _updateIndicators() {
        const focus = this._tracker.focus_app;
        let running = 0;
        let focused = 0;
        for (const row of this._rows.values()) {
            const count = this._windows(row.app).length;
            const active = count > 0 && row.app === focus;
            if (count)
                running++;
            if (active)
                focused++;
            row.dot[count ? 'add_style_class_name' : 'remove_style_class_name']('running');
            row.dot[active ? 'add_style_class_name' : 'remove_style_class_name']('focused');
            row.button[active ? 'add_style_class_name' : 'remove_style_class_name']('localzet-dock-focused');
            row.button.accessible_name = row.app.get_name() + (count ? ' · ' + count + ' окон' : '');
        }
        if (GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1')
            console.log('Localzet Dock: running=' + running + ' items=' + this._rows.size + ' focused=' + focused);
    }

    _place() {
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        // Size from the actual themed actor requisitions, not an assumed
        // width per app. Show horizontal scrolling only on real overflow.
        const [, anchorWidth] = this._anchor.get_preferred_width(-1);
        const [, appWidth] = this._apps.get_preferred_width(-1);
        const natural = Math.max(64, Math.ceil(anchorWidth + appWidth + 32));
        const width = Math.min(monitor.width - 24, natural);
        this._scroll.set_policy(natural > width ? St.PolicyType.AUTOMATIC : St.PolicyType.NEVER,
            St.PolicyType.NEVER);
        const height = 56;
        this._actor.set_size(width, height);
        const x = monitor.x + Math.round((monitor.width - width) / 2);
        const y = monitor.y + monitor.height - height - 12;
        this._actor.set_position(x, y);
        if (GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1')
            console.log('Localzet Launcher: dock=' + x + ',' + y);
    }

    destroy() {
        if (this._idle)
            GLib.source_remove(this._idle);
        for (const [object, id] of this._connections)
            object.disconnect(id);
        this._connections = [];
        this._launcher.destroy();
        for (const id of this._rows.keys())
            this._removeRow(id);
        this._actor.destroy();
        this._actor = null;
    }
}
