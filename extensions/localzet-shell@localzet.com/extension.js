import Gio from 'gi://Gio';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// Minimal GNOME 50 probe. We will not replace GNOME Shell internals in P0.
export default class LocalzetShell extends Extension {
    enable() {
        this._indicator = new PanelMenu.Button(0.0, 'Localzet', false);
        this._indicator.add_style_class_name('localzet-indicator');
        this._indicator.add_child(new St.Icon({
            icon_name: 'applications-system-symbolic',
            style_class: 'system-status-icon',
        }));

        const settings = new PopupMenu.PopupMenuItem('Настройки системы');
        settings.connect('activate', () => {
            try {
                Gio.Subprocess.new(['gnome-control-center'], Gio.SubprocessFlags.NONE);
            } catch (error) {
                console.error(`Localzet Shell: cannot open settings: ${error}`);
            }
        });
        this._indicator.menu.addMenuItem(settings);
        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'left');
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
