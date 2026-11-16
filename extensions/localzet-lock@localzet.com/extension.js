// CSS-only lock appearance. No actors, input handlers, authentication code,
// unlock methods, or private screen-shield references.
import St from 'gi://St';
import Gio from 'gi://Gio';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class ExecutiveLockAppearance extends Extension {
    enable() {
        if (this._modeId) return;
        this._file = this.dir.get_child('lock-material.css');
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._contrastId = this._settings.connect('changed::high-contrast', () => this._sync());
        this._modeId = Main.sessionMode.connect('updated', () => this._sync());
        this._sync();
    }

    _sync() {
        const theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
        // The native high-contrast theme always takes precedence. Only
        // load our small clock/notification sheet in the locked session.
        const active = Main.sessionMode.currentMode === 'unlock-dialog' &&
            !this._settings.get_boolean('high-contrast');
        const loaded = theme.get_custom_stylesheets().some(file => file.equal(this._file));
        if (active && !loaded) {
            theme.load_stylesheet(this._file);
            console.log('Localzet Lock: visual stylesheet active');
        } else if (!active && loaded) {
            theme.unload_stylesheet(this._file);
        }
    }

    disable() {
        if (this._modeId) Main.sessionMode.disconnect(this._modeId);
        this._modeId = 0;
        if (this._contrastId) this._settings.disconnect(this._contrastId);
        this._contrastId = 0;
        if (this._file) {
            const theme = St.ThemeContext.get_for_stage(global.stage).get_theme();
            if (theme.get_custom_stylesheets().some(file => file.equal(this._file)))
                theme.unload_stylesheet(this._file);
        }
        this._file = null;
        this._settings = null;
    }
}
