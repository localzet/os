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
            this._panel = new AuroraPanel(this._dock, this.path);
            this._preferDesktopAtStartup();
        } catch (error) {
            this.disable();
            throw error;
        }
    }

    _preferDesktopAtStartup() {
        // GNOME 50 loads extensions asynchronously. Only intervene while
        // the initial animation is running; never close an overview that
        // the user opens later, or on extension reload / unlock.
        const layout = Main.layoutManager;
        if (!layout._startingUp || Main.sessionMode.isLocked)
            return;
        if (typeof layout.startInOverview === 'boolean') {
            this._previousStartInOverview = layout.startInOverview;
            layout.startInOverview = false;
        }
        this._startupId = layout.connect('startup-complete', () => {
            this._restoreStartupPreference();
            if (Main.overview.visible && !Main.sessionMode.isLocked)
                Main.overview.hide();
            console.log('Localzet Shell: startup desktop preference applied');
        });
    }

    _restoreStartupPreference() {
        if (this._startupId) {
            Main.layoutManager.disconnect(this._startupId);
            this._startupId = 0;
        }
        if (typeof this._previousStartInOverview === 'boolean') {
            Main.layoutManager.startInOverview = this._previousStartInOverview;
            this._previousStartInOverview = undefined;
        }
    }

    disable() {
        this._restoreStartupPreference();
        this._panel?.destroy();
        this._panel = null;
        this._dock?.destroy();
        this._dock = null;
        if (Main.panel[OWNER] === this)
            delete Main.panel[OWNER];
    }
}
