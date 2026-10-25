# tello-battery-decoder

A DSView protocol decoder for the single-wire bus between a DJI Tello and its battery.

The decoder is written for DSView, DreamSourceLab's fork of sigrok.
It uses DSView's decoder format and does not load in PulseView as is.

## Tested with

- DSView 1.3.2 on macOS (Intel)
- DSLogic U3Pro32

## Installation

Copy the `tello_battery` folder in `dsview/decoders/` into DSView's `decoders` folder, then restart DSView.

On macOS:

```sh
cp -R dsview/decoders/tello_battery /Applications/DSView.app/MacOS/decoders/
```

Copy it again after updating DSView, since an update replaces the application folder.

## Usage

1. Connect the battery data line to one logic analyzer channel, and the ground to the analyzer's ground.
2. Set the threshold to about 0.9 V, as the line is a 1.8 V signal.
3. Sample at 4 MHz or faster.
4. Add the decoder "Tello battery" and assign the channel to `DATA`.

Communication appears on this line within a few seconds after the Tello is powered on.

## Options

| Option | Default | Meaning |
|---|---|---|
| Low shorter than this is 1 (µs) | 2.5 | Bit slots with a shorter low are 1, others are 0. |
| Low at least this long is stop (µs) | 5.0 | A slot with a low at least this long ends the frame. |

## Annotation rows

| Row | Shows |
|---|---|
| Bits | Each slot: `S` (start), `1` / `0`, `A` (ACK) / `N` (NACK), `P` (stop). |
| Bytes | Each byte in hex. A first byte of `A0` / `A1` is marked as an address write / read. |
| Chars | Each data byte as a character: printable bytes quoted (`'D'`), others as a bare `.`. |
| Frames | The whole frame, e.g. `W A0: 03 10`, with the data bytes also as text when there is room. |
| Warnings | Frames that end mid-byte or without a stop, a stop without a start, and bytes after a NACK. |

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
