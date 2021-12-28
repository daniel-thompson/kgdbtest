import kbuild
import ktest
import pytest
import time

UP = '\x1b[A'
DOWN = '\x1b[B'
RIGHT = '\x1b[C'
LEFT = '\x1b[D'
HOME = '\x1b[1~'
DEL = '\x1b[3~'
END = '\x1b[4~'

INVALID3  = '\x1b[]'

INVALID4  = '\x1b[1]'

@pytest.fixture(scope="module")
def kdb():
	kbuild.config(kgdb=True)
	kbuild.build()

	qemu = ktest.qemu()

	console = qemu.console
	console.expect_boot()
	console.expect_busybox()
	# Now we have booted our expectations should be met quickly
	console.timeout = 5

	yield qemu

	qemu.close()

def test_up(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zyx\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt(sync=False)

		kdb.console.send('wvu\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt(sync=False)

		kdb.console.send(UP)
		kdb.console.expect('wvu')

		kdb.console.send(UP)
		kdb.console.expect('zyx')

		kdb.console.send('\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_down(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zyx\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt(sync=False)

		kdb.console.send('wvu\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt(sync=False)

		kdb.console.send(UP)
		kdb.console.expect('wvu')

		kdb.console.send(UP)
		kdb.console.expect('zyx')

		kdb.console.send(DOWN)
		kdb.console.expect('wvu')

		kdb.console.send('\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_left(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zx' + LEFT + 'y\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_right(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zx' + LEFT + 'y' + RIGHT + 'w\r')
		kdb.console.expect('Unknown.*zyxw')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_end(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('yx' + LEFT + LEFT + 'z' + END + 'w\r')
		kdb.console.expect('Unknown.*zyxw')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_home(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('yx' + HOME + 'z\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_del(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zyEx' + LEFT + LEFT + DEL + '\r')
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_inval(kdb):
	'''An invalid escape sequence will return ESC to the caller and throw away
	all other characters.

	Since the kdb command line parser ignores unrecognised control characters
	(and special things like Escape) this test simply checks that the
	invalid escape sequences are ignored.'''
	kdb.console.enter_kdb()
	try:
		kdb.console.send('zy\x1bxx\r')
                # For a two character sequence we pass if Escape x produces
                # nothing or 'x' (since either is sane)
		kdb.console.expect('Unknown.*zyx')
		kdb.console.expect_prompt()

		kdb.console.send('wv' + INVALID3 + 'u\r')
		kdb.console.expect('Unknown.*wvu')
		kdb.console.expect_prompt()

		kdb.console.send('ts' + INVALID4 + 'r\r')
		kdb.console.expect('Unknown.*tsr')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_pager_line(kdb):
	'''Test line-by-line pager handling

	This test assumes the output of the help command does not
	change much between releases (although we deliberately don't
	use strings on the very last and very first lines to give us
	a little tolerance of change.'''
	kdb.console.enter_kdb()
	try:
		kdb.console.send('help\r')
		kdb.console.expect('more>')
		
		for i in range(4):
			kdb.console.send('\r')
			# The pager flushes the input buffer after processing
			# a character... we must leave time for it to be
			# processed
			time.sleep(0.1)

		kdb.console.expect('Switch to new cpu')
		kdb.console.expect('Enter kgdb mode')
		# Ensure we didn't produce too much output
		assert 0 == kdb.console.expect(['more>', 'Single Step'])

		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_pager_page(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('help\r')
		kdb.console.expect('more>')
		
		kdb.console.send(' ')
		kdb.console.expect('Enter kgdb mode')
		# test_pager_search relies on 'Single Step' to detect
		# failure. If this expectation requires modifying then
		# test_pager_search may need updating too.
		kdb.console.expect('Single Step')
		kdb.console.expect('more>')

		kdb.console.send(' ')
		kdb.console.expect('Same as dumpall')
		kdb.console.expect('kdb>')
	finally:
		kdb.console.exit_kdb()

@pytest.mark.xfail(condition = kbuild.get_version() < (5, 10),
		   reason = 'pager search eats line after match')
def test_pager_search(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('help\r')
		kdb.console.expect('md.*Display Memory Contents')
		kdb.console.expect('env.*Show environment variables')
		kdb.console.expect('more>')

		kdb.console.send('/')
		kdb.console.expect('search>')
		kdb.console.send('Common\r')
		assert 0 == kdb.console.expect(['Common kdb debugging',
						'Single Step'])
		kdb.console.expect('First line debugging')
		kdb.console.expect('Same as dumpall')
	finally:
		kdb.console.exit_kdb()

def test_grep(kdb):
	'''Test "piping" through grep'''
	kdb.console.enter_kdb()
	try:
		kdb.console.send('help | grep summary\r')
		kdb.console.expect('Summarize the system')
		kdb.console.expect('kdb>')
	finally:
		kdb.console.exit_kdb()

def test_tab_complete(kdb):
	'''Test tab completion as with hone in on a symbol.'''
	c = kdb.console.enter_kdb()
	try:
		symbols = [ 'kdb_reboot ', 'kdb_rd ',
                            'kdb_register ', 'kdb_rm ' ]
		c.send('kdb_r\t\t')
		while symbols:
			i = c.expect(symbols)
			del symbols[i]
		c.expect_prompt(sync=False)

		c.send('\bu\t')
		c.expect('register')

		c.send('\t')
		c.expect('kdb_unregister')
		c.expect_prompt(sync=False)
		c.expect('kdb_unregister')

		c.send(' kdb_reb\t')
		c.expect('kdb_reboot')

		c.send('\r')
		c.expect_prompt()
	finally:
		c.exit_kdb()

def test_tab_search(kdb):
	'''Test tab completion when there are too many symbols to display'''
	c = kdb.console.enter_kdb()
	try:
		c.send('\t\t')
		c.expect('symbols are found.*only first.*symbols will be printed.')
		c.expect_prompt(sync=False)

		c.send('p\t\t')
		c.expect('symbols are found.*only first.*symbols will be printed.')
		c.expect_prompt(sync=False)

		c.send(' q r s t\t\t')
		c.expect('symbols are found.*only first.*symbols will be printed.')
		c.expect_prompt(sync=False)

		c.send('\r')
		c.expect_prompt()
	finally:
		c.exit_kdb()
