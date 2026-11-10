import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// Localzet design tokens are mirrored in stylesheet.css. GNOME Shell does
// not support the full CSS syntax of web browsers (no backdrop-filter).
const MAX_VISIBLE_APPS = 8;

export default class LocalzetShell extends Extension {
    enable() {
        if (this._indicator)
            return;

        this._indicator = new PanelMenu.Button(0.0, 'Localzet OS', false);
        this._indicator.add_style_class_name('localzet-indicator');

        const mark = new St.BoxLayout({
            style_class: 'localzet-brand',
            vertical: false,
        });
        mark.add_child(new St.Icon({
            icon_name: 'applications-system-symbolic',
            style_class: 'system-status-icon localzet-brand-icon',
        }));
        mark.add_child(new St.Label({
            text: 'Localzet',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'localzet-brand-label',
        }));
        this._indicator.add_child(mark);
        this._indicator.menu.box.add_style_class_name('localzet-launcher');

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
            () => this._launch(['localzet-settings']));

        this._search.clutter_text.connect('notify::text', () => {
            this._updateApps(this._search.get_text());
        });
        this._indicator.menu.connect('open-state-changed', (_menu, open) => {
            if (!open)
                return;
            this._search.set_text('');
            this._updateApps('');
            global.stage.set_key_focus(this._search.clutter_text);
        });
        this._updateApps('');
        Main.panel.addToStatusArea(this.uuid, this._indicator, 0, 'left');
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
    }

    _launch(argv) {
        // Fixed commands only; never pass untrusted input to a shell.
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
        this._appsSection = null;
        this._search = null;
    }
}
