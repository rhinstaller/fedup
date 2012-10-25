PYTHON=python
VERSION=0.7

all: build

SUBDIRS := $(shell ls -d dracut plymouth systemd 2>/dev/null)
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
	rm -f $(ARCHIVES)

ARCHIVES = fedup-$(VERSION).tar.xz fedup-dracut-$(VERSION).tar.xz
archives: $(ARCHIVES)

fedup-$(VERSION).tar.xz:
	git archive --format=tar --prefix=fedup-$(VERSION)/ HEAD \
	  $$(git ls-tree -r HEAD --name-only | grep -v dracut) \
	  | xz -c > $@ || rm $@

fedup-dracut-$(VERSION).tar.xz:
	git archive --format=tar --prefix=fedup-dracut-$(VERSION)/ HEAD \
	  dracut fedup-dracut.spec Makefile \
	  | xz -c > $@ || rm $@

.PHONY: all archives install clean
.PHONY: $(SUBDIRS) $(INSTALL_TARGETS) $(CLEAN_TARGETS)
