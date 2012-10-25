SERVICES=upgrade-prep.service upgrade-switch-root.service
TARGETS=system-upgrade.target upgrade-switch-root.target
SCRIPTS=upgrade-prep.sh
UTILDIR=$(DESTDIR)$(shell pkg-config systemd --variable systemdutildir)
UNITDIR=$(DESTDIR)$(shell pkg-config systemd --variable systemdsystemunitdir)
INSTALL=install -p

all:

install: $(SERVICES) $(TARGETS) $(SCRIPTS)
	$(INSTALL) -d $(UTILDIR)
	$(INSTALL) -m 0755 $(SCRIPTS) $(UTILDIR)
	$(INSTALL) -d $(UNITDIR)
	$(INSTALL) -m 0644 $(SERVICES) $(TARGETS) $(UNITDIR)

clean:

.PHONY: all install clean
