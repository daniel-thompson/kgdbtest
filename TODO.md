TODO
====

 * Improve test coverage
   - Exercise every kdb command at least once
   - kdb/ftrace
   - kgdb peek/poke
   - kgdb breakpoint in module
   - kgdb register modification (HARD)
   - parameterize kgdb smoke test to cover kernels built with and
     without kdb support.
   - kgdb entry on panic()
 * Split self tests into boot test and split out the different test
   cases
 * Modify boot message parsing to be table based (so if a message is
   missing we don't get stuck)
