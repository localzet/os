// Static, wallpaper-only glass. No capture of windows, passwords or screens.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const WALLPAPER = '/usr/share/backgrounds/localzet/executive-dusk.jpg';
export class WallpaperGlass {
    constructor(menu) {
        this._menu = menu;
        this._background = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
        this._interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._contrast = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._path = WALLPAPER;
        if (GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1') {
            const test = GLib.getenv('LOCALZET_TEST_WALLPAPER');
            if (test && /^\/[A-Za-z0-9_./-]+\/executive-dusk\.jpg$/.test(test))
                this._path = test;
        }
        this._blur = this._path.replace(/\.jpg$/, '-glass.jpg');
        this._signals = [];
        const watch = (object, name) => {
            this._signals.push([object, object.connect(name, () => this._schedule())]);
        };
        watch(this._background, 'changed');
        watch(this._interface, 'changed::color-scheme');
        watch(this._contrast, 'changed::high-contrast');
        watch(Main.layoutManager, 'monitors-changed');
        watch(global.display, 'window-created');
        watch(global.display, 'notify::focus-window');
        watch(global.workspace_manager, 'active-workspace-changed');
        this._signals.push([menu.box, menu.box.connect('notify::allocation', () => {
            if (menu.isOpen && !this._idle)
                this._idle = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 120, () => {
                    this._idle = 0;
                    this._refresh();
                    return GLib.SOURCE_REMOVE;
                });
        })]);
        this._open = menu.connect('open-state-changed', (_menu, open) => {
            if (open) this._schedule();
            else this.clear();
        });
    }

    _schedule() {
        // A change must fail closed while the new backdrop is evaluated.
        this.clear();
        if (!this._menu.isOpen)
            return;
        this._idle = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 120, () => {
            this._idle = 0;
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _refresh() {
        if (!this._menu.isOpen || this._contrast.get_boolean('high-contrast') ||
            Main.overview.visible || Main.layoutManager.monitors.length !== 1 ||
            St.ThemeContext.get_for_stage(global.stage).scale_factor !== 1)
            return;
        const dark = this._interface.get_string('color-scheme') === 'prefer-dark';
        const uri = this._background.get_string(dark ? 'picture-uri-dark' : 'picture-uri');
        if (uri !== Gio.File.new_for_path(this._path).get_uri() ||
            this._background.get_string('picture-options') !== 'zoom' ||
            !GLib.file_test(this._blur, GLib.FileTest.IS_REGULAR))
            return;
        // Static material is only correct on an empty desktop. Do not pass
        // it off as sampling live windows when any window is visible.
        if (global.workspace_manager.get_active_workspace().list_windows().some(w =>
            !w.minimized && w.showing_on_its_workspace()))
            return;
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        const [x, y] = this._menu.box.get_transformed_position();
        const [w, h] = this._menu.box.get_transformed_size();
        if (w < 10 || h < 10)
            return;
        // Wallpaper is 3840×2160; reproduce GNOME's centered zoom crop.
        const scale = Math.max(monitor.width / 3840, monitor.height / 2160);
        const bw = Math.round(3840 * scale), bh = Math.round(2160 * scale);
        const dx = Math.round(monitor.x + (monitor.width - bw) / 2 - x);
        const dy = Math.round(monitor.y + (monitor.height - bh) / 2 - y);
        const style = 'background-image: url("' + this._blur + '"); ' +
            'background-size: ' + bw + 'px ' + bh + 'px; ' +
            'background-position: ' + dx + 'px ' + dy + 'px; background-repeat: no-repeat;';
        if (this._menu.box.get_style() !== style)
            this._menu.box.set_style(style);
        this._menu.actor.add_style_class_name('localzet-wallpaper-glass');
        console.log('Localzet Glass: wallpaper material active');
    }

    clear() {
        if (this._idle) {
            GLib.source_remove(this._idle);
            this._idle = 0;
        }
        this._menu.box.set_style(null);
        this._menu.actor.remove_style_class_name('localzet-wallpaper-glass');
    }

    destroy() {
        this.clear();
        this._menu.disconnect(this._open);
        for (const [object, id] of this._signals)
            object.disconnect(id);
        this._signals = [];
    }
}
