## upgrade-from-dev
* verify device
* set up mount unit

## `download`
* FedupCliKeyImport magic
* merge package download and image download
* sanity checks
  * need_product()
  * missing kernel
  * missing "important repos"
* test transaction
* problem summary

### Possibly in librepo:
* GPG keyring stuff to verify `.treeinfo.signed`
* retry kernel/initrd download if checksum fails

## `reboot`
1. copy kernel/initrd
2. update bootloader
3. create symlinks
  * including mount unit if needed
4. reboot

## `clean`
* various things to clean up

## functional test cases
* basic upgrade
* excludes in yum.conf
* luks + non-us keyboard

## more unit tests
* state
* beyond that we need a massive mock DNF object or something
  * yuck
