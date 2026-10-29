# MS Plus delay-memory investigation

Read-only static investigation of the verified firmware-1.10 stock backup,
2026-10-28. This is research, not permission to write arbitrary DSP memory.
Stomphacks remains pinned at 26470497e7de90497fba7528386b8029b84f8939;
its remote HEAD was checked and is the same revision.

The six musical experiments were briefly reinstalled for requested manual
listening, then removed when the user prioritized completing all 22 first.
`build/msplus/final-audit-after-manual-cancel/VERIFIED.json` confirms the
original effect list, stock-only temporary patch, all 100 saved patches and
absence of experimental files after that cleanup.

## Static evidence

Extract stock DATA sections with zoom-zt2's ZD2 parser, then inspect ELF symbols
with pyelftools and disassemble with TI's dis6x. Original containers and extracted
code stay private under ignored `build/msplus/`. REA was consulted, but its
Ghidra provider is unconfigured and Hopper is unavailable; the existing TI
vendor disassembler supports this CPU without changing tool registration.

In stock DELAY_C, `Fx_DLY_Delay`:

- Address 0x668 loads `instance[3]` into A27.
- 0x85c decrements the write offset by four bytes; 0x868 and 0x880 wrap a
  negative offset by adding descriptor word 2.
- 0x874 loads descriptor word 0, adds the write offset at 0x888, and stores
  one float at that address at 0x88c.
- 0x898/0x89c load words 1/2; 0x8ac/0x8ae compare read addresses to word 1,
  and 0x8b4/0x8c4 wrap addresses by subtracting word 2 before float reads.

These operations support `{base, exclusive_end, byte_count}` for the three
words, rather than three float pointers. The code does not establish allocation
size, ownership across slots, clearing, or stability across chain edits.

STDELAY independently loads `instance[3]` at 0x8a6 and descriptor word 0 at
0x8b8 and 0x8e4. Its internal channel offsets use 0x56220 bytes. Neither its
init function nor DELAY_C's init requests a buffer allocation: they copy
coefficients, clear small state and initialize parameter handlers. Host/loader
allocation still needs investigation.

## Read-only diagnostic

`src/msplus/meminfo` uses the existing cleanroom scaffold, initialized state
guard and bounded quiet output. Its default Arm=0 never accesses `instance[3]`.
Only an explicit temporary Arm=1 edit after initialization reads the descriptor's
three words. It never dereferences their values, reads/writes the arena, or
calls an unknown host service. Two quiet triangle frequencies encode two
bytes per half-second, after a 200/300 Hz preamble. Peak is at most 0.0002.
The native test confirms disarmed behavior even with an invalid descriptor
pointer, unchanged descriptor contents, the encoded frequencies and the ceiling.

A live diagnostic must use the guarded install/readback/unsaved audition/restore/
uninstall sequence, retaining all prior safety checks. Record actual grants
before designing a bounded allocator; insufficient grants must fail closed.

## Hardware result and first buffered port

On firmware 1.10 in the one-slot scratch patch, telemetry decoded
`{0xc0378000, 0xc0424440, 0x000ac440}`: **705,600 bytes**, exactly
exclusive_end minus base. The diagnostic was restored/uninstalled after capture;
raw recordings, exact uploaded artifact, source hashes and `memory.json` are in
`build/msplus/memory-research/hil-01/hil/`.

`mp_arena_state` accepts only aligned, internally consistent descriptors with
at most this observed grant and sufficient capacity for the port. It does not
change descriptors or ask the host for memory. Each new instance invalidates
only its own legacy state header, then the original bounded initialization runs.
No absolute DSP address is embedded in any musical kernel. Ownership across
multiple effect slots is not yet hardware-qualified; initial tests are standalone.

GenLoss is the first buffered proof of concept. Native canary tests cover
undersized/inconsistent/oversized descriptor rejection before writes and an
independent fixed-delay/filter reference. Its guarded hardware campaign passed
dry/half/wet and maximum-wow sweeps on both returns, with no clipping, non-finite
output or xruns. All saved patches remained unchanged, stock scratch settings
were restored, and GenLoss was removed. Captures: `build/msplus/genloss-hil-01/`.
The read-only diagnostic and this bounded implementation advance the prior
memory blocker; the remaining effects still require individual build and DSP tests.
