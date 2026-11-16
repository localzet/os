import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {LocalzetDock} from './dock.js';
import {AuroraPanel} from './panel.js';

// A hot-reloaded extension instance can overlap a previous one in devkit.
// Own only our own actors, and always tear them down before replacing them.
const OWNER = Symbol.for('com.localzet.shell.executive.owner');
export default class LocalzetShell extends Extension {
    enable() {
        if (Main.panel[OWNER] === this && this._dock && this._panel)
            return;
        const previous = Main.panel[OWNER];
        if (previous && previous !== this)
            previous.disable();
        Main.panel[OWNER] = this;
        try {
            this._dock = new LocalzetDock(this.path);
            this._panel = new AuroraPanel(this._dock);
        } catch (error) {
            this.disable();
            throw error;
        }
    }

    disable() {
        this._panel?.destroy();
        this._panel = null;
        this._dock?.destroy();
        this._dock = null;
        if (Main.panel[OWNER] === this)
            delete Main.panel[OWNER];
    }
}
