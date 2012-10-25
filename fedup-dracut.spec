%define dracutlibdir %{_prefix}/lib/dracut

Name:		fedup-dracut
Version:	0.7
Release:	1%{?dist}
Summary:	the Fedora Upgrade tool

License:	GPLv2+
URL:		http://github.com/wgwoods/fedup
Source0:	%{name}-%{version}.tar.xz

Summary:        initramfs environment for system upgrades
BuildRequires:	rpm-devel >= 4.10.0
Requires:	rpm >= 4.10.0
Requires:       plymouth >= 0.8.6
Requires:       dracut

%description
These dracut modules provide the framework for upgrades and the tool that
actually runs the upgrade itself.

%prep
%setup -q


%build
make %{?_smp_mflags} dracut


%install
rm -rf $RPM_BUILD_ROOT
make install-dracut DESTDIR=$RPM_BUILD_ROOT


%files
/usr/libexec/system-upgrade-fedora
%{dracutlibdir}/modules.d/85system-upgrade-fedora
%{dracutlibdir}/modules.d/90system-upgrade

%changelog
* Wed Oct 24 2012 Will Woods <wwoods@redhat.com> 0.7-1
- Initial packaging
