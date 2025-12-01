import kbuild
import ktest
import pytest
from types import MethodType

def test_kgdb_nolockdown():
	'''Verify we can connect to kgdb when there is no kdb and no lockdown.'''
	configs = [ 'KGDB_KDB=n', 'SECURITY=y', 'SECURITY_LOCKDOWN_LSM=y' ]
	kbuild.config(kgdb=True, extra_config=configs)
	kbuild.build()

	qemu = ktest.qemu(second_uart=True, gdb=True, append='kgdbwait')
	(console, gdb) = (qemu.console, qemu.debug)

	console.expect_boot(want_gdb_message=True)
	gdb.connect_to_target()

	gdb.send('where\r')
	gdb.expect('kgdb_register_io_module')
	gdb.expect_prompt()

	gdb.sendline('continue')
	console.expect_busybox()
	qemu.close()

def test_kgdb_integrity_lockdown():
	'''Verify we cannot access kgdb with no kdb and no lockdown.'''
	configs = [ 'KGDB_KDB=n', 'SECURITY=y', 'SECURITY_LOCKDOWN_LSM=y' ]
	kbuild.config(kgdb=True, extra_config=configs)
	kbuild.build()

	qemu = ktest.qemu(second_uart=True, gdb=True, append='kgdbwait lockdown=integrity')
	(console, gdb) = (qemu.console, qemu.debug)

	console.expect_boot(skip_late=True)
	console.expect('Lockdown.*use of kgdb/kdb')
	qemu.close()
