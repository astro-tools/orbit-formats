# Command-line interface

Installing orbit-formats adds an `orbit-formats` console script for one-shot, file-to-file
conversion. It is a thin shell over the [Python API](api.md): the file it writes is identical
to the one the equivalent `convert` / `write` calls produce.

## `orbit-formats convert`

```bash
orbit-formats convert <input> <output> --to <format> [--from <format>] [--frame <frame>]
```

Read `<input>`, convert it to the `--to` format, and write it to `<output>`.

- **Auto-detection.** The input format is detected from the file's content signature and
  extension. Pass `--from <format>` to override the detection — needed for a format with no
  content signature (such as a GMAT report) when the file does not carry the expected
  extension.
- **Frame rotation.** Pass `--frame <frame>` (one of `TEME`, `EME2000` / `J2000`, `GCRF`,
  `ICRF`, `ITRF`) to rotate the Cartesian state into that reference frame; omitted, the source
  frame is kept. The rotation is lossless. A frame outside the set, or a mean-element input
  (a TLE or OMM) with no Cartesian state to rotate, fails with a non-zero exit.
- **Lossy warnings.** A conversion that cannot carry every field across — for example,
  writing an ephemeris that has no object id to OEM — prints a warning to **stderr** naming
  what was lost, and still writes the output.
- **Exit code.** Zero on success, including a lossy-but-completed conversion. Non-zero only
  on a hard failure: an unreadable input, an unknown or read-only target format, or a
  conversion the library does not support.

## Example

Re-serialise a GMAT report as a CCSDS OEM:

```bash
orbit-formats convert mission.report mission.oem --to ccsds-oem
```

If the report supplies no object id or central body, the synthesised OEM fills those fields
with placeholders and names them on stderr:

```text
orbit-formats: warning: the ephemeris does not supply the OEM-required OBJECT_ID; wrote the placeholder 'UNKNOWN'
orbit-formats: warning: the ephemeris does not supply the OEM-required CENTER_NAME; wrote the placeholder 'UNKNOWN'
```

Re-serialise an OEM into the J2000 frame:

```bash
orbit-formats convert orbit.oem j2000.oem --to ccsds-oem --frame J2000
```
