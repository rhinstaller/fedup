%define dracutlibdir %{_prefix}/lib/dracut

Name:		fedup
Version:	0.7
Release:	1%{?dist}
Summary:	the Fedora Upgrade tool

License:	GPLv2+
URL:		http://github.com/wgwoods/fedup
Source0:	fedup-%{version}.tar.xz

BuildRequires:  python2-devel
Requires:       systemd

%package dracut
Summary:        initramfs environment for system upgrades
BuildRequires:	rpm-devel >= 4.10.0
Requires:	rpm >= 4.10.0
Requires:       plymouth >= 0.8.6
Requires:       dracut

%package plymouth
Summary:        plymouth theme for system upgrade progress

%description
fedup is the Fedora Upgrade tool.

%description dracut
These dracut modules provide the framework for upgrades and the tool that
actually runs the upgrade itself.

%description plymouth
The plymouth theme used during system upgrade.


%prep
%setup -q


%build
make %{?_smp_mflags}


%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT


%files
%doc README.asciidoc TODO
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

%files dracut
/usr/libexec/system-upgrade-fedora
%{dracutlibdir}/modules.d/85system-upgrade-fedora
%{dracutlibdir}/modules.d/90system-upgrade

%files plymouth
%{_datadir}/plymouth/themes/fedup

%changelog
* Wed Oct 24 2012 Will Woods <wwoods@redhat.com> 0.7-1
- Initial packaging
