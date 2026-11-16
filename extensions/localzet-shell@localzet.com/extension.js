import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {LocalzetDock} from './dock.js';
import {AuroraPanel} from './panel.js';

// Keep the upstream accessible overview, clock and quick settings.
// Do not duplicate them with a second menu on the top panel.
export default class LocalzetShell extends Extension {
    enable() {
        if (!this._panel)
            this._panel = new AuroraPanel();
        if (!this._dock)
            this._dock = new LocalzetDock();
    }

    disable() {
        this._dock?.destroy();
        this._dock = null;
        this._panel?.destroy();
        this._panel = null;
    }
}
