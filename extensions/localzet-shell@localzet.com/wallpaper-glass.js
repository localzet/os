// Real wallpaper-only compositor glass. No screen/window capture or static blur image.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const WALLPAPER = '/usr/share/backgrounds/localzet/executive-dusk.jpg';
const EFFECT_NAME = 'localzet-wallpaper-background-blur';
const EFFECT_RADIUS = 18;
const EFFECT_BRIGHTNESS = 0.85;

export function wallpaperPath() {
    if (GLib.getenv('LOCALZET_EXPERIMENTAL_GLASS') === '1') {
        const test = GLib.getenv('LOCALZET_TEST_WALLPAPER');
        if (test && /^\/[A-Za-z0-9_./-]+\/(?:executive-dusk\.jpg|blur-probe\.png)$/.test(test))
            return test;
    }
    return WALLPAPER;
}

export function wallpaperGlassAvailable(background, settings, contrast, path) {
    // Every unsupported/accessibility state fails closed to the opaque style.
    if (GLib.getenv('LOCALZET_DISABLE_GLASS') === '1' ||
        contrast.get_boolean('high-contrast') ||
        Main.sessionMode.isLocked || Main.sessionMode.isGreeter || Main.overview.visible ||
        Main.layoutManager.monitors.length !== 1 ||
        St.ThemeContext.get_for_stage(global.stage).scale_factor !== 1)
        return false;

    const dark = settings.get_string('color-scheme') === 'prefer-dark';
    const uri = background.get_string(dark ? 'picture-uri-dark' : 'picture-uri');
    if (uri !== Gio.File.new_for_path(path).get_uri() ||
        background.get_string('picture-options') !== 'zoom' ||
        !GLib.file_test(path, GLib.FileTest.IS_REGULAR))
        return false;

    // The dock and popovers use wallpaper-only glass. Never blur live windows.
    if (global.workspace_manager.get_active_workspace().list_windows().some(w =>
        !w.minimized && w.showing_on_its_workspace()))
        return false;
    return !!Main.layoutManager.primaryMonitor;
}

export function hasStageAllocation(actor) {
    return !!actor && actor.get_stage() !== null && actor.is_mapped() &&
        actor.get_width() > 0 && actor.get_height() > 0;
}

export class WallpaperGlass {
    constructor(menu, surface = 'launcher') {
        this._menu = menu;
        this._surface = surface;
        this._effect = null;
        this._effectActor = null;
        this._idle = 0;
        this._disposed = false;
        this._allocationSignals = [];
        this._allocationTimeout = 0;
        this._background = new Gio.Settings({schema_id: 'org.gnome.desktop.background'});
        this._interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._contrast = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._path = wallpaperPath();
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
        watch(Main.overview, 'showing');
        watch(Main.overview, 'hidden');
        watch(Main.sessionMode, 'updated');
        this._open = menu.connect('open-state-changed', (_menu, open) => {
            if (open)
                this._schedule();
            else
                this.clear();
        });
        // PopupMenu actors may be destroyed independently during Shell
        // teardown. Their destroy signals own disposal; never call methods on
        // a Clutter actor after it has started destruction.
        this._actorDestroyId = menu.actor.connect('destroy', () => this._dispose());
        this._boxDestroyId = menu.box.connect('destroy', () => this._dispose());
    }

    _dispose() {
        if (this._disposed)
            return;
        this._disposed = true;
        if (this._idle) {
            GLib.source_remove(this._idle);
            this._idle = 0;
        }
        if (this._allocationTimeout) {
            GLib.source_remove(this._allocationTimeout);
            this._allocationTimeout = 0;
        }
        // The actors are being destroyed, so their effects and signal
        // connections die with them. Do not remove effects or style classes.
        this._allocationSignals = [];
        this._effect = null;
        this._effectActor = null;
    }

    _schedule() {
        if (this._disposed)
            return;
        // Remove the effect while the new display state is evaluated.
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
        if (this._disposed || !this._menu.isOpen ||
            !wallpaperGlassAvailable(this._background, this._interface, this._contrast, this._path)) {
            this._clearAllocationWait();
            this._restore();
            return;
        }
        if (this._effect)
            return;

        // PopupMenu's outer BoxPointer owns the arrow and event surface;
        // the actual translucent .popup-menu-content is menu.box. Mutter's
        // BACKGROUND effect must be attached to that content actor or it only
        // blurs the transparent wrapper while the visible child stays sharp.
        const effectActor = this._menu.box;
        if (!hasStageAllocation(this._menu.actor) || !hasStageAllocation(effectActor)) {
            this._waitForAllocation();
            return;
        }

        try {
            const effect = new Shell.BlurEffect({
                name: EFFECT_NAME,
                radius: EFFECT_RADIUS,
                brightness: EFFECT_BRIGHTNESS,
                mode: Shell.BlurMode.BACKGROUND,
            });
            // Mutter 50 can silently skip BACKGROUND blur when an effect is
            // attached before the popup and its content have real allocations.
            // Wait for both actors; the content BoxLayout samples the wallpaper
            // beneath its translucent surface while text and controls stay sharp.
            effectActor.add_effect_with_name(EFFECT_NAME, effect);
            effect.queue_repaint();
            this._effectActor = effectActor;
            this._effect = effect;
            effectActor.add_style_class_name('localzet-wallpaper-glass');
            console.log('Localzet Glass: wallpaper compositor effect active ' + this._surface +
                ' mode=' + effect.get_mode() + ' radius=' + effect.get_radius() +
                ' allocated=' + Math.round(effectActor.get_width()) + 'x' +
                Math.round(effectActor.get_height()) + ' enabled=' + effect.get_enabled());
        } catch (error) {
            this._restore();
            console.warn('Localzet Glass: opaque fallback ' + this._surface + ': ' + error);
        }
    }

    _waitForAllocation() {
        if (this._disposed || this._allocationSignals.length)
            return;

        const retry = () => {
            if (this._disposed || !this._menu.isOpen) {
                this._clearAllocationWait();
                return;
            }
            if (hasStageAllocation(this._menu.actor) && hasStageAllocation(this._menu.box)) {
                this._clearAllocationWait();
                this._refresh();
            }
        };

        for (const actor of [this._menu.actor, this._menu.box]) {
            if (!actor)
                continue;
            this._allocationSignals.push([actor, actor.connect('notify::allocation', retry)]);
        }
        this._allocationTimeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {
            this._allocationTimeout = 0;
            this._clearAllocationWait();
            if (this._menu.isOpen && !this._effect)
                console.warn('Localzet Glass: allocation timeout; opaque fallback ' + this._surface);
            return GLib.SOURCE_REMOVE;
        });
        retry();
    }

    _clearAllocationWait() {
        for (const [actor, id] of this._allocationSignals)
            actor.disconnect(id);
        this._allocationSignals = [];
        if (this._allocationTimeout) {
            GLib.source_remove(this._allocationTimeout);
            this._allocationTimeout = 0;
        }
    }

    clear() {
        if (this._disposed)
            return;
        if (this._idle) {
            GLib.source_remove(this._idle);
            this._idle = 0;
        }
        this._clearAllocationWait();
        this._restore();
    }

    _restore() {
        if (this._disposed)
            return;
        if (this._effect) {
            (this._effectActor ?? this._menu.box).remove_effect(this._effect);
            this._effect = null;
            this._effectActor = null;
        }
        this._menu.actor.remove_style_class_name('localzet-wallpaper-glass');
    }

    destroy() {
        if (!this._disposed)
            this.clear();
        try {
            this._menu.disconnect(this._open);
        } catch (_) {
            // The PopupMenu may already have been disposed by GNOME Shell.
        }
        if (!this._disposed) {
            this._menu.actor.disconnect(this._actorDestroyId);
            this._menu.box.disconnect(this._boxDestroyId);
        }
        for (const [object, id] of this._signals) {
            try { object.disconnect(id); } catch (_) {}
        }
        this._signals = [];
        this._disposed = true;
    }
}
