import kbuild
import ktest
import pytest

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

def test_nop(kdb):
	'''
	Simple nop test.

	Check that the basic console management is working OK.
	'''
	c = kdb.console.enter_kdb()
	c.exit_kdb()

def test_bp(kdb):
	'''
	Simple breakpoint test.

	Set a breakpoint, check it triggers and clear.
	'''
	c = kdb.console

	c = kdb.console.enter_kdb()
	try:
		# Set the breakpoint
		c.sendline('bp write_sysrq_trigger')
		# Instruction(i) BP #0 at 0x1071b728 (write_sysrq_trigger)
		#    is enabled   addr at 1071b728, hardtype=0 installed=0
		c.expect('Instruction.*BP.*write_sysrq_trigger')
		c.expect('is enabled')
		c.expect_prompt()
	finally:
		c.exit_kdb()

	# Check it triggers
	c.sysrq('h')
	c.enter_kdb(sysrq=False)
	try:
		c.sendline('bc 0')
		# Breakpoint 0 at 0x106a0bf8 cleared
		c.expect('Breakpoint.*cleared')
		c.expect_prompt()
	finally:
		c.exit_kdb(shell=False)
	# [ 6741.495608] sysrq: HELP : loglevel(0-9) reboot(b) crash(c)...
	c.expect('[sS]ys[rR]q.*HELP.*show-registers')
	c.expect_prompt()

	# Check it does not retrigger
	c.sysrq('h')
	c.expect('[sS]ys[rR]q.*HELP.*show-registers')
	c.expect_prompt()

def test_bta(kdb):
	'''
	Test `bta` and its slightly weird nested pager.

	Currently we do not check the quality of the backtrace because
	it is difficult to do so portably. We simply check that the
	nested pager is working.
	'''

	def handle_nested_pager(c):
		choices = ['cr.* to continue', 'more>', 'kdb>']

		choice = c.expect(choices)
		while choice == 1:
			c.send(' ')
			choice = c.expect(choices)

		assert choice == 0

	c = kdb.console.enter_kdb()

	try:
		# Run a bta command and wait for a btaprompt
		c.send('bta\r')
		handle_nested_pager(c)

		# Continue with <cr>
		c.send('\r')
		handle_nested_pager(c)

		# Continue with a <space>
		c.send(' ')
		handle_nested_pager(c)

		# Bust out. We do not use expect_prompt here because we
		# are also testing that we *don't* see a more> prompt.
		c.send('q')
		c.expect('kdb>')

	finally:
		c.exit_kdb()

def test_btc(kdb):
	'''
	Test `btc` (backtrace on all cpus)

        This is a simple survival test.
	'''
	c = kdb.console
	try:
		# Generate some load
		c.sendline('n=$((`nproc` + 1))')
		c.expect_prompt()
		c.sendline('for i in `seq $n`; do dd if=/dev/urandom of=/dev/null bs=65536 & done')
		c.expect_prompt()

		c.enter_kdb()

		# btc/start/stop
		for i in range(16):

			c.sendline('btc | grep traceback')

			choices = ['kdb>', 'traceback']
			choice = c.expect(choices)
			while 1 == choice:
				choice = c.expect(choices)
			assert choice == 0

			# Let userspace run for a moment
			c.exit_kdb()
			c.enter_kdb()


	finally:
		c.exit_kdb()

		# Terminate the load generating tasks
		c.expect_prompt(no_history=True)
		c.sendline('for i in `seq $n`; do kill %$i; done; sleep 1')
		c.expect_prompt()


def test_help(kdb):
	c = kdb.console.enter_kdb()
	try:
		c.send('help\r')
		c.expect('go.*Continue Execution')
		c.expect_prompt()
	finally:
		c.exit_kdb()

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

def md_regex(bytesperword, fields):
	# Hex number (at least 8 hexdigits long) followed up space
	address = '0x[0-9a-f]{8}[0-9a-f]* '

	# Hex number (exactly 2xbytesperword long) followed up a space
	datum = '[0-9a-f]{{{}}} '.format(2 * bytesperword)

	# datum (above) repeated fields times
	data = '({}){{{}}}'.format(datum, fields)

	# an extra space (which is then followed by the printable
	# ascii dump but we don't match that)
	tail = ' '

	return address + data + tail

def test_mdXc1(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('md1c1 kdb_printf\r')
		kdb.console.expect(md_regex(1, 1))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md2c1 kdb_printf\r')
		kdb.console.expect(md_regex(2, 1))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md3c1 kdb_printf\r')
		kdb.console.expect('Illegal value for BYTESPERWORD')
		kdb.console.expect_prompt()

		kdb.console.send('md4c1 kdb_printf\r')
		kdb.console.expect(md_regex(4, 1))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md5c1 kdb_printf\r')
		kdb.console.expect('Illegal value for BYTESPERWORD')
		kdb.console.expect_prompt()

		kdb.console.send('md6c1 kdb_printf\r')
		kdb.console.expect('Illegal value for BYTESPERWORD')
		kdb.console.expect_prompt()

		kdb.console.send('md7c1 kdb_printf\r')
		kdb.console.expect('Illegal value for BYTESPERWORD')
		kdb.console.expect_prompt()

		kdb.console.send('md8c1 kdb_printf\r')
		kdb.console.expect([md_regex(8, 1),
		                    'Illegal value for BYTESPERWORD'])
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md9c1 kdb_printf\r')
		kdb.console.expect('Illegal value for BYTESPERWORD')
		kdb.console.expect_prompt()

		kdb.console.send('md10c1 kdb_printf\r')
		kdb.console.expect('Unknown kdb command')
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_mdXc4(kdb):
	kdb.console.enter_kdb()
	try:
		address = '0x[0-9a-f]{8}[0-9a-f]* '
		def data(bytesperword, fields):
			return '([0-9a-f]'

		kdb.console.send('md1c4 kdb_printf\r')
		kdb.console.expect(md_regex(1, 4))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md2c4 kdb_printf\r')
		kdb.console.expect(md_regex(2, 4))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md4c4 kdb_printf\r')
		kdb.console.expect(md_regex(4, 4))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md8c4 kdb_printf\r')
		if 0 == kdb.console.expect([md_regex(8, 2),
				'Illegal value for BYTESPERWORD']):
			kdb.console.expect(md_regex(8, 2))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

	finally:
		kdb.console.exit_kdb()

def test_mdXc16(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.sendline('md1c16 kdb_printf')
		kdb.console.expect(md_regex(1, 16))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md2c16 kdb_printf\r')
		kdb.console.expect(md_regex(2, 8))
		kdb.console.expect(md_regex(2, 8))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md4c16 kdb_printf\r')
		for i in range(4):
			kdb.console.expect(md_regex(4, 4))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])

		kdb.console.send('md8c16 kdb_printf\r')
		if 0 == kdb.console.expect([md_regex(8, 2),
				'Illegal value for BYTESPERWORD']):
			for i in range(7):
				kdb.console.expect(md_regex(8, 2))
		assert 0 == kdb.console.expect(['kdb>', '0x[0-9a-f]'])
	finally:
		kdb.console.exit_kdb()

def test_mdr_variable(kdb):
	kdb.console.enter_kdb()
	try:
		kdb.console.send('mdr kgdb_single_step 4\r')
		assert 0 == kdb.console.expect(['00000000', 'Illegal numeric value'])
		kdb.console.expect_prompt()
	finally:
		kdb.console.exit_kdb()

def test_ps(kdb):
	commlist = [ 'sh[\r\n]', 'init[\r\n]', 'kthreadd[\r\n]', 'syslogd[\r\n]' ]

	c = kdb.console.enter_kdb()
	try:
		c.sendline('ps')
		c.expect('sleeping system daemon.*processes suppressed')
		assert 0 == c.expect(commlist)
		assert 1 == c.expect(commlist)
		# 2 is one of the threads we expect to be suppressed
		assert 3 == c.expect(commlist)
		c.expect_prompt()
	finally:
		c.exit_kdb()

def test_ps_A(kdb):
	commlist = [ 'more>', 'sh[\r\n]', 'init[\r\n]', 'kthreadd[\r\n]', 'syslogd[\r\n]' ]

	def expect(n):
		while True:
			r = c.expect(commlist)
			if r != 0:
				break
			c.send(' ')
		assert(r == n)

	c = kdb.console.enter_kdb()
	try:
		c.sendline('ps A')
		expect(1)
		expect(2)
		expect(3)
		expect(4)
		c.expect_prompt()
	finally:
		c.exit_kdb()

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm'), run = False,
		   reason = 'Oops when stepping after clearing breakpoint')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'mips'), run = False,
		   reason = 'Oops when stepping after clearing breakpoint')
def test_ss(kdb):
	'''
	Test the `ss` command.

	Currently this is merely a survival test; we do not check that
	the PC advances during the step. There's currently too much
	variability between the architectures to go deeper on this.
	'''
	c = kdb.console.enter_kdb()
	try:
		# Set breakpoint to some place we can step fairly far
		c.sendline('bp write_sysrq_trigger')
		c.expect_prompt()
		c.exit_kdb()

		# Trigger and then clear the breakpoint
		c.sysrq('h')
		c.enter_kdb(sysrq=False)
		c.sendline('bc 0')
		c.expect_prompt()

		# Single step a few times
		for i in range(32):
			c.send('ss\r')
			c.expect('Entering kdb')
			c.expect_prompt()
	finally:
		c.exit_kdb()

def test_sr(kdb):
	c = kdb.console.enter_kdb()
	try:
		c.send('sr h\r')
		c.expect('[sS]ys[rR]q.*HELP.*show-registers')
		c.expect_prompt()
	finally:
		c.exit_kdb()
