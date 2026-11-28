import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {WallpaperGlass} from './wallpaper-glass.js';

const MAX_COLUMNS = 4;
const TILE_WIDTH = 96;
const TILE_HEIGHT = 82;
const SHORT_NAMES = {
    'com.localzet.Apps.desktop': 'Приложения',
    'com.localzet.Settings.desktop': 'Компоненты',
    'com.localzet.Hardware.desktop': 'Оборудование',
    'com.localzet.Containers.desktop': 'Контейнеры',
    'com.localzet.Network.desktop': 'Сеть',
    'com.localzet.WindowsRuntime.desktop': 'Windows Runtime',
    'com.localzet.Connect.desktop': 'Телефон',
    'com.localzet.AIWorkspace.desktop': 'AI Workspace',
};
const displayName = app => SHORT_NAMES[app.get_id()] ?? app.get_name();
const FILTERS = [
    ['all', 'Все', []],
    ['system', 'Система', ['System', 'Settings']],
    ['utility', 'Утилиты', ['Utility']],
    ['development', 'Разработка', ['Development']],
    ['media', 'Медиа', ['AudioVideo', 'Graphics', 'Audio', 'Video']],
    ['internet', 'Интернет', ['Network']],
    ['office', 'Офис', ['Office']],
    ['games', 'Игры', ['Game']],
];

export class AuroraLauncher {
    constructor(anchor) {
        this._appSystem = Shell.AppSystem.get_default();
        this._category = 'all';
        this._results = [];
        this._tiles = [];
        this._columns = MAX_COLUMNS;
        this._favorites = new Gio.Settings({schema_id: 'org.gnome.shell'});
        this._menu = new PopupMenu.PopupMenu(anchor, 0.5, St.Side.BOTTOM);
        this._menu.actor.add_style_class_name('localzet-launcher-popup');
        Main.uiGroup.add_child(this._menu.actor);
        this._menu.actor.hide();
        this._contrast = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'});
        this._contrastId = this._contrast.connect('changed::high-contrast', () => this._refreshMaterial());
        this._refreshMaterial();
        this._wallpaperGlass = new WallpaperGlass(this._menu);
        this._manager = new PopupMenu.PopupMenuManager(anchor);
        this._manager.addMenu(this._menu);
        const section = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        this._body = new St.BoxLayout({vertical: true, style_class: 'localzet-launcher'});
        section.add_child(this._body);
        this._menu.addMenuItem(section);
        this._entry = new St.Entry({style_class: 'localzet-launcher-search',
            hint_text: 'Поиск приложений…', can_focus: true, track_hover: true});
        this._entry.set_primary_icon(new St.Icon({icon_name: 'system-search-symbolic', icon_size: 16}));
        this._body.add_child(this._entry);
        const content = new St.BoxLayout({style_class: 'localzet-launcher-content'});
        this._categories = new St.BoxLayout({vertical: true, style_class: 'localzet-launcher-categories'});
        content.add_child(this._categories);
        this._buttons = new Map();
        const categoryIcons = {"all":"view-app-grid-symbolic","system":"preferences-system-symbolic","utility":"applications-utilities-symbolic","development":"applications-development-symbolic","media":"applications-multimedia-symbolic","internet":"applications-internet-symbolic","office":"applications-office-symbolic","games":"applications-games-symbolic"};
        for (const [id, label] of FILTERS) {
            const categoryContent = new St.BoxLayout({style_class: 'localzet-category-content', x_expand: true, x_align: Clutter.ActorAlign.START});
            categoryContent.add_child(new St.Icon({icon_name: categoryIcons[id], icon_size: 18}));
            categoryContent.add_child(new St.Label({text: label, y_align: Clutter.ActorAlign.CENTER}));
            const button = new St.Button({child: categoryContent, accessible_name: label, can_focus: true, reactive: true,
                x_expand: true, style_class: 'localzet-launcher-category'});
            button.connect('clicked', () => {
                this._category = id;
                this._refresh();
            });
            this._buttons.set(id, button);
            this._categories.add_child(button);
        }
        const main = new St.BoxLayout({vertical: true, x_expand: true, style_class: 'localzet-launcher-main'});
        const heading = new St.BoxLayout({style_class: 'localzet-launcher-heading'});
        this._heading = new St.Label({text: 'Приложения', x_expand: true, style_class: 'localzet-launcher-title'});
        this._count = new St.Label({style_class: 'localzet-launcher-caption', y_align: Clutter.ActorAlign.CENTER});
        heading.add_child(this._heading);
        heading.add_child(this._count);
        main.add_child(heading);
        const scroll = new St.ScrollView({style_class: 'localzet-launcher-scroll', x_expand: true,
            overlay_scrollbars: true});
        this._scroll = scroll;
        this._list = new St.BoxLayout({vertical: true, x_expand: true, style_class: 'localzet-launcher-list'});
        scroll.set_child(this._list);
        scroll.set_policy(St.PolicyType.NEVER, St.PolicyType.AUTOMATIC);
        main.add_child(scroll);
        content.add_child(main);
        this._body.add_child(content);
        const footer = new St.BoxLayout({style_class: 'localzet-launcher-footer'});
        const catalog = this._appSystem.lookup_app('com.localzet.Apps.desktop');
        if (catalog) {
            const appsButton = new St.Button({label: 'Центр приложений', can_focus: true,
                style_class: 'localzet-launcher-overview'});
            appsButton.connect('clicked', () => this._activate(catalog));
            footer.add_child(appsButton);
        }
        const overview = new St.Button({label: 'Рабочие пространства', can_focus: true,
            style_class: 'localzet-launcher-overview'});
        overview.connect('clicked', () => { this.close(); Main.overview.show(); });
        footer.add_child(overview);
        footer.add_child(new St.Widget({x_expand: true}));
        const settings = new St.Button({child: new St.Icon({icon_name: 'preferences-system-symbolic', icon_size: 18}),
            accessible_name: 'Настройки', can_focus: true, style_class: 'localzet-launcher-footer-action'});
        settings.connect('clicked', () => {
            const app = this._appSystem.lookup_app('org.gnome.Settings.desktop');
            if (app) this._activate(app);
        });
        settings.visible = !!this._appSystem.lookup_app('org.gnome.Settings.desktop');
        footer.add_child(settings);
        this._body.add_child(footer);

        this._entry.clutter_text.connect('text-changed', () => this._refresh());
        this._entry.clutter_text.connect('activate', () => {
            if (this._results.length)
                this._activate(this._results[0]);
        });
        this._entry.clutter_text.connect('key-press-event', (_actor, event) => {
            if (event.get_key_symbol() === Clutter.KEY_Down && this._firstResult?.can_focus) {
                global.stage.set_key_focus(this._firstResult);
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        this._openId = this._menu.connect('open-state-changed', (_menu, open) => {
            if (open) {
                this._category = 'all';
                const monitor = Main.layoutManager.primaryMonitor;
                this._columns = Math.max(2, Math.min(MAX_COLUMNS, Math.floor(((monitor?.width ?? 800) - 248) / TILE_WIDTH)));
                this._body.set_width(190 + this._columns * TILE_WIDTH);
                this._entry.set_text('');
                this._refresh();
                global.stage.set_key_focus(this._entry.clutter_text);
                console.log('Localzet Launcher: opened');
                // Report geometry after the menu allocation/animation.
                // Geometry contains no user data and is also required by the installed-session optical smoke.
                if (!this._geometrySource)
                    this._geometrySource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 450, () => {
                        this._geometrySource = 0;
                        if (this._menu?.isOpen) {
                            const [x, y] = this._menu.actor.get_transformed_position();
                            const [w, h] = this._menu.actor.get_transformed_size();
                            console.log('Localzet Launcher: bounds=' +
                                [x, y, w, h].map(Math.round).join(','));
                        }
                        return GLib.SOURCE_REMOVE;
                    });
            } else {
                console.log('Localzet Launcher: closed');
            }
        });
        this._favoritesId = this._favorites.connect('changed::favorite-apps', () => {
            if (this._menu.isOpen) this._refresh();
        });
        this._appsId = this._appSystem.connect('installed-changed', () => {
            if (this._menu.isOpen)
                this._refresh();
        });
    }

    _refreshMaterial() {
        const highContrast = this._contrast.get_boolean('high-contrast');
        this._menu.actor[highContrast ? 'add_style_class_name' : 'remove_style_class_name']('localzet-launcher-contrast');
        if (highContrast || GLib.getenv('LOCALZET_DISABLE_GLASS') === '1')
            console.log('Localzet Glass: launcher opaque fallback');
        // WallpaperGlass owns the real Shell.BlurEffect BACKGROUND lifecycle.
    }

    _activate(app) {
        this.close();
        try {
            app.activate();
            console.log('Localzet Launcher: activated ' + app.get_id());
        } catch (error) {
            console.error('Localzet Launcher: activation failed: ' + error);
        }
    }

    _refresh() {
        const query = this._entry.get_text().trim().toLocaleLowerCase();
        const categories = FILTERS.find(row => row[0] === this._category)?.[2] ?? [];
        for (const [id, button] of this._buttons)
            button[id === this._category ? 'add_style_pseudo_class' : 'remove_style_pseudo_class']('checked');
        const installed = this._appSystem.get_installed();
        const apps = installed.map(info => this._appSystem.lookup_app(info.get_id()))
            .filter(app => app && app.get_app_info().should_show());
        const unique = new Map(apps.map(app => [app.get_id(), app]));
        const favorites = new Map(this._favorites.get_strv('favorite-apps').map((id, index) => [id, index]));
        const favoriteRank = app => !query && this._category === 'all' ? (favorites.get(app.get_id()) ?? 10000) : 0;
        this._results = [...unique.values()].filter(app => {
            const info = app.get_app_info();
            const tags = (info.get_categories() ?? '').split(';');
            if (!query && categories.length && !categories.some(tag => tags.includes(tag)))
                return false;
            const text = [app.get_name(), displayName(app), info.get_generic_name(), info.get_description(), app.get_id(), ...(info.get_keywords?.() ?? [])]
                .filter(Boolean).join(' ').toLocaleLowerCase();
            return query.split(/\s+/).every(word => text.includes(word));
        }).sort((a, b) => favoriteRank(a) - favoriteRank(b) || a.get_name().localeCompare(b.get_name()));
        // Reference composition: a single real application grid with
        // favorites first, no duplicate cards or empty promotional panels.
        this._heading.set_text(query ? 'Результаты поиска' :
            this._category === 'all' ? 'Все приложения' : FILTERS.find(row => row[0] === this._category)[1]);
        this._tiles = [];
        this._firstResult = null;
        this._list.destroy_all_children();
        const monitor = Main.layoutManager.primaryMonitor;
        const rows = Math.max(2, Math.min(4, Math.floor(((monitor?.height ?? 720) - 290) / TILE_HEIGHT)));
        this._scroll.set_height(rows * TILE_HEIGHT);
        let row;
        for (const [index, app] of this._results.entries()) {
            if (index % this._columns === 0) {
                row = new St.BoxLayout({style_class: 'localzet-launcher-row'});
                this._list.add_child(row);
            }
            const tile = new St.BoxLayout({vertical: true, style_class: 'localzet-launcher-tile',
                x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER});
            const icon = app.create_icon_texture(40);
            icon.set_x_align(Clutter.ActorAlign.CENTER);
            tile.add_child(icon);
            const label = new St.Label({text: displayName(app), style_class: 'localzet-launcher-label',
                x_align: Clutter.ActorAlign.CENTER});
            label.set_width(88);
            label.set_height(34);
            label.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
            label.clutter_text.set_line_wrap(true);
            label.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
            label.clutter_text.set_single_line_mode(false);
            label.clutter_text.ellipsize = Pango.EllipsizeMode.END;
            tile.add_child(label);
            const button = new St.Button({child: tile, can_focus: true, reactive: true,
                style_class: 'localzet-launcher-app', accessible_name: app.get_name()});
            button.connect('clicked', () => this._activate(app));
            button.connect('key-press-event', (_actor, event) => this._navigate(index, event));
            this._tiles.push(button);
            row.add_child(button);
            if (!this._firstResult)
                this._firstResult = button;
        }
        console.log('Localzet Launcher: columns=' + this._columns + ' rows=' + rows);
        if (!this._results.length)
            this._list.add_child(new St.Label({text: 'Приложения не найдены', style_class: 'localzet-launcher-empty'}));
        this._count.set_text('Приложений: ' + this._results.length);
        // Report only counts, never search terms or application inventories.
        console.log('Localzet Launcher: results=' + this._results.length);
    }

    _navigate(index, event) {
        const key = event.get_key_symbol();
        let next = index;
        if (key === Clutter.KEY_Left) next--;
        else if (key === Clutter.KEY_Right) next++;
        else if (key === Clutter.KEY_Up) next -= this._columns;
        else if (key === Clutter.KEY_Down) next += this._columns;
        else if (key === Clutter.KEY_Home) next = 0;
        else if (key === Clutter.KEY_End) next = this._tiles.length - 1;
        else return Clutter.EVENT_PROPAGATE;
        if (next < 0 && key === Clutter.KEY_Up)
            global.stage.set_key_focus(this._entry.clutter_text);
        else if (this._tiles[next])
            global.stage.set_key_focus(this._tiles[next]);
        return Clutter.EVENT_STOP;
    }

    toggle() {
        this._menu.toggle();
    }

    close() {
        if (this._menu.isOpen)
            this._menu.close();
    }

    destroy() {
        this._wallpaperGlass.destroy();
        if (this._geometrySource)
            GLib.source_remove(this._geometrySource);
        this._geometrySource = 0;
        this._contrast.disconnect(this._contrastId);
        this._appSystem.disconnect(this._appsId);
        this._favorites.disconnect(this._favoritesId);
        this._menu.disconnect(this._openId);
        this.close();
        this._manager.removeMenu(this._menu);
        this._menu.destroy();
        this._menu = null;
    }
}
