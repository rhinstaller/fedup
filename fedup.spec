Name:           fedup
Version:        0.7.1
Release:        1%{?dist}
Summary:        The Fedora Upgrade tool

License:        GPLv2+
URL:            https://github.com/wgwoods/fedup
Source0:        https://github.com/downloads/wgwoods/fedup/%{name}-%{version}.tar.xz

BuildRequires:  python2-devel
Requires:       systemd
BuildArch:      noarch

%description
fedup is the Fedora Upgrade tool.


%prep
%setup -q

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --skip-build --root $RPM_BUILD_ROOT
make install-systemd DESTDIR=$RPM_BUILD_ROOT


%files
%doc README.asciidoc TODO.asciidoc COPYING
# systemd stuff
%{_unitdir}/system-upgrade.target
%{_unitdir}/upgrade-prep.service
%{_unitdir}/upgrade-switch-root.service
%{_unitdir}/upgrade-switch-root.target
%{_unitdir}/../upgrade-prep.sh
# python library
%{python_sitelib}/fedup*
# binaries
%{_bindir}/fedup-cli

#TODO - finish and package gtk-based GUI
#files gtk
#{_bindir}/fedup-gtk
#{_datadir}/fedup/ui

%changelog
* Mon Nov 19 2012 Will Woods <wwoods@redhat.com> 0.7.1-1
- Add --clean commandline argument
- Fix grubby traceback (#872088)
- Fetch kernel/initrd and set up bootloader
- Work around data-corrupting umount bug (#873459)
- Add support for upgrades from media (--device)

* Wed Oct 24 2012 Will Woods <wwoods@redhat.com> 0.7-1
- Initial packaging
