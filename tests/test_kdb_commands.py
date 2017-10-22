import kbuild
import ktest
import pytest
from types import MethodType

def enter_kdb(self):
	self.sysrq('g')
	self.expect('Entering kdb')
	self.expect_kdb()

def expect_kdb(self):
	# TODO: Manage the pager until we get the kdb prompt
	self.expect('kdb>')

def exit_kdb(self):
	self.send('go\r')
	self.expect_prompt()
	

def bind_methods(c):
	# TODO: Can we use introspection to find methods to bind?
	c.enter_kdb = MethodType(enter_kdb, c)
	c.expect_kdb = MethodType(expect_kdb, c)
	c.exit_kdb = MethodType(exit_kdb, c)

@pytest.fixture(scope="module")
def kdb():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu()

	console = qemu.console
	bind_methods(console)
	console.expect_boot()
	console.expect_busybox()

	yield qemu

	qemu.close()

def test_nop(kdb):
	kdb.console.enter_kdb()
	kdb.console.exit_kdb()

def test_go(kdb):
	kdb.console.enter_kdb()
	kdb.console.send('go\r')
	kdb.console.expect_prompt()

def test_sr(kdb):
	kdb.console.enter_kdb()
	kdb.console.send('sr h\r')
	kdb.console.expect('SysRq : HELP.*show-registers')
	kdb.console.expect_kdb()
	kdb.console.exit_kdb()
