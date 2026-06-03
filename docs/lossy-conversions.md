# Lossy conversions

The contract at the heart of orbit-formats: a conversion either preserves information or
**says so**. Nothing is dropped silently.

## The guarantee

- **Same-format round-trips are lossless.** Reading a format and writing it back recovers
  the source — byte-for-byte when the read opted into `retain_source=True`, otherwise
  content-lossless (every field preserved, canonically reformatted). This works because the
  read keeps the full per-format fidelity model on
  [`source_native`](canonical-representation.md).
- **Cross-format conversions are lossless only where the formats overlap.** When a target
  cannot hold something the source carried, the conversion still proceeds — but emits a
  structured, catchable warning naming exactly what was lost.
- **A conversion that cannot be done without modelling is refused, not faked.** Turning a
  mean-element set into a state series is a propagation; orbit-formats raises rather than
  guessing (see below).

## The warning types

Every lossy warning descends from `LossyConversionWarning`, so one handler catches the whole
family. Each carries its dropped information as structured `DroppedField(name, reason)`
records — inspect *what* was lost as data, not by scraping a message string.

| Warning | Fires when |
|---------|-----------|
| `DroppedFieldWarning` | the target format structurally cannot represent a value the source had (e.g. covariance, or maneuvers, written to a format with no block for them) |
| `PrecisionLossWarning` | a value is narrowed to fit a target's field width or numeric precision |
| `ModelApproximationWarning` | a cross-category conversion introduces a model step, so the result is model-dependent rather than an exact restatement |
| `MissingFieldWarning` | the *source* omitted a value the canonical form has room for; the slot is filled with NaN, never fabricated |

## Catching them

A lossy conversion warns through the standard `warnings` machinery, so catch it the usual
way:

```python
import warnings
from orbit_formats import read, LossyConversionWarning

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    state = read("positions_only.report", format="gmat-report")

for record in caught:
    message = record.message
    if isinstance(message, LossyConversionWarning):
        print(message.fields)        # e.g. ('VX', 'VY', 'VZ')
        for dropped in message.dropped:
            print(dropped.name, "—", dropped.reason)
```

The `orbit-formats` CLI surfaces the same warnings on stderr while the conversion still
succeeds; see the [command-line interface](cli.md).

## Frame and time-transform scope

Cross-format conversion sometimes needs a real transform. orbit-formats draws the line
deliberately:

- **Time scales — supported.** Converting an instant between `UTC`, `TAI`, `TT`, `TDB`,
  `GPS`, and `UT1` is a lossless reinterpretation of the same instant; it runs internally
  through astropy (with leap seconds and bundled Earth-orientation data, no network access).
- **Frame rotation — supported.** Rotating a Cartesian state between `TEME`, `EME2000` /
  `J2000`, `GCRF`, `ICRF`, and `ITRF` is a rigid, lossless change of axes. Pass `frame=` to
  `convert` (or `--frame` to the CLI) to request it; omitted, the source frame is kept. The
  rotation runs through astropy (precession / nutation for the inertial frames, the IERS
  Earth-orientation tables and the Earth-rotation rate for the terrestrial ITRF), read
  hermetically with no network access — `GCRF` and `ICRF` are identical, so that pair is a
  no-op. It drops the byte-lossless `source_native` handle, since the rotated state no longer
  matches the original bytes; the canonical content stays exact. A frame outside the set, or a
  mean-element set with no Cartesian state to rotate, raises `FrameRotationUnsupportedError`
  rather than performing a naïve, un-modelled transform.

Frame rotation does **not** turn a mean-element set into an ephemeris: that step needs a
propagator, which is out of scope. The conversion is refused with
`UnsupportedConversionError` rather than approximated — the
[conversion-capability matrix](conversion-matrix.md) lists which paths are available.
