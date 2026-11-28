import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {ExecutiveQuickActions} from './quick-actions.js';
import {hasStageAllocation, WallpaperGlass} from './wallpaper-glass.js';

const BASE = 'localzet-panel';
const GLASS = 'localzet-panel-glass';
const EFFECT = 'localzet-panel-background-blur';
const SURFACE = 'localzet-system-surface';

// Real compositor blur is enabled by default on supported GNOME sessions.
// High contrast and LOCALZET_DISABLE_GLASS=1 use the opaque accessible fallback.
// Rounded surfaces use wallpaper-only material only on an empty desktop.
export class AuroraPanel {
    constructor(dock, path) {
        this._dock = dock;
        this._path = path;
        this._navigation = null;
        this._panel = Main.panel;
        this._effect = null;
        this._surfaces = [];
        this._quickActions = null;
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._contrastId = this._settings.connect('changed::high-contrast', () => this._refresh());
        this._glassEnabled = GLib.getenv('LOCALZET_DISABLE_GLASS') !== '1';
        this._allocationId = this._panel.connect('notify::allocation', () => {
            if (!this._effect && this._glassEnabled && !this._settings.get_boolean('high-contrast'))
                this._installPanelBlur();
        });
        try {
            this._refresh();
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    _clear() {
        this._quickActions?.destroy();
        this._quickActions = null;
        this._navigation?.destroy();
        this._navigation = null;
        for (const {actor, menu, signal, glass} of this._surfaces) {
            glass?.destroy();
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
        const quickSettings = this._panel.statusArea.quickSettings;
        if (quickSettings && Main.sessionMode.allowSettings && !Main.sessionMode.isLocked)
            this._quickActions = new ExecutiveQuickActions(quickSettings);
        if (this._settings.get_boolean('high-contrast')) {
            if (this._glassEnabled)
                console.log('Localzet Glass: panel opaque fallback high-contrast');
            return; // Respect native GNOME high-contrast styling.
        }
        this._panel.add_style_class_name(BASE);
        this._installNavigation();
        // Style only real upstream menus, leaving their input, authentication,
        // accessibility, network, volume and notification semantics intact.
        for (const name of ['quickSettings', 'dateMenu']) {
            const menu = this._panel.statusArea[name]?.menu;
            if (menu?.actor) {
                menu.actor.add_style_class_name(SURFACE);
                const signal = this._glassEnabled ? menu.connect('open-state-changed', (_menu, open) => {
                    if (open)
                        console.log('Localzet Surfaces: opened ' + name);
                }) : 0;
                const glass = this._glassEnabled && menu.box ? new WallpaperGlass(menu, name) : null;
                this._surfaces.push({actor: menu.actor, menu, signal, glass});
            }
        }
        if (this._glassEnabled)
            console.log('Localzet Surfaces: native menus=' + this._surfaces.length);
        if (!this._glassEnabled)
            return;
        this._installPanelBlur();
    }

    _installPanelBlur() {
        if (!this._glassEnabled || this._effect ||
            this._settings.get_boolean('high-contrast') ||
            !hasStageAllocation(this._panel))
            return;

        try {
            const effect = new Shell.BlurEffect({
                radius: 18,
                brightness: 0.85,
                mode: Shell.BlurMode.BACKGROUND,
            });
            this._panel.add_effect_with_name(EFFECT, effect);
            effect.queue_repaint();
            this._effect = effect;
            this._panel.add_style_class_name(GLASS);
            console.log('Localzet Glass: panel background effect active allocated=' +
                Math.round(this._panel.get_width()) + 'x' +
                Math.round(this._panel.get_height()) + ' enabled=' + effect.get_enabled());
        } catch (error) {
            if (this._effect) {
                this._panel.remove_effect(this._effect);
                this._effect = null;
            }
            this._panel.remove_style_class_name(GLASS);
            console.warn('Localzet Glass: opaque fallback: ' + error);
        }
    }

    _installNavigation() {
        // Keep the native Activities button, clock and quick settings intact.
        // The brand shortcut invokes the SAME command hub as the dock.
        const item = new PanelMenu.Button(0.0, 'Localzet — приложения', true);
        item.add_style_class_name('localzet-panel-navigation');
        const content = new St.BoxLayout({style_class: 'localzet-panel-brand',
            y_align: Clutter.ActorAlign.CENTER});
        const brand = Gio.File.new_for_path(GLib.build_filenamev([this._path, 'icons', 'launcher.svg']));
        const icon = brand.query_exists(null)
            ? new St.Icon({gicon: new Gio.FileIcon({file: brand}), icon_size: 16})
            : new St.Icon({icon_name: 'view-app-grid-symbolic', icon_size: 16});
        content.add_child(icon);
        content.add_child(new St.Label({text: 'Localzet', y_align: Clutter.ActorAlign.CENTER}));
        item.add_child(content);
        const activate = () => {
            if (Main.overview.visible)
                Main.overview.hide();
            else
                this._dock.toggleLauncher();
        };
        item.connect('button-press-event', (_actor, event) => {
            if (event.get_button() !== 1)
                return Clutter.EVENT_PROPAGATE;
            activate();
            return Clutter.EVENT_STOP;
        });
        item.connect('key-press-event', (_actor, event) => {
            if (![Clutter.KEY_Return, Clutter.KEY_KP_Enter, Clutter.KEY_space].includes(event.get_key_symbol()))
                return Clutter.EVENT_PROPAGATE;
            activate();
            return Clutter.EVENT_STOP;
        });
        this._navigation = item;
        this._panel.addToStatusArea('localzetExecutive', item, 1, 'left');
        if (this._glassEnabled)
            console.log('Localzet Panel: executive navigation ready');
    }

    destroy() {
        this._settings.disconnect(this._contrastId);
        this._panel.disconnect(this._allocationId);
        this._clear();
        this._panel = null;
        this._settings = null;
    }
}
