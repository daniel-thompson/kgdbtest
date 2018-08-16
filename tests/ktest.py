import kbuild
import os
import pexpect
import sys
import time
from types import MethodType

def expect_boot(self, bootloader=()):
	for msg in bootloader:
		self.expect(msg)
	self.expect('Linux version.*$')
	self.expect('Calibrating delay loop')
	self.expect('NET: Registered protocol family 2')
	self.expect('io scheduler [^ ]* registered .default.')
        # We need a wildcard here because some newer kernels now
        # "Free unused kernel image memory".
	self.expect('Freeing unused kernel.*memory')

def expect_busybox(self):
	self.expect('Starting logging')
	self.expect('OK')
	self.expect('Welcome to Buildroot')
	self.expect(['debian-[^ ]* login:', 'buildroot login:'])
	self.sendline('root')

	self.expect_prompt()

	self.sendline('mount -t debugfs none /sys/kernel/debug')
	self.expect_prompt()

def expect_prompt(self):
	self.expect('# ')

def sysrq(self, ch):
	self.send('echo {} > /proc/sysrq-trigger\r'.format(ch))

def gdb_connect_to_target(self):
	self.expect_prompt()
	self.send('target extended-remote | socat - UNIX:ttyS1.sock\r')
	self.expect('Remote debugging using')
	self.expect_prompt()

def gdb_expect_prompt(self):
	self.expect('[(]gdb[)] ')
	self.sendline('printf "force_gdb_sync"')
	# No newline means the output here will be unique
	self.expect('force_gdb_sync[^\r\n]*[(]gdb[)] ')

def bind_methods(c, d):
	# TODO: Can we use introspection to find methods to bind?
	c.expect_boot = MethodType(expect_boot, c)
	c.expect_busybox = MethodType(expect_busybox, c)
	c.expect_prompt = MethodType(expect_prompt, c)
	c.sysrq = MethodType(sysrq, c)

	if d:
		d.connect_to_target = MethodType(gdb_connect_to_target, d)
		d.expect_prompt = MethodType(gdb_expect_prompt, d)


class ConsoleWrapper(object):
	def __init__(self, console, debug=None):
		bind_methods(console, debug)
		self.console = console
		self.debug = debug
	
	def close(self):
		if self.debug:
			self.debug.close()
		self.console.close()

def qemu(kdb=True, append=None, gdb=False, interactive=False, second_uart=False):
	'''Create a qemu instance and provide pexpect channels to control it'''

	arch = kbuild.get_arch()

	if arch == 'arm' or arch == 'arm64':
		tty = 'ttyAMA'
	else:
		tty = 'ttyS'

	cmdline = ''
	cmdline += ' console={}0,115200'.format(tty)
	if kdb:
		if not second_uart:
			cmdline += ' kgdboc={}0'.format(tty)
		else:
			cmdline += ' kgdboc={}1'.format(tty)
	if gdb:
		cmdline += ' nokaslr'
	if append:
		cmdline += ' ' + append

	# Heavily broken out so we can easily slot in support for other
	# architectures.
	if arch == 'arm':
		cmd = 'qemu-system-arm'
		cmd += ' -accel tcg,thread=multi '
		cmd += ' -M vexpress-a15 -cpu cortex-a15'
		cmd += ' -kernel arch/arm/boot/zImage'
		cmd += ' -dtb arch/arm/boot/dts/vexpress-v2p-ca15-tc1.dtb'
	elif arch == 'arm64':
		cmd = 'qemu-system-aarch64'
		cmd += ' -accel tcg,thread=multi '
		cmd += ' -M virt,gic_version=3 -cpu cortex-a57'
		cmd += ' -kernel arch/arm64/boot/Image'
	elif arch == 'x86':
		cmd = 'qemu-system-x86_64'
		cmd += ' -enable-kvm'
		cmd += ' -kernel arch/x86/boot/bzImage'
	else:
		assert False

	cmd += ' -m 1G'
	cmd += ' -smp 2'
	cmd += ' -nographic -monitor none'
	cmd += ' -chardev stdio,id=mon,mux=on,signal=off -serial chardev:mon'
	if second_uart:
		cmd += ' -chardev socket,id=ttyS1,path=ttyS1.sock,server,nowait'
		cmd += ' -serial chardev:ttyS1'
	cmd += ' -initrd rootfs.cpio.gz'
	cmd += ' -append "{}"'.format(cmdline)

	if gdb:
		gdbcmd = '{}gdb'.format(kbuild.get_cross_compile())
		gdbcmd += ' vmlinux'
		gdbcmd += ' -ex "set pagination 0"'

	if interactive:
		if gdb:
			gdbcmd += ' -ex "target extended-remote |' + \
					'socat - UNIX:ttyS1.sock"'
			print ('\n>>> (cd {}; {})\n'.format(
					kbuild.get_kdir(), gdbcmd))

		print('+| ' + cmd)
		os.system(cmd)
		return None

	print('+| ' + cmd)
	qemu = pexpect.spawn(cmd, encoding='utf-8', logfile=sys.stdout)

	if gdb:
		print('+| ' + gdbcmd)
		gdb = pexpect.spawn(gdbcmd,
				encoding='utf-8', logfile=sys.stdout)
	else:
		gdb = None

	return ConsoleWrapper(qemu, gdb)
