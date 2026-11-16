import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const COLUMNS = 4;
const FILTERS = [
    ['all', 'Все приложения', []],
    ['system', 'Система', ['System', 'Settings', 'Utility']],
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
        this._menu = new PopupMenu.PopupMenu(anchor, 0.5, St.Side.BOTTOM);
        this._menu.actor.add_style_class_name('localzet-launcher-popup');
        Main.uiGroup.add_child(this._menu.actor);
        this._menu.actor.hide();
        this._manager = new PopupMenu.PopupMenuManager(anchor);
        this._manager.addMenu(this._menu);
        const section = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        this._body = new St.BoxLayout({vertical: true, style_class: 'localzet-launcher'});
        section.add_child(this._body);
        this._menu.addMenuItem(section);
        const title = new St.BoxLayout({style_class: 'localzet-launcher-heading'});
        title.add_child(new St.Label({text: 'Localzet', style_class: 'localzet-launcher-title'}));
        title.add_child(new St.Label({text: 'Приложения', style_class: 'localzet-launcher-caption'}));
        this._body.add_child(title);
        this._entry = new St.Entry({style_class: 'localzet-launcher-search',
            hint_text: 'Поиск приложений', can_focus: true, track_hover: true});
        this._entry.set_primary_icon(new St.Icon({icon_name: 'system-search-symbolic', icon_size: 16}));
        this._body.add_child(this._entry);
        const content = new St.BoxLayout({style_class: 'localzet-launcher-content'});
        this._categories = new St.BoxLayout({vertical: true, style_class: 'localzet-launcher-categories'});
        content.add_child(this._categories);
        this._buttons = new Map();
        const categoryIcons = {"all":"view-app-grid-symbolic","system":"preferences-system-symbolic","development":"applications-development-symbolic","media":"applications-multimedia-symbolic","internet":"applications-internet-symbolic","office":"applications-office-symbolic","games":"applications-games-symbolic"};
        for (const [id, label] of FILTERS) {
            const categoryContent = new St.BoxLayout({style_class: 'localzet-category-content', x_expand: true, x_align: Clutter.ActorAlign.START});
            categoryContent.add_child(new St.Icon({icon_name: categoryIcons[id], icon_size: 15}));
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
        const scroll = new St.ScrollView({style_class: 'localzet-launcher-scroll', x_expand: true,
            overlay_scrollbars: true});
        this._list = new St.BoxLayout({vertical: true, x_expand: true, style_class: 'localzet-launcher-list'});
        scroll.set_child(this._list);
        scroll.set_policy(St.PolicyType.NEVER, St.PolicyType.AUTOMATIC);
        content.add_child(scroll);
        this._body.add_child(content);
        this._count = new St.Label({style_class: 'localzet-launcher-caption'});
        this._body.add_child(this._count);
        const overview = new St.Button({label: 'Рабочие пространства', can_focus: true,
            style_class: 'localzet-launcher-overview'});
        overview.connect('clicked', () => { this.close(); Main.overview.show(); });
        this._body.add_child(overview);

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
                this._entry.set_text('');
                this._refresh();
                global.stage.set_key_focus(this._entry.clutter_text);
                console.log('Localzet Launcher: opened');
            } else {
                console.log('Localzet Launcher: closed');
            }
        });
        this._appsId = this._appSystem.connect('installed-changed', () => {
            if (this._menu.isOpen)
                this._refresh();
        });
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
        this._results = [...unique.values()].filter(app => {
            const info = app.get_app_info();
            const tags = (info.get_categories() ?? '').split(';');
            if (categories.length && !categories.some(tag => tags.includes(tag)))
                return false;
            const text = [app.get_name(), info.get_generic_name(), info.get_description(), app.get_id()]
                .filter(Boolean).join(' ').toLocaleLowerCase();
            return query.split(/\s+/).every(word => text.includes(word));
        }).sort((a, b) => a.get_name().localeCompare(b.get_name()));
        this._firstResult = null;
        this._list.destroy_all_children();
        let row;
        for (const [index, app] of this._results.entries()) {
            if (index % COLUMNS === 0) {
                row = new St.BoxLayout({style_class: 'localzet-launcher-row'});
                this._list.add_child(row);
            }
            const tile = new St.BoxLayout({vertical: true, style_class: 'localzet-launcher-tile',
                x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER});
            const icon = app.create_icon_texture(40);
            icon.set_x_align(Clutter.ActorAlign.CENTER);
            tile.add_child(icon);
            const label = new St.Label({text: app.get_name(), style_class: 'localzet-launcher-label',
                x_align: Clutter.ActorAlign.CENTER});
            label.set_width(92);
            label.set_height(30);
            label.clutter_text.set_line_alignment(Pango.Alignment.CENTER);
            label.clutter_text.set_line_wrap(true);
            label.clutter_text.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR);
            label.clutter_text.ellipsize = Pango.EllipsizeMode.END;
            tile.add_child(label);
            const button = new St.Button({child: tile, can_focus: true, reactive: true,
                style_class: 'localzet-launcher-app', accessible_name: app.get_name()});
            button.connect('clicked', () => this._activate(app));
            row.add_child(button);
            if (!this._firstResult)
                this._firstResult = button;
        }
        if (!this._results.length)
            this._list.add_child(new St.Label({text: 'Приложения не найдены', style_class: 'localzet-launcher-empty'}));
        this._count.set_text('Приложений: ' + this._results.length);
        // Report only counts, never search terms or application inventories.
        console.log('Localzet Launcher: results=' + this._results.length);
    }

    toggle() {
        this._menu.toggle();
    }

    close() {
        if (this._menu.isOpen)
            this._menu.close();
    }

    destroy() {
        this._appSystem.disconnect(this._appsId);
        this._menu.disconnect(this._openId);
        this.close();
        this._manager.removeMenu(this._menu);
        this._menu.destroy();
        this._menu = null;
    }
}
