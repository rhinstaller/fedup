dracutdir = $(DESTDIR)/usr/lib/dracut/modules.d
libexecdir = $(DESTDIR)/usr/libexec

system_upgrade_DIR = 90system-upgrade
system_upgrade_SCRIPTS = module-setup.sh \
			 upgrade-init.sh \
			 upgrade-pre-pivot.sh \
			 upgrade-pre.sh \
			 upgrade.sh \
			 upgrade-post.sh
system_upgrade_DATA = README.txt \
		      upgrade.target \
		      upgrade-pre.service \
		      upgrade.service \
		      upgrade-post.service \
		      upgrade-debug-shell.service

system_upgrade_fedora_DIR = 85system-upgrade-fedora
system_upgrade_fedora_SCRIPTS = module-setup.sh \
				keep-initramfs.sh \
				do-upgrade.sh \
				save-journal.sh

all: system-upgrade-fedora

PACKAGES=glib-2.0 rpm
# TODO: use ply-boot-client
#PACKAGES+=ply-boot-client
#CFLAGS+=-DUSE_PLYMOUTH_LIBS

system-upgrade-fedora: system-upgrade-fedora.c
	$(CC) $(shell pkg-config $(PACKAGES) --cflags --libs) $(CFLAGS) $< -o $@

clean:
	rm -f system-upgrade-fedora

install: install-scripts install-data
	install -d $(libexecdir)
	install system-upgrade-fedora $(libexecdir)

install-dirs:
	install -d $(dracutdir)/$(system_upgrade_DIR)
	install -d $(dracutdir)/$(system_upgrade_fedora_DIR)

install-scripts: install-dirs
	cd $(system_upgrade_DIR); \
	  install $(system_upgrade_SCRIPTS) \
		  $(dracutdir)/$(system_upgrade_DIR)
	cd $(system_upgrade_fedora_DIR); \
	  install $(system_upgrade_fedora_SCRIPTS) \
	          $(dracutdir)/$(system_upgrade_fedora_DIR)

install-data: install-dirs
	cd $(system_upgrade_DIR); \
	  install -m644 $(system_upgrade_DATA) \
	                $(dracutdir)/$(system_upgrade_DIR)

.PHONY: all install clean install-dirs install-scripts install-data
