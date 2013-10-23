INSTALL=install -p
SED=sed

UNITDIR=$(shell pkg-config systemd --variable systemdsystemunitdir)
UTILDIR=$(shell pkg-config systemd --variable systemdutildir)
LIBEXECDIR=/usr/libexec

SERVICES=upgrade-prep.service upgrade-switch-root.service
TARGETS=system-upgrade.target upgrade-switch-root.target

unit_DATA=$(SERVICES) $(TARGETS)
unit_DIR=$(UNITDIR)

prep_SCRIPTS=upgrade-prep.sh
prep_DIR=$(LIBEXECDIR)

generator_SCRIPTS=system-upgrade-generator
generator_DIR=$(UTILDIR)/system-generators

GENFILES = system-upgrade-generator upgrade-prep.service

DATA = $(unit_DATA)
SCRIPTS = $(prep_SCRIPTS) $(generator_SCRIPTS)

all: $(DATA) $(SCRIPTS)

$(GENFILES): %: %.in
	$(SED) \
	  -e 's,@UNITDIR@,$(UNITDIR),g' \
	  -e 's,@LIBEXECDIR@,$(LIBEXECDIR),g' \
	$< > $@

clean:
	rm -f $(GENFILES)

install: $(SERVICES) $(TARGETS) $(SCRIPTS)
	$(INSTALL) -d $(DESTDIR)$(unit_DIR)
	$(INSTALL) -m 0644 $(unit_DATA) $(DESTDIR)$(unit_DIR)
	$(INSTALL) -d $(DESTDIR)$(prep_DIR)
	$(INSTALL) -m 0755 $(prep_SCRIPTS) $(DESTDIR)$(prep_DIR)
	$(INSTALL) -d $(DESTDIR)$(generator_DIR)
	$(INSTALL) -m 0755 $(generator_SCRIPTS) $(DESTDIR)$(generator_DIR)

clean:

.PHONY: all install clean
