import kbuild
import ktest
import pytest
from types import MethodType

def enter_kdb(self):
	self.sysrq('g')
	self.expect('Entering kdb')
	self.expect_kdb()

	self.old_expect_prompt = self.expect_prompt
	self.expect_prompt = self.expect_kdb

def expect_kdb(self):
	'''
	Manage the pager until we get a kdb prompt (or timeout)
	'''
	while True:
		if 0 == self.expect(['kdb>', 'more>']):
			return
		self.send(' ')

def exit_kdb(self):
	self.send('go\r')
	self.expect_prompt = self.old_expect_prompt

	# We should now be running again but whether or not we get a
	# prompt depends on how the debugger was triggered. This
	# technique ensures we are fully up to date with the input.
	self.send('echo "FORCE"_"IO"_"SYNC"\r')
	self.expect('FORCE_IO_SYNC')
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
	'''
	Simple nop test.

	Check that the basic console management is working OK.
	'''
	kdb.console.enter_kdb()
	kdb.console.exit_kdb()

def test_help(kdb):
	kdb.console.enter_kdb()
	kdb.console.send('help\r')
	kdb.console.expect('go.*Continue Execution')
	kdb.console.expect_prompt()
	kdb.console.exit_kdb()

def test_go(kdb):
	'''
	Test the `go` command.

	This test does not use enter_kdb() because it ends by calling
	go directly (meaning the enter/exit would be mis-matched and
	this would expect_prompt() broken for the next test.
	'''
	kdb.console.sysrq('g')
	kdb.console.expect('Entering kdb')
	kdb.console.expect_kdb()
	kdb.console.send('go\r')
	kdb.console.expect_prompt()

def test_sr(kdb):
	kdb.console.enter_kdb()
	kdb.console.send('sr h\r')
	kdb.console.expect('SysRq : HELP.*show-registers')
	kdb.console.expect_kdb()
	kdb.console.exit_kdb()
