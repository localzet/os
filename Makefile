PYTHON ?= python3
.PHONY: test extension-zip clean

test:
	$(PYTHON) -m unittest discover -s tests -v
	PYTHONPATH=src $(PYTHON) -m localzet.cli validate

extension-zip:
	mkdir -p dist
	cd extensions && zip -qr ../dist/localzet-shell.zip 'localzet-shell@localzet.com'

clean:
	rm -rf dist
