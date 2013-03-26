INSTALL=install -p
MANDIR=/usr/share/man
mandir=$(MANDIR)
man8dir=$(mandir)/man8

MAN8PAGES=fedup.8
MANPAGES=$(MAN8PAGES)

all: $(MANPAGES)

$(MANPAGES): %: %.asciidoc
	-a2x --format=manpage $<

install: $(MANPAGES)
	$(INSTALL) -d $(DESTDIR)$(man8dir)
	-$(INSTALL) $(MAN8PAGES) $(DESTDIR)$(man8dir)

clean:
	rm -f $(MANPAGES) $(MANPAGES:%=%.xml)

.PHONY: all install clean
