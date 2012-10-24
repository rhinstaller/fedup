# really simple makefile

.PHONY: all clean install

PACKAGES=glib-2.0 rpm

# TODO: use ply-boot-client
#PACKAGES+=ply-boot-client
#CFLAGS+=-DUSE_PLYMOUTH_LIBS

dracutdir=$(DESTDIR)/usr/lib/dracut/modules.d
bindir=$(DESTDIR)/usr/libexec

all: system-upgrade-fedora

system-upgrade-fedora: system-upgrade-fedora.c
	$(CC) $(shell pkg-config $(PACKAGES) --cflags --libs) $(CFLAGS) $< -o $@

clean:
	rm -f system-upgrade-fedora

install:
	install system-upgrade-fedora $(bindir)
	install -d $(dracutdir)
	for d in 90system-upgrade 85system-upgrade-fedora; do \
	    install -d $(dracutdir)/$$d; \
	    for f in $$d/*; do \
	        install $$f $(dracutdir)/$$d; \
	    done; \
	done
