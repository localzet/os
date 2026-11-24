# Приёмка Aurora: нативный интерфейс

## Цель и контракт

Целевая тема по умолчанию — Aurora Blue. Aurora Purple и Aurora Black —
равноправные альтернативы. Цветовые значения закреплены в
`assets/design-tokens.json`; выбор доступен только в Settings → Appearance,
переключателя в верхней панели нет.

Утверждённые владельцем PNG Blue/Purple/Black просмотрены из закрытого архива;
в публичный репозиторий они не копировались. Это концепт-board, а не снимки
работающей GNOME. В реализацию перенесены first-party SVG и горные WebP-обои.
Сторонние логотипы не рисуются и не включаются в пакет. PR #73 развивает
отдельную тему `Aurora`; эта ветка использует один системный идентификатор
темы `Localzet` с fallback Adwaita/hicolor. Согласование зафиксировано в
комментарии к PR #73; конкурирующее слияние не является частью этой работы.

## Изменения этой ветки

- `Localzet` объявляет восемь scalable-контекстов freedesktop, 16–256 px и
  fallback `Adwaita,hicolor`.
- Desktop entries Localzet используют first-party `Icon=` и AppStream metadata.
- Appearance применяет пользовательские обои, dark scheme, системный accent
  color, иконки и акцент Localzet Shell. Перед первым изменением сохраняется
  исходный снимок; ошибки отката сохраняют данные восстановления.
  Apply/restore используют общий
  межпроцессный lock.
- Первые значения Live-сессии: горные Aurora Blue wallpaper, тема значков
  `Localzet`, dark scheme и Blue-акцент. Ручной вход в Appearance не требуется.
- Dock обновляет pinned apps при изменении `changed::pinned-apps` и освобождает
  подписку при уничтожении.
- Top bar остаётся компактной, без переключателя темы. Dock glyphs — 38 px;
  размеры и скругления Shell умеренные.
- Dock и launcher используют GNOME `Shell.BlurEffect` с radius 18, умеренной
  прозрачностью, границами и тенями из утверждённых токенов. Если эффект
  недоступен, остаётся прозрачная поверхность без blur. Скругления, контраст и
  производительность нужно оценить на реальных GNOME кадрах.

## Доказательства и открытые gates

| Gate | Статус | Что требуется |
| --- | --- | --- |
| Approved PNG источники | PASS (reviewed) | Оригиналы Blue/Purple/Black просмотрены; это концепт-board, не GNOME captures |
| SVG, index и размеры 16/20/24/32/48/64/128/256 px | PASS (previous run) | Ветка до текущих правок: 120 SVG масштабировались через GdkPixbuf во всех восьми размерах |
| Первая оптическая проверка иконок | PARTIAL | Contact sheet ранее осмотрен; геометрию и разрешение имён нужно перепроверить в реальной GNOME-сессии |
| DEB, icon cache и GSettings schema | PASS (previous run) | Ранее собранный DEB проверен во временном каталоге; повторить после итоговых правок |
| Shell extension bundle | PASS (previous run) | Ранее проверен ZIP и schema; повторить после итоговых правок |
| Metadata desktop entries | PASS (previous run) | `desktop-file-validate`, AppStream; повторить в итоговом цикле |
| Apply/rollback/restore concurrency | PENDING | Регрессионные тесты добавлены; выполнить актуальный `make test` и UI-сценарий |
| Dock pinned-app signal lifecycle | PENDING | Обработчик и disconnect добавлены; выполнить проверки и осмотреть полный Dock |
| First-login defaults | PENDING | Проверить кадр полной Live-сессии: Aurora Blue mountains и `Localzet` icon theme |
| GTK icon lookup и Shell журнал | PENDING | QEMU-гость проверяет фактические 120 локальных SVG-имён, upstream Nautilus/Ptyxis и `JS ERROR` после полного сценария |
| GNOME 50 Wayland captures | PENDING | QEMU framebuffer: desktop/Dock, Nautilus, Launcher, Quick Settings, Appearance, Settings, notifications для каждой темы и restore |
| Comparison to approved PNG | NOT ACCEPTED | Вручную осмотреть все сцены, записать конкретные расхождения и исправить их до решения владельца |
| Ранее снятые DevKit/Xvfb кадры | REJECTED | Blue/Purple/Black различались менее чем на 0,01% пикселей и не подтверждали качество всей сессии |
| QEMU BIOS/UEFI boot-marker | PASS (previous run) | Проверка загрузки не является тестом установки или дизайн-приёмкой |
| Визуальная приёмка владельцем | OPEN | PR #137 оставить draft до явного принятия результата |

Скриншоты снимаются из полноценной Ubuntu 26.04 / GNOME 50 Wayland Live-сессии
через QEMU QMP framebuffer, а не GNOME Shell screenshot API. Происхождение и
SHA-256 каждого кадра пишутся в `manifest.json`. Успешный CI-захват подтверждает
только наличие кадров; он не выставляет качество UI и не закрывает визуальный
gate. Рабочий GNOME-хост и его настройки не используются для обхода запретов
screenshot/D-Bus.

## Локальные проверки

```sh
make test
make desktop-deb
make extension-zip
```

Подробности runtime-проверки и ручного сравнения: [`GNOME-50-SMOKE.md`](GNOME-50-SMOKE.md).
