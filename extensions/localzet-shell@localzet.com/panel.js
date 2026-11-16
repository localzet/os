import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const BASE = 'localzet-panel';
const GLASS = 'localzet-panel-glass';
const EFFECT = 'localzet-panel-background-blur';
const SURFACE = 'localzet-system-surface';

// First compositor-backed glass experiment. The native top panel has a
// rectangular footprint, unlike the dock and popovers. Do not extend this
// effect to rounded surfaces without an antialiased clipping solution.
// The experiment is opt-in at session startup until pixel/performance QA.
export class AuroraPanel {
    constructor() {
        this._panel = Main.panel;
        this._effect = null;
        this._surfaces = [];
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._contrastId = this._settings.connect('changed::high-contrast', () => this._refresh());
        this._experimental = GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1';
        this._refresh();
    }

    _clear() {
        for (const {actor, menu, signal} of this._surfaces) {
            if (signal)
                menu.disconnect(signal);
            actor.remove_style_class_name(SURFACE);
        }
        this._surfaces = [];
        if (this._effect) {
            this._panel.remove_effect(this._effect);
            this._effect = null;
        }
        this._panel.remove_style_class_name(GLASS);
        this._panel.remove_style_class_name(BASE);
    }

    _refresh() {
        this._clear();
        if (this._settings.get_boolean('high-contrast'))
            return; // Respect native GNOME high-contrast styling.
        this._panel.add_style_class_name(BASE);
        // Style only real upstream menus, leaving their input, authentication,
        // accessibility, network, volume and notification semantics intact.
        for (const name of ['quickSettings', 'dateMenu']) {
            const menu = this._panel.statusArea[name]?.menu;
            if (menu?.actor) {
                menu.actor.add_style_class_name(SURFACE);
                const signal = this._experimental ? menu.connect('open-state-changed', (_menu, open) => {
                    if (open)
                        console.log('Localzet Surfaces: opened ' + name);
                }) : 0;
                this._surfaces.push({actor: menu.actor, menu, signal});
            }
        }
        if (this._experimental)
            console.log('Localzet Surfaces: native menus=' + this._surfaces.length);
        if (!this._experimental)
            return;
        try {
            const effect = new Shell.BlurEffect({
                radius: 18,
                brightness: 0.85,
                mode: Shell.BlurMode.BACKGROUND,
            });
            this._panel.add_effect_with_name(EFFECT, effect);
            this._effect = effect;
            this._panel.add_style_class_name(GLASS);
            console.log('Localzet Glass: panel background effect active');
        } catch (error) {
            // The opaque fallback retains the native menu styles.
            if (this._effect) {
                this._panel.remove_effect(this._effect);
                this._effect = null;
            }
            this._panel.remove_style_class_name(GLASS);
            console.warn('Localzet Glass: opaque fallback: ' + error);
        }
    }

    destroy() {
        this._settings.disconnect(this._contrastId);
        this._clear();
        this._panel = null;
        this._settings = null;
    }
}
