Name:           fedup
Version:        0.7
Release:        1%{?dist}
Summary:        the Fedora Upgrade tool

License:        GPLv2+
URL:            http://github.com/wgwoods/fedup
Source0:        %{name}-%{version}.tar.xz

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
%doc README.asciidoc TODO COPYING
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
#%files gtk
#%{_bindir}/fedup-gtk
#%{_datadir}/fedup/ui

%changelog
* Wed Oct 24 2012 Will Woods <wwoods@redhat.com> 0.7-1
- Initial packaging
