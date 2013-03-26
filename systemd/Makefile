SERVICES=upgrade-prep.service upgrade-switch-root.service
TARGETS=system-upgrade.target upgrade-switch-root.target
SCRIPTS=upgrade-prep.sh
UNITDIR=$(DESTDIR)$(shell pkg-config systemd --variable systemdsystemunitdir)
UTILDIR=$(DESTDIR)/usr/libexec
INSTALL=install -p

all:

ifeq ($(strip $(UNITDIR)),$(DESTDIR))
install: install-scripts
	@echo "no UNITDIR, skipping systemd units"
else
install: install-scripts install-units
endif

install-scripts: $(SCRIPTS)
	$(INSTALL) -d $(UTILDIR)
	$(INSTALL) -m 0755 $(SCRIPTS) $(UTILDIR)

install-units: $(SERVICES) $(TARGETS)
	$(INSTALL) -d $(UNITDIR)
	$(INSTALL) -m 0644 $(SERVICES) $(TARGETS) $(UNITDIR)

clean:

.PHONY: all install install-scripts install-units clean
