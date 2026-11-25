import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {LocalzetDock} from './dock.js';

// Localzet design tokens are mirrored in stylesheet.css; blur uses a Shell effect.
const MAX_VISIBLE_APPS = 8;
const APPEARANCE_CLASSES = ['localzet-theme-blue', 'localzet-theme-purple', 'localzet-theme-black'];
const VISUAL_TEST_MODE = '/usr/lib/localzet/localzet-visual-test-mode';
const VISUAL_TEST_INTERFACE = `
<node>
  <interface name="org.localzet.VisualTest">
    <method name="OpenLauncher">
      <arg name="ready" type="b" direction="out" />
    </method>
    <method name="OpenQuickSettings">
      <arg name="ready" type="b" direction="out" />
    </method>
    <method name="FindWindow">
      <arg name="app" type="s" direction="in" />
      <arg name="title" type="s" direction="out" />
    </method>
    <method name="CloseWindow">
      <arg name="app" type="s" direction="in" />
      <arg name="requested" type="b" direction="out" />
    </method>
  </interface>
</node>`;
const VISUAL_TEST_WINDOW_CLASSES = {
    settings: ['com.localzet.settings', 'localzet-settings'],
    files: ['org.gnome.nautilus', 'nautilus'],
    terminal: ['org.gnome.ptyxis', 'ptyxis'],
};

function openMenuAndReport(menu) {
    if (!menu)
        return false;
    menu.open();
    return menu.isOpen === true;
}

function findVisualTestWindowActor(app) {
    const expectedClasses = VISUAL_TEST_WINDOW_CLASSES[app];
    if (!expectedClasses)
        return null;

    for (const actor of global.get_window_actors()) {
        const window = actor.meta_window;
        if (!window || !actor.visible)
            continue;
        const wmClass = String(window.get_wm_class() || '').toLowerCase();
        if (expectedClasses.some(candidate => wmClass === candidate))
            return actor;
    }
    return null;
}

function findVisualTestWindow(app) {
    const actor = findVisualTestWindowActor(app);
    if (!actor)
        return '';
    const window = actor.meta_window;
    return window.get_title() || window.get_wm_class() || '';
}

function closeVisualTestWindow(app) {
    const actor = findVisualTestWindowActor(app);
    if (!actor)
        return false;
    actor.meta_window.delete(global.get_current_time());
    return true;
}

function addGlassBlur(actor, name, radius = 18) {
    const backgroundMode = Shell.BlurMode?.BACKGROUND;
    if (typeof Shell.BlurEffect !== 'function' || backgroundMode === undefined)
        return false;
    try {
        actor.add_effect_with_name(name, new Shell.BlurEffect({
            mode: backgroundMode,
            radius,
        }));
        return true;
    } catch (error) {
        console.warn('Localzet Shell: background blur unavailable: ' + error);
        return false;
    }
}

const GLASS_WINDOW_CLASSES = new Set([
    'nautilus', 'org.gnome.nautilus',
    'ptyxis', 'org.gnome.ptyxis',
]);

export default class LocalzetShell extends Extension {
    enable() {
        if (this._indicator)
            return;

        this._settings = this.getSettings();
        this._interfaceSettings = new Gio.Settings({
            schema_id: 'org.gnome.desktop.interface',
        });
        this._windowGlassActors = new Map();
        this._windowGlassSources = new Set();
        this._windowCreated = global.display.connect(
            'window-created', (_display, window) => this._scheduleWindowGlass(window));
        this._gtkThemeChanged = this._interfaceSettings.connect(
            'changed::gtk-theme', () => this._syncWindowGlass());
        this._visualTestNameOwner = 0;
        this._visualTestObject = null;
        this._appearanceChanged = this._settings.connect(
            'changed::appearance', () => this._applyAppearance());
        this._applyAppearance();

        Main.panel.add_style_class_name('localzet-panel');
        addGlassBlur(Main.panel, 'localzet-panel-blur');
        this._quickSettingsBox = Main.panel.statusArea.quickSettings?.menu?.box || null;
        if (this._quickSettingsBox)
            addGlassBlur(this._quickSettingsBox, 'localzet-quick-settings-blur', 20);
        this._syncWindowGlass();

        this._indicator = new PanelMenu.Button(0.0, 'Localzet OS', false);
        this._indicator.add_style_class_name('localzet-indicator');
        this._indicator.accessible_name = 'Localzet OS';

        const mark = new St.BoxLayout({
            style_class: 'localzet-brand',
            vertical: false,
        });
        mark.add_child(new St.Icon({
            gicon: new Gio.FileIcon({
                file: this.dir.get_child('localzet-brand.svg'),
            }),
            style_class: 'system-status-icon localzet-brand-icon',
        }));
        mark.add_child(new St.Label({
            text: 'Localzet',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'localzet-brand-label',
        }));
        this._indicator.add_child(mark);
        this._indicator.menu.box.add_style_class_name('localzet-launcher');
        addGlassBlur(this._indicator.menu.box, 'localzet-launcher-blur');

        const heading = new PopupMenu.PopupMenuItem('LOCALZET OS', {
            reactive: false,
            can_focus: false,
        });
        heading.add_style_class_name('localzet-menu-heading');
        this._indicator.menu.addMenuItem(heading);

        const searchItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
        });
        searchItem.add_style_class_name('localzet-search-container');
        this._search = new St.Entry({
            hint_text: 'Найти приложение…',
            style_class: 'localzet-search',
            can_focus: true,
            x_expand: true,
        });
        this._search.set_primary_icon(new St.Icon({
            icon_name: 'system-search-symbolic',
            style_class: 'localzet-search-icon',
        }));
        searchItem.add_child(this._search);
        this._indicator.menu.addMenuItem(searchItem);

        const label = new PopupMenu.PopupMenuItem('ПРИЛОЖЕНИЯ', {
            reactive: false,
            can_focus: false,
        });
        label.add_style_class_name('localzet-section-label');
        this._indicator.menu.addMenuItem(label);
        this._appsSection = new PopupMenu.PopupMenuSection();
        this._indicator.menu.addMenuItem(this._appsSection);

        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._addAction('Обзор рабочих столов', 'view-grid-symbolic',
            () => Main.overview.show());
        this._addAction('Файлы', 'folder-symbolic',
            () => this._launch(['nautilus']));
        this._addAction('Терминал', 'utilities-terminal-symbolic',
            () => this._launch(['ptyxis']));
        this._addAction('Настройки', 'preferences-system-symbolic',
            () => this._launch(['gnome-control-center']));

        this._phoneAction = this._addAction('Связь с телефоном', 'phone-symbolic',
            () => Shell.AppSystem.get_default().lookup_app('com.localzet.Connect.desktop')?.activate());
        this._phoneAction.visible = !!Shell.AppSystem.get_default().lookup_app('com.localzet.Connect.desktop');

        this._search.clutter_text.connect('notify::text', () => {
            this._updateApps(this._search.get_text());
        });
        this._indicator.menu.connect('open-state-changed', (_menu, open) => {
            if (!open)
                return;
            this._phoneAction.visible = !!Shell.AppSystem.get_default().lookup_app('com.localzet.Connect.desktop');
            this._search.set_text('');
            this._updateApps('');
            global.stage.set_key_focus(this._search.clutter_text);
        });
        this._updateApps('');
        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'left');
        this._enableVisualTestControl();
        this._dock = new LocalzetDock(this._settings);
    }

    _enableVisualTestControl() {
        if (!GLib.file_test(VISUAL_TEST_MODE, GLib.FileTest.EXISTS))
            return;

        this._visualTestNameOwner = Gio.bus_own_name(
            Gio.BusType.SESSION,
            'org.localzet.VisualTest',
            Gio.BusNameOwnerFlags.NONE,
            connection => {
                this._visualTestObject = Gio.DBusExportedObject.wrapJSObject(
                    VISUAL_TEST_INTERFACE,
                    {
                        OpenLauncher: () => openMenuAndReport(this._indicator?.menu),
                        OpenQuickSettings: () => openMenuAndReport(
                            Main.panel.statusArea.quickSettings?.menu,
                        ),
                        FindWindow: app => findVisualTestWindow(app),
                        CloseWindow: app => closeVisualTestWindow(app),
                    },
                );
                this._visualTestObject.export(connection, '/org/localzet/VisualTest');
            },
            null,
            (_connection, name) => console.warn(
                `Localzet Shell: visual test bus name ${name} is unavailable`,
            ),
        );
    }

    _applyAppearance() {
        if (!this._settings)
            return;
        const uiGroup = Main.layoutManager.uiGroup;
        for (const appearance of APPEARANCE_CLASSES)
            uiGroup.remove_style_class_name(appearance);
        const selected = this._settings.get_string('appearance');
        const appearance = APPEARANCE_CLASSES.includes(`localzet-theme-${selected}`)
            ? `localzet-theme-${selected}`
            : 'localzet-theme-blue';
        uiGroup.add_style_class_name(appearance);
    }

    _updateApps(rawQuery) {
        if (!this._appsSection)
            return;
        this._appsSection.removeAll();
        const query = String(rawQuery || '').trim().toLocaleLowerCase();
        let installed = [];
        try {
            installed = Shell.AppSystem.get_default().get_installed();
        } catch (error) {
            console.error('Localzet Shell: cannot list applications: ' + error);
            return;
        }

        const matches = installed
            .filter(app => app.should_show() && app.get_name())
            .filter(app => {
                if (!query)
                    return true;
                const name = app.get_name().toLocaleLowerCase();
                const id = (app.get_id() || '').toLocaleLowerCase();
                return name.includes(query) || id.includes(query);
            })
            .sort((a, b) => a.get_name().localeCompare(b.get_name()))
            .slice(0, MAX_VISIBLE_APPS);

        if (matches.length === 0) {
            const empty = new PopupMenu.PopupMenuItem('Ничего не найдено', {
                reactive: false,
                can_focus: false,
            });
            empty.add_style_class_name('localzet-empty');
            this._appsSection.addMenuItem(empty);
            return;
        }

        for (const app of matches) {
            const item = new PopupMenu.PopupImageMenuItem(
                app.get_name(), app.get_icon());
            item.add_style_class_name('localzet-application');
            item.connect('activate', () => {
                try {
                    app.launch([], null);
                } catch (error) {
                    console.error('Localzet Shell: app launch failed: ' + error);
                }
            });
            this._appsSection.addMenuItem(item);
        }
    }

    _addAction(label, icon, action) {
        const item = new PopupMenu.PopupImageMenuItem(label, icon);
        item.add_style_class_name('localzet-action');
        item.connect('activate', () => {
            try {
                action();
            } catch (error) {
                console.error('Localzet Shell: ' + label + ' failed: ' + error);
            }
        });
        this._indicator.menu.addMenuItem(item);
        return item;
    }

    _launch(argv) {
        // Fixed commands only; never pass untrusted input to a shell.
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    }

    disable() {
        this._visualTestObject?.unexport();
        this._visualTestObject = null;
        if (this._visualTestNameOwner) {
            Gio.bus_unown_name(this._visualTestNameOwner);
            this._visualTestNameOwner = 0;
        }
        this._dock?.destroy();
        this._dock = null;
        this._indicator?.destroy();
        this._indicator = null;
        this._appsSection = null;
        this._search = null;
        this._phoneAction = null;
        if (this._settings && this._appearanceChanged) {
            this._settings.disconnect(this._appearanceChanged);
            this._appearanceChanged = 0;
        }
        const uiGroup = Main.layoutManager.uiGroup;
        for (const appearance of APPEARANCE_CLASSES)
            uiGroup.remove_style_class_name(appearance);
        Main.panel.remove_effect_by_name('localzet-panel-blur');
        Main.panel.remove_style_class_name('localzet-panel');
        this._quickSettingsBox?.remove_effect_by_name('localzet-quick-settings-blur');
        this._quickSettingsBox = null;
        if (this._windowCreated) {
            global.display.disconnect(this._windowCreated);
            this._windowCreated = 0;
        }
        if (this._gtkThemeChanged && this._interfaceSettings) {
            this._interfaceSettings.disconnect(this._gtkThemeChanged);
            this._gtkThemeChanged = 0;
        }
        for (const source of this._windowGlassSources)
            GLib.source_remove(source);
        this._windowGlassSources.clear();
        for (const [actor, destroyed] of this._windowGlassActors) {
            actor.disconnect(destroyed);
            actor.remove_effect_by_name('localzet-window-blur');
        }
        this._windowGlassActors.clear();
        this._interfaceSettings = null;
        this._settings = null;
    }

    _usesAuroraGtkTheme() {
        return this._interfaceSettings?.get_string('gtk-theme')
            .startsWith('Localzet-Aurora-') || false;
    }

    _isGlassWindow(window) {
        const wmClass = String(window?.get_wm_class() || '').toLowerCase();
        return GLASS_WINDOW_CLASSES.has(wmClass);
    }

    _attachWindowGlass(actor) {
        if (!this._usesAuroraGtkTheme() || this._windowGlassActors.has(actor))
            return;
        if (!addGlassBlur(actor, 'localzet-window-blur', 16))
            return;
        const destroyed = actor.connect('destroy', () => {
            this._windowGlassActors.delete(actor);
        });
        this._windowGlassActors.set(actor, destroyed);
    }

    _syncWindowGlass() {
        if (!this._usesAuroraGtkTheme()) {
            for (const [actor, destroyed] of this._windowGlassActors) {
                actor.disconnect(destroyed);
                actor.remove_effect_by_name('localzet-window-blur');
            }
            this._windowGlassActors.clear();
            return;
        }
        for (const actor of global.get_window_actors()) {
            if (this._isGlassWindow(actor.meta_window))
                this._attachWindowGlass(actor);
        }
    }

    _scheduleWindowGlass(window) {
        if (!this._isGlassWindow(window))
            return;
        let attempts = 0;
        let source = 0;
        source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            if (!this._usesAuroraGtkTheme()) {
                this._windowGlassSources.delete(source);
                return GLib.SOURCE_REMOVE;
            }
            const actor = global.get_window_actors().find(
                candidate => candidate.meta_window === window,
            );
            if (actor) {
                this._attachWindowGlass(actor);
                this._windowGlassSources.delete(source);
                return GLib.SOURCE_REMOVE;
            }
            attempts++;
            if (attempts >= 20) {
                this._windowGlassSources.delete(source);
                return GLib.SOURCE_REMOVE;
            }
            return GLib.SOURCE_CONTINUE;
        });
        this._windowGlassSources.add(source);
    }
}
