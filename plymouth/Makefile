THEMESDIR=$(DESTDIR)$(shell pkg-config ply-splash-graphics --variable=themesdir)
THEMENAME=fedup

all:

install:
	install -d $(THEMESDIR)$(THEMENAME)
	install -m644 *.png $(THEMESDIR)$(THEMENAME)
	install -m644 fedup.plymouth \
		      $(THEMESDIR)$(THEMENAME)/$(THEMENAME).plymouth

clean:

.PHONY: all install clean
