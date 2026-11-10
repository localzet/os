import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// P1: a small launcher built on GNOME Shell's extension API.
// No replacements of Shell/Overview internals and no privileged services.
export default class LocalzetShell extends Extension {
    enable() {
        if (this._indicator)
            return;

        this._indicator = new PanelMenu.Button(0.0, 'Localzet OS', false);
        this._indicator.add_style_class_name('localzet-indicator');

        const mark = new St.BoxLayout({
            style_class: 'localzet-brand',
            vertical: false,
        });
        mark.add_child(new St.Icon({
            icon_name: 'applications-system-symbolic',
            style_class: 'system-status-icon localzet-brand-icon',
        }));
        mark.add_child(new St.Label({
            text: 'Localzet',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'localzet-brand-label',
        }));
        this._indicator.add_child(mark);

        const title = new PopupMenu.PopupMenuItem('Localzet OS · Alpha', {
            reactive: false,
            can_focus: false,
        });
        title.add_style_class_name('localzet-menu-title');
        this._indicator.menu.addMenuItem(title);
        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        this._addAction('Поиск и приложения', () => Main.overview.show());
        this._addAction('Файлы', () => this._launch(['nautilus']));
        this._addAction('Терминал', () => this._launch(['ptyxis']));

        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addAction('Настройки системы', () => this._launch(['gnome-control-center']));

        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'left');
    }

    _addAction(title, action) {
        const item = new PopupMenu.PopupMenuItem(title);
        item.add_style_class_name('localzet-menu-action');
        item.connect('activate', () => {
            try {
                action();
            } catch (error) {
                console.error('Localzet Shell: ' + title + ' failed: ' + error);
            }
        });
        this._indicator.menu.addMenuItem(item);
    }

    _launch(argv) {
        // Constant executable arguments only; no shell or user-provided commands.
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
