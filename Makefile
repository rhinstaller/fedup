PYTHON=python
VERSION=0.8.0

all: build

SUBDIRS := systemd man
$(SUBDIRS):
	$(MAKE) -C $@

INSTALL_TARGETS = $(SUBDIRS:%=install-%)
$(INSTALL_TARGETS):
	$(MAKE) -C $(@:install-%=%) install

CLEAN_TARGETS = $(SUBDIRS:%=clean-%)
$(CLEAN_TARGETS):
	$(MAKE) -C $(@:clean-%=%) clean

build: $(SUBDIRS)
	$(PYTHON) setup.py build

install: all $(INSTALL_TARGETS)
	$(PYTHON) setup.py install --skip-build --root $(DESTDIR)/

clean: $(CLEAN_TARGETS)
	$(PYTHON) setup.py clean
	rm -rf build
	rm -f $(ARCHIVE)

ARCHIVE = fedup-$(VERSION).tar.xz
archive: $(ARCHIVE)
fedup-$(VERSION).tar.xz: $(shell git ls-tree -r --name-only HEAD)
	git archive --format=tar --prefix=fedup-$(VERSION)/ HEAD \
	  | xz -c > $@ || rm $@

.PHONY: all archive install clean
.PHONY: $(SUBDIRS) $(INSTALL_TARGETS) $(CLEAN_TARGETS)
