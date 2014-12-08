Name:           fedup
Version:        0.9.1
Release:        1%{?dist}
Summary:        The Fedora Upgrade tool

License:        GPLv2+
URL:            https://github.com/wgwoods/fedup
Source0:        https://github.com/downloads/wgwoods/fedup/%{name}-%{version}.tar.xz

Requires:       systemd >= 183
Requires:       grubby
Requires:       yum

BuildRequires:  python-libs
BuildRequires:  systemd-devel
BuildRequires:  asciidoc
BuildArch:      noarch

# GET THEE BEHIND ME, SATAN
Obsoletes:      preupgrade

%description
fedup is the Fedora Upgrade tool.


%prep
%setup -q

%build
make PYTHON=%{__python}

%install
rm -rf $RPM_BUILD_ROOT
make install PYTHON=%{__python} DESTDIR=$RPM_BUILD_ROOT MANDIR=%{_mandir}
# backwards compatibility symlinks, wheee
ln -sf fedup $RPM_BUILD_ROOT/%{_bindir}/fedup-cli
ln -sf fedup.8 $RPM_BUILD_ROOT/%{_mandir}/man8/fedup-cli.8
# updates dir
mkdir -p $RPM_BUILD_ROOT/etc/fedup/update.img.d

%post
for d in /var/tmp /var/lib; do
    if [ -d $d/fedora-upgrade -a ! -e $d/system-upgrade ]; then
        mv $d/fedora-upgrade $d/system-upgrade
    fi
done

%files
%doc README.asciidoc TODO.asciidoc COPYING
# systemd stuff
%{_unitdir}/system-upgrade.target
%{_unitdir}/upgrade-prep.service
%{_unitdir}/upgrade-switch-root.service
%{_unitdir}/upgrade-switch-root.target
%{_unitdir}/upgrade-plymouth-switch-root.service
%{_unitdir}/../system-generators/system-upgrade-generator
# upgrade prep program
%{_libexecdir}/upgrade-prep.sh
# python library
%{python_sitelib}/fedup*
# binaries
%{_bindir}/fedup
%{_bindir}/fedup-cli
# man pages
%{_mandir}/man*/*
# empty config dir
%dir /etc/fedup
# empty updates dir
%dir /etc/fedup/update.img.d

#TODO - finish and package gtk-based GUI
#files gtk
#{_bindir}/fedup-gtk
#{_datadir}/fedup/ui

%changelog
* Mon Dec 08 2014 Will Woods <wwoods@redhat.com> 0.9.1-1
- Fix traceback if --product/--add-install is misspelled/missing (#1167971)
- Make sure fedup --clean doesn't require --product (#1158766)
- Give clearer error messages about invalid '--network' values

* Mon Nov 03 2014 Will Woods <wwoods@redhat.com> 0.9.0-2
- Make systemd consider startup finished before starting upgrade (#1159292)

* Wed Oct 29 2014 Will Woods <wwoods@redhat.com> 0.9.0-1
- Add --product=PRODUCT flag for upgrades to F21
- Use host's config files in upgrade.img
- Fix logging during upgrade - upgrade logs will appear in system journal
- Fix keymap problems during upgrade (#1038413)
- Move cache to /var/cache (#1066679, CVE-2013-6494)

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.8.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Thu May 22 2014 Will Woods <wwoods@redhat.com> 0.8.1-1
- Warn the user when there is no kernel package in the upgrade
- Fix crash when resizing terminal window (#1044987)
- Fix crashes with bad arguments to --repo and --iso (#1045090, #1044083)
- Fix some crashes during transaction test (#1043981, #1047005)
- Fix upgrade hang if packagedir isn't on root partition (#1045168)
- Don't redownload everything if the user just upgraded from 0.7.x

* Fri Feb 28 2014 Adam Williamson <awilliam@redhat.com> 0.8.0-4
- backport a few more bugfixes from git master:
  + fix upgrade startup when packagedir isn't on root (#1045168)
  + Fix --network VERSION if /etc/debian_release exists (#1057817)
  + Warn the user if upgrade contains no kernels
- bump the required systemd version (also a 'backport' from git)

* Tue Dec 10 2013 Will Woods <wwoods@redhat.com> 0.8.0-3
- Fix crash with Ctrl-C on F18
- Fix --instrepo with --device/--iso

* Wed Dec 4 2013 Will Woods <wwoods@redhat.com> 0.8.0-0
- Check signatures on downloaded packages and images (#877623)
- Added --nogpgcheck, --instrepokey, --enableplugin, --disableplugin
- Improve error messages and warnings about transaction problems
- Improve disk space error messages (#949963)
- Clarify "instrepo not found" error (#980818)
- Start upgrade using systemd generator instead of boot args (#964303)
- Fix emergency shell on F17 upgrades (#958586)
- Don't start upgrade if media/packages are missing (#984415)
- Check for mismatched instrepo arch (#981180)
- Fix traceback with deltarpm (#1005895)
- Use the right kernel for Xen guests (#1023618)
- Fix mirror failover for instrepo (#1027573)
- Download multiple packages in parallel for extra speed
- Lots of other bugfixes

* Fri Mar 15 2013 Will Woods <wwoods@redhat.com> 0.7.3-0
- Write debuglog by default (/var/log/fedup.log)
- Add support for applying updates to upgrade.img
- Use proxy settings from yum.conf (#892994)
- Fix "NameError: global name 'po' is not defined" (#895576)
- Clearer error on already-upgraded systems (#895967)
- Fix upgrade hang with multiple encrypted partitions (#896010)
- Fix "OSError: [Errno 2]..." when `selinuxenabled` is not in PATH (#896721)
- Fix tracebacks on bad arguments to --iso (#896440, #895665)
- Fix traceback if grubby is missing (#896194)
- Require newer systemd to fix hang on not-updated systems (#910326)
- Fix hang starting upgrade on systems with /dev/md* (#895805)
- Better error messages if you're out of disk space (#896144)

* Thu Dec 06 2012 Will Woods <wwoods@redhat.com> 0.7.2-1
- Fix grubby traceback on EFI systems (#884696)
- Fix traceback if /var/tmp is a different filesystem from /var/lib (#883107)
- Disable SELinux during upgrade if system has SELinux disabled (#882549)
- Use new-kernel-pkg to set up bootloader (#872088, #879290, #881338)
- Remove boot option after upgrade (#873065)
- Fix running on minimal systems (#885990)
- Work around wrong/missing plymouth theme (#879295)
- Get instrepo automatically if available (#872899, #882141)
- Rename 'fedup-cli' to 'fedup'
- Rename '--repourl' to '--addrepo'
- Add mirrorlist support for --addrepo/--instrepo
- Clearer messages for most errors
- Fix --iso

* Mon Nov 19 2012 Will Woods <wwoods@redhat.com> 0.7.1-1
- Add --clean commandline argument
- Fix grubby traceback (#872088)
- Fetch kernel/initrd and set up bootloader
- Work around data-corrupting umount bug (#873459)
- Add support for upgrades from media (--device)

* Wed Oct 24 2012 Will Woods <wwoods@redhat.com> 0.7-1
- Initial packaging
