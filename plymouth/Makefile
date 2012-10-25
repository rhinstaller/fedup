THEMESDIR=$(DESTDIR)$(shell pkg-config ply-splash-graphics --variable=themesdir)
THEMENAME=fedup
INSTALL=install -p

all:

install:
	$(INSTALL) -d $(THEMESDIR)$(THEMENAME)
	$(INSTALL) -m644 *.png $(THEMESDIR)$(THEMENAME)
	$(INSTALL) -m644 fedup.plymouth \
		         $(THEMESDIR)$(THEMENAME)/$(THEMENAME).plymouth

clean:

.PHONY: all install clean
