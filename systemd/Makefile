# really simple placeholder makefile

.PHONY: all clean

PACKAGES=glib-2.0 rpm ply-boot-client

all: fedora-system-upgrade

fedora-system-upgrade: fedora-system-upgrade.c
	$(CC) $(shell pkg-config $(PACKAGES) --cflags --libs) $(CFLAGS) $< -o $@

clean:
	rm -f fedora-system-upgrade

install:
	install fedora-system-upgrade $(DESTDIR)/usr/lib/systemd
