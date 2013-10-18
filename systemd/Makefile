SERVICES=upgrade-prep.service upgrade-switch-root.service
TARGETS=system-upgrade.target upgrade-switch-root.target
SCRIPTS=upgrade-prep.sh
GENERATORS=system-upgrade-generator
UNITDIR=$(DESTDIR)$(shell pkg-config systemd --variable systemdsystemunitdir)
UTILDIR=$(DESTDIR)/usr/libexec
ifeq ($(strip $(UTILDIR)),$(DESTDIR))
  # Older systemd doesn't have this in its pkg-config, so..
  UTILDIR=$(UNITDIR)/..
endif
GENERATORDIR=$(DESTDIR)$(shell pkg-config systemd --variable systemdutildir)/system-generators
INSTALL=install -p

all:

install: $(SERVICES) $(TARGETS) $(SCRIPTS)
	$(INSTALL) -d $(UTILDIR)
	$(INSTALL) -m 0755 $(SCRIPTS) $(UTILDIR)
	$(INSTALL) -d $(UNITDIR)
	$(INSTALL) -m 0644 $(SERVICES) $(TARGETS) $(UNITDIR)
	$(INSTALL) -m 0755 $(GENERATORS) $(GENERATORDIR)

clean:

.PHONY: all install clean
