import kbuild
import ktest
import pytest
import re

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
	'''Test `btc` (backtrace on all cpus)

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

def test_btp(kdb):
	'''Test `btp` (backtrace specific PID)'''

	# Stack traceback for pid 1
	# 0xffffa19381198000        1        0  0    1   S  0xffffa193811994c0  init
	# Call Trace:
	#  <TASK>
	#  __schedule+0x2f9/0xb30
	#  schedule+0x49/0xb0
	#  schedule_hrtimeout_range_clock+0x12e/0x140
	#  ? lock_release+0x13c/0x2e0
	#  ? _raw_spin_unlock_irq+0x1f/0x40
	#  do_sigtimedwait+0x172/0x250
	# [...]
	output = kdb.console.run_command('btp 1')

	assert output.startswith('Stack traceback for pid 1')
	assert 'init\n' in output

	# Normally init will sleep inside do_sigtimedwait() or do_nanosleep()
	# but if init is on the CPU (e.g. *init appears in the process list)
	# then we are doing something else and will see kdb calls instead!
	expect_sigtimedwait = '*init' not in output
	if expect_sigtimedwait:
		assert 'schedule' in output
		assert ('do_sigtimedwait' in output or
		        'sys_rt_sigtimedwait' in output or
			'do_nanosleep' in output)
	else:
		assert 'kgdb_cpu_enter' in output

def test_help(kdb):
	'''Test the `help` command.

	Runs the command and checks a couple of basic command are present
	and correct. Note that `go` and `kgdb` (and often `dumpcpu` too)
	appear on different pages (but paging is transparently handled by
	run_command().
	'''
	output = kdb.console.run_command('help')
	assert re.search(r'\ngo *\[<vaddr>\] *Continue Execution\n', output)
	assert re.search(r'\nkgdb *Enter kgdb mode\n', output)
	assert re.search(r'\ndumpcpu *Same as dumpall', output)

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

def test_pid(kdb):
	c = kdb.console.enter_kdb()
	try:
		# KDB current process is init(pid=1)
		output = c.run_command('pid 1')
		assert 'current process is init'

		# Stack traceback for pid 1
		# 0xffffa19381198000        1        0  0    1   S  0xffffa193811994c0  init
		# Call Trace:
		#  <TASK>
		#  __schedule+0x2f9/0xb30
		#  schedule+0x49/0xb0
		#  schedule_hrtimeout_range_clock+0x12e/0x140
		#  ? lock_release+0x13c/0x2e0
		#  ? _raw_spin_unlock_irq+0x1f/0x40
		#  do_sigtimedwait+0x172/0x250
		# [...]
		output = c.run_command('bt')

		assert output.strip().startswith('Stack traceback for pid 1')
		assert 'init\n' in output

		# Normally init will sleep inside do_sigtimedwait() but if
		# init is on the CPU (e.g. *init appears in the process list)
		# then we are doing something else and will see kdb calls
		# instead!
		expect_sigtimedwait = '*init' not in output
		if expect_sigtimedwait:
			assert ('do_sigtimedwait' in output or
			        'sys_rt_sigtimedwait' in output)
		else:
			assert 'kgdb_cpu_enter' in output

	finally:
		c.exit_kdb()

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

def test_rd(kdb):
	'''Test the `rd` command.

	Grab the contents of the register set and (optionally) perform a
	per-arch sanity test. The actual call to the rd command happens
	inside the library code in ktest.py [get_regs_kdb()]. However it is
	worth pulling out into a seperate test because other tests won't fail
	in such an easily understood way if there were a regression in the
	output of `rd`.
	'''
	c = kdb.console.enter_kdb()
	try:
		regs = c.get_regs()

		if kbuild.get_arch() == 'arm64':
			assert 'x0' in regs
			assert regs['sp'].startswith('ffff')
			assert regs['pc'].startswith('ffff')
		elif kbuild.get_arch == 'riscv':
			assert regs['sp'].startswith('ffff')
			assert regs['pc'].startswith('ffff')
		elif kbuild.get_arch() == 'x86':
			assert 'ax' in regs
			assert regs['sp'].startswith('ffff')
			assert regs['ip'].startswith('ffff')
	finally:
		c.exit_kdb()

def test_summary(kdb):
	'''Test the `summary` command.

	The summary output usually looks like this::

	    sysname    Linux
	    release    5.17.0
	    version    #150 SMP PREEMPT Thu Mar 31 09:34:03 BST 2022
	    machine    aarch64
	    nodename   (none)
	    domainname (none)
	    date       1970-01-01 00:00:01 tz_minuteswest 0
	    uptime     00:00
	    load avg   0.00 0.00 0.00

	    MemTotal:         976356 kB
	    MemFree:          949648 kB
	    Buffers:               0 kB
	'''
	summary = kdb.console.run_command('summary')
	assert summary.startswith('sysname    Linux')
	assert 'MemTotal' in summary

@pytest.mark.xfail(condition = (kbuild.get_arch() == 'arm'),
		   reason = 'Stepping triggers breakpoint')
@pytest.mark.xfail(condition = (kbuild.get_arch() == 'mips'),
		   reason = 'Stepping triggers breakpoint')
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

		oldpc = ''

		# Single step a few times
		for i in range(16):
			c.send('ss\r')
			c.expect('Entering kdb')
			choice = c.expect(['due to SS', 'due to Breakpoint'])
			assert(choice == 0)
			c.expect(' @ 0x[0-9a-f]*[^0-9a-f]')
			newpc = c.after
			c.expect_prompt()

			assert(newpc != oldpc)
			oldpc = newpc
	finally:
		# Clear the breakpoint (doesn't matter if we never set it...
		# we'll still get a prompt and be recovered for the next test.
		c.sendline('bc 0')
		c.expect_prompt()

		c.exit_kdb()

def test_sr(kdb):
	c = kdb.console.enter_kdb()
	try:
		c.send('sr h\r')
		c.expect('[sS]ys[rR]q.*HELP.*show-registers')
		c.expect_prompt()
	finally:
		c.exit_kdb()
