import kbuild
import ktest
import pytest
from types import MethodType

UP = '\x1b[A'
DOWN = '\x1b[B'
RIGHT = '\x1b[C'
LEFT = '\x1b[D'
HOME = '\x1b[1~'
DEL = '\x1b[3~'
END = '\x1b[4~'

INVALID2  = '\x1b]'
INVALID3  = '\x1b[]'
INVALID4  = '\x1b[1]'

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

def test_up(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zyx\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()

		kdb.console.send('wvu\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt()

		kdb.console.send(UP)
		kdb.console.expect('wvu')

		kdb.console.send(UP)
		kdb.console.expect('zyx')

		kdb.console.send('\r')
		kdb.console.expect('Unknown.*zyx')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_down(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zyx\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()

		kdb.console.send('wvu\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt()

		kdb.console.send(UP)
		kdb.console.expect('wvu')

		kdb.console.send(UP)
		kdb.console.expect('zyx')

		kdb.console.send(DOWN)
		kdb.console.expect('wvu')

		kdb.console.send('\r')
		kdb.console.expect('Unknown.*wvu')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_left(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zx' + LEFT + 'y\r')
		kdb.console.expect('Unknown.*zyx')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_right(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zx' + LEFT + 'y' + RIGHT + 'w\r')
		kdb.console.expect('Unknown.*zyxw')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_end(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('yx' + LEFT + LEFT + 'z' + END + 'w\r')
		kdb.console.expect('Unknown.*zyxw')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_home(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('yx' + HOME + 'z\r')
		kdb.console.expect('Unknown.*zyx')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_del(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zyEx' + LEFT + LEFT + DEL + '\r')
		kdb.console.expect('Unknown.*zyx')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()

def test_inval(kdb):
	'''An invalid escape sequence will return ESC to the caller and throw away
	all other characters.

	Since the kdb command line parser ignores unrecognised control characters
	(and special things like Escape) this test simply checks that the
	invalid escape sequences are ignored.'''
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zy' + INVALID2 + 'x\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()

		kdb.console.send('wv' + INVALID3 + 'u\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt()

		kdb.console.send('ts' + INVALID4 + 'r\r')
		kdb.console.expect('Unknown.*tsr')
	finally:
		kdb.console.expect_prompt()
		kdb.console.exit_kdb()
