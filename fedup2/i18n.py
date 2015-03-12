import gettext
t = gettext.translation("fedup", "/usr/share/locale", fallback=True)
_ = t.lgettext
