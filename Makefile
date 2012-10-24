PYTHON=python
VERSION=0.7

all: build

SUBDIRS = dracut plymouth systemd
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
	rm -f fedup-$(VERSION).tar.xz

archive: fedup-$(VERSION).tar.xz

fedup-$(VERSION).tar.xz:
	git archive --format=tar --prefix=fedup-$(VERSION)/ HEAD | xz -c > $@ \
	  || rm $@

.PHONY: all archive install clean $(SUBDIRS) $(INSTALL_TARGETS) $(CLEAN_TARGETS)
