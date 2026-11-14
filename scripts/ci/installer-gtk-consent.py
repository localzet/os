"""GTK consent integration test; no host disks or real sudo calls."""
from __future__ import annotations
import json
from unittest.mock import patch

from localzet.installer import app


class FakeProcess:
    def __init__(self):
        self.requests = []
        self.callback = None
        self.success = True

    def communicate_utf8_async(self, payload, cancellable, callback):
        self.requests.append(json.loads(payload))
        self.callback = callback

    def communicate_utf8_finish(self, result):
        return True, "fixture result", ""

    def get_successful(self):
        return self.success


def main():
    payload = {"blockdevices": [
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "type": "disk",
         "model": "Fixture SSD", "serial": "FIXTURE-SSD", "size": 64 * 1024**3,
         "ro": False, "rm": False, "rota": False, "tran": "nvme",
         "children": []},
        {"name": "sdb", "path": "/dev/sdb", "type": "disk",
         "model": "Live USB", "serial": "LIVE-USB", "size": 8 * 1024**3,
         "ro": False, "rm": True, "rota": False, "tran": "usb",
         "children": []},
    ]}
    fake = FakeProcess()
    with patch.object(app, "read_lsblk", return_value=payload), \
         patch.object(app, "live_source_disk", return_value="/dev/sdb"), \
         patch.object(app, "spawn_backend", return_value=fake) as spawn:
        wizard = app.create_application()
        assert wizard.register(None)
        wizard.activate()
        assert wizard.plan["selected_identity"] == "serial:FIXTURE-SSD"
        assert not wizard.install.get_sensitive()
        wizard.start()
        spawn.assert_not_called()
        wizard.username.set_text("tester")
        wizard.password.set_text("fixture-password")
        wizard.repeat.set_text("wrong-password")
        wizard.confirm.set_text("INSTALL serial:FIXTURE-SSD")
        wizard.backup.set_active(True)
        assert not wizard.install.get_sensitive()
        wizard.repeat.set_text("fixture-password")
        wizard.confirm.set_text("INSTALL serial:WRONG")
        assert not wizard.install.get_sensitive()
        wizard.confirm.set_text("INSTALL serial:FIXTURE-SSD")
        wizard.backup.set_active(False)
        assert not wizard.install.get_sensitive()
        wizard.backup.set_active(True)
        assert wizard.install.get_sensitive()
        wizard.install.emit("clicked")
        spawn.assert_called_once_with()
        assert wizard.running and not wizard.install.get_sensitive()
        assert not wizard.refresh_button.get_sensitive()
        assert wizard.password.get_text() == wizard.repeat.get_text() == ""
        assert len(fake.requests) == 1
        request = fake.requests[0]
        assert request["plan"]["selected_identity"] == "serial:FIXTURE-SSD"
        assert request["confirmation"] == "INSTALL serial:FIXTURE-SSD"
        assert request["backup_acknowledged"] is True
        assert request["username"] == "tester"
        assert request["password"] == "fixture-password"
        wizard.start()
        wizard.refresh()
        spawn.assert_called_once_with()
        assert wizard.running
        fake.callback(fake, None)
        assert not wizard.running and wizard.plan is None
        assert not wizard.install.get_sensitive()
        assert wizard.refresh_button.get_sensitive()
        assert not wizard.backup.get_active()
        assert wizard.confirm.get_text() == ""
        # A failed spawn also discards the reviewed plan and unlocks the form.
        wizard.refresh()
        wizard.password.set_text("fixture-password")
        wizard.repeat.set_text("fixture-password")
        wizard.confirm.set_text("INSTALL serial:FIXTURE-SSD")
        wizard.backup.set_active(True)
        spawn.side_effect = OSError("fixture launch failure")
        wizard.install.emit("clicked")
        assert not wizard.running and wizard.plan is None
        assert not wizard.install.get_sensitive()
        assert wizard.username.get_sensitive()
        assert wizard.refresh_button.get_sensitive()
        assert not wizard.backup.get_active()
        # Inventory with another internal disk is blocked even after refresh.
        payload["blockdevices"].append(dict(payload["blockdevices"][0],
            name="nvme1n1", path="/dev/nvme1n1", serial="OTHER"))
        wizard.refresh()
        assert wizard.plan is None
        assert not wizard.install.get_sensitive()
        wizard.window.destroy()
        wizard.quit()
    print("PASS: GTK consent, exact request, duplicate guard, failure reset, extra disk rejection")


if __name__ == "__main__":
    main()
