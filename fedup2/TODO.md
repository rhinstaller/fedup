## upgrade-from-dev
* verify device
* set up mount unit

## `download`
* FedupCliKeyImport magic
* sanity checks
  * need_product()
  * missing kernel
  * missing "important repos"
* test transaction
* problem summary

### Possibly in librepo:
* GPG keyring stuff to verify `.treeinfo.signed`
* retry kernel/initrd download if checksum fails

## functional test cases
* basic upgrade
* excludes in yum.conf
* luks + non-us keyboard

## more unit tests
* we need a massive mock DNF object or something
  * yuck
