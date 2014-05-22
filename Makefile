PYTHON=python
VERSION=0.9.0
RELEASE_TAG=0.8.1

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

version:
	echo 'version="$(VERSION)"' > fedup/version.py
	sed -ri 's/(Version:\s*)\S*/\1$(VERSION)/' fedup.spec


ARCHIVE = fedup-$(RELEASE_TAG).tar.xz
archive: $(ARCHIVE)
$(ARCHIVE):
	git archive --format=tar --prefix=fedup-$(RELEASE_TAG)/ $(RELEASE_TAG) \
	  | xz -c > $@ || rm $@

# VERSION-pre<commits-since-last-tag>-g<head-commit-id-short>
# e.g.: 0.9.0-pre7-gedf04c5
SNAPSHOT_VERSION=$(VERSION)-pre$(shell git describe --tags --match '*.*.*' | cut -d- -f2-3)
SNAPSHOT = fedup-$(SNAPSHOT_VERSION).tar.xz
snapshot: $(SNAPSHOT)
$(SNAPSHOT):
	git archive --format=tar --prefix=fedup-$(SNAPSHOT_VERSION)/ HEAD \
	  | xz -c > $@ || rm $@

.PHONY: all archive install clean version
.PHONY: $(ARCHIVE) $(SNAPSHOT) $(SUBDIRS) $(INSTALL_TARGETS) $(CLEAN_TARGETS)
