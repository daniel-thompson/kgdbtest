import kbuild

def test_buildable():
	'''Simple buildability test.

	This test is not generally useful (since every other test also
	compiles the kernel) but is very helpful for bisection since
	it helps us identify uncompilable kernels.
	'''
	kbuild.config(kgdb=True)
	kbuild.build()
