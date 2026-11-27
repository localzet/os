import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';

const EFFECT_PREFIX = 'localzet-compositor-blur-';

export class CompositorGlass {
    constructor(actor, name, {radius = 18, brightness = 0.85} = {}) {
        this.actor = actor;
        this.name = name;
        this.radius = radius;
        this.brightness = brightness;
        this.effect = null;
        this.parent = null;
        this.parentRedirect = null;
        this.destroyed = false;
        this.effectName = EFFECT_PREFIX + name;
        this.highContrast = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this.interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this.connections = [
            [actor, actor.connect('notify::mapped', () => this.refresh())],
            [actor, actor.connect('destroy', () => this.destroy())],
            [this.highContrast, this.highContrast.connect('changed::high-contrast', () => this.refresh())],
            [this.interface, this.interface.connect('changed::enable-animations', () => this.refresh())],
        ];
        this.refresh();
    }

    _fallbackReason() {
        if (GLib.getenv('LOCALZET_DISABLE_GLASS') === '1')
            return 'disabled';
        if (this.highContrast.get_boolean('high-contrast'))
            return 'high-contrast';
        if (!this.interface.get_boolean('enable-animations'))
            return 'reduced-motion';
        return null;
    }

    _restoreParent() {
        if (this.parent
            && this.parent.offscreen_redirect === Clutter.OffscreenRedirect.AUTOMATIC_FOR_OPACITY) {
            this.parent.offscreen_redirect = this.parentRedirect;
        }
        this.parent = null;
        this.parentRedirect = null;
    }

    _removeEffect() {
        if (this.effect && this.actor) {
            try {
                this.actor.remove_effect(this.effect);
            } catch (error) {
                console.warn('Localzet Glass: effect removal failed ' + this.name + ': ' + error);
            }
            this.effect = null;
        }
        if (this.actor) {
            this.actor.remove_style_class_name('localzet-compositor-glass');
            this.actor.remove_style_class_name('localzet-glass-opaque');
        }
        this._restoreParent();
    }

    refresh() {
        if (this.destroyed || !this.actor)
            return;
        this._removeEffect();
        if (!this.actor.mapped)
            return;
        const fallback = this._fallbackReason();
        if (fallback) {
            if (fallback !== 'high-contrast')
                this.actor.add_style_class_name('localzet-glass-opaque');
            console.log('Localzet Glass: opaque fallback ' + this.name + ' (' + fallback + ')');
            return;
        }

        try {
            const parent = this.actor.get_parent();
            if (parent
                && parent.offscreen_redirect === Clutter.OffscreenRedirect.ALWAYS) {
                this.parent = parent;
                this.parentRedirect = parent.offscreen_redirect;
                // Background sampling must see the live stage, not a cached
                // parent texture. Restore the original mode when unmapped.
                parent.offscreen_redirect = Clutter.OffscreenRedirect.AUTOMATIC_FOR_OPACITY;
            }

            const effect = new Shell.BlurEffect({
                radius: this.radius,
                brightness: this.brightness,
                mode: Shell.BlurMode.BACKGROUND,
            });
            this.actor.add_effect_with_name(this.effectName, effect);
            this.effect = effect;
            this.actor.add_style_class_name('localzet-compositor-glass');
            console.log('Localzet Glass: compositor blur active ' + this.name);
        } catch (error) {
            this._removeEffect();
            this.actor.add_style_class_name('localzet-glass-opaque');
            console.warn('Localzet Glass: opaque fallback ' + this.name + ': ' + error);
        }
    }

    destroy() {
        if (this.destroyed)
            return;
        this.destroyed = true;
        this._removeEffect();
        for (const [object, id] of this.connections) {
            try {
                object.disconnect(id);
            } catch (_) {
                // The actor may already be in its destroy signal.
            }
        }
        this.connections = [];
        this.highContrast = null;
        this.interface = null;
        this.actor = null;
    }
}
