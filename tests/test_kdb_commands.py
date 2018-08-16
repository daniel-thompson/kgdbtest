import kbuild
import ktest
import pytest
import random
import string
from types import MethodType

def enter_kdb(self):
	self.sysrq('g')
	self.expect('Entering kdb')
	self.expect_kdb()

	self.old_expect_prompt = self.expect_prompt
	self.expect_prompt = self.expect_kdb

def unique_tag(prefix=''):
	return prefix + ''.join(
		    [random.choice(string.ascii_uppercase) for i in range(8)])

def expect_kdb(self, sync=True):
	'''
	Manage the pager until we get a kdb prompt (or timeout)

	Set sync to False for test cases that rely upon a "clean" command
	history.
	'''
	if 1 == self.expect(['kdb>', 'more>']):
		self.send('q')
		self.expect('kdb>')

	if sync:
		tag = unique_tag('SYNC_KDB_')
		self.send(tag + '\r')
		self.expect('Unknown[^\r\n]*' + tag)
		self.expect('kdb>')

def exit_kdb(self):
	# Make sure we break out of the pager (q is enough to break out
	# but if we're *not* in the pager we need the \r to make the q
	# harmless
	self.send('q\r')
	self.expect('kdb>')

	# Now we have got the prompt back we can exit kdb
	self.send('go\r')
	self.expect_prompt = self.old_expect_prompt

	# We should now be running again but whether or not we get a
	# prompt depends on how the debugger was triggered. This
	# technique ensures we are fully up to date with the input.
	tag = unique_tag()
	self.send('echo "SYNC"_"SHELL"_"{}"\r'.format(tag))
	self.expect('SYNC_SHELL_{}'.format(tag))
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
	# Now we have booted our expectations should be met quickly
	console.timeout = 5

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
	try:
		kdb.console.send('help\r')
		kdb.console.expect('go.*Continue Execution')
		kdb.console.expect_prompt()
	finally:
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

def test_mdr_variable(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('mdr kgdb_single_step 4\r')
		assert 0 == kdb.console.expect(['00000000', 'Illegal numeric value'])
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_ss(kdb):
	'''
	Test the `ss` command.

	Currently this is merely a survival test; we do not check that
	the PC advances during the step. There's currently too much
	variability between the architectures to go deeper on this.
	'''
	kdb.console.enter_kdb()
	try:
		for i in range(32):
			kdb.console.send('ss\r')
			kdb.console.expect('Entering kdb')
			kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_sr(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('sr h\r')
		kdb.console.expect('SysRq : HELP.*show-registers')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()
