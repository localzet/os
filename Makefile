PYTHON ?= python3
.PHONY: test extension-zip clean

test:
	$(PYTHON) -m unittest discover -s tests -v
	PYTHONPATH=src $(PYTHON) -m localzet.cli validate

extension-zip:
	@command -v gnome-extensions >/dev/null || { echo "gnome-extensions is required (use Ubuntu 26.04 or CI)" >&2; exit 2; }
	mkdir -p dist
	gnome-extensions pack --force --out-dir dist extensions/localzet-shell@localzet.com
	$(PYTHON) scripts/verify-shell-bundle.py dist/localzet-shell@localzet.com.shell-extension.zip

clean:
	rm -rf dist
