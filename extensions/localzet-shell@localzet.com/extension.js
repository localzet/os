import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {LocalzetDock} from './dock.js';

// Keep the upstream accessible overview, clock and quick settings.
// Do not duplicate them with a second menu on the top panel.
export default class LocalzetShell extends Extension {
    enable() {
        if (!this._dock)
            this._dock = new LocalzetDock();
    }

    disable() {
        this._dock?.destroy();
        this._dock = null;
    }
}
