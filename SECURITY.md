# Security boundaries

SONATA source is interpreted as a bounded AST. It does not evaluate host-language
code or expose arbitrary filesystem/network operations. Source, AST, array,
recursion, instruction, trace, MIDI, and audio limits are checked at their relevant
boundaries. Module loading is a CLI operation confined to the selected entry's
resolved directory; imported files may contain functions and imports only.

The debugger binds to loopback and rejects unexpected Host/Origin headers. Run
it locally; do not expose it to an untrusted network or treat it as a production
multi-user service. Limits reduce accidental resource exhaustion but do not
provide process-level isolation from a malicious local user.

The Python tracing API is for trusted callables and runs with normal Python
permissions. Optional live MIDI accesses only explicitly selected ports. Its
playback accepts channel messages and rejects SysEx/system messages; capture
counts and ignores messages outside that supported subset. Do not use SONATA
as a boundary protecting an instrument from arbitrary other software.

Please report a reproducible security issue with the affected version, input,
expected boundary, actual result, and minimal steps. Do not post credentials,
private source, or sensitive recordings. Validate reports using owned/local
fixtures and describe demonstrated impact without inferring remote exposure.
