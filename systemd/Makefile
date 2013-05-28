SERVICES=upgrade-prep.service upgrade-switch-root.service upgrade-plymouth-switch-root.service start-system-upgrade.service
TARGETS=system-upgrade.target upgrade-switch-root.target
SCRIPTS=upgrade-prep.sh
UNITDIR=$(DESTDIR)$(shell pkg-config systemd --variable systemdsystemunitdir)
UTILDIR=$(DESTDIR)/usr/libexec
GENERATORS=system-upgrade-generator
GENERATORDIR=$(UNITDIR)-generators
INSTALL=install -p

all:

install: $(SERVICES) $(TARGETS) $(SCRIPTS)
	$(INSTALL) -d $(UTILDIR)
	$(INSTALL) -m 0755 $(SCRIPTS) $(UTILDIR)
	$(INSTALL) -d $(UNITDIR)
	$(INSTALL) -m 0644 $(SERVICES) $(TARGETS) $(UNITDIR)
	$(INSTALL) -d $(GENERATORDIR)
	$(INSTALL) -m 0755 $(GENERATORS) $(GENERATORDIR)

clean:

.PHONY: all install clean
