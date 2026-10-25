##
## This file is part of tello-battery-decoder.
##
## Copyright (C) 2026 hanyazou
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

## DJI Tello battery single-wire bus decoder for DSView (libsigrokdecode API 3).
## Written from the layout of DSView's 1:I²C decoder.

import sigrokdecode as srd

# Address bytes that are shown with their read/write direction.
ADDRESS_WRITE = 0xA0
ADDRESS_READ = 0xA1

# A slot whose high part lasts longer than this ends the frame without a
# stop slot. Inside a frame the high part is about 10 µs at most.
FRAME_TIMEOUT_US = 50.0

class Ann:
    START, STOP, ACK, NACK, BIT, ADDR_WRITE, ADDR_READ, DATA, CHAR, FRAME, WARN = range(11)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'tello_battery'
    name = 'Tello battery'
    longname = 'DJI Tello battery single-wire bus'
    desc = 'Single-wire, I²C-like bus between a Tello and its battery.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'data', 'type': 0, 'name': 'DATA', 'desc': 'Battery data line'},
    )
    options = (
        {'id': 'bit_threshold', 'desc': 'Low shorter than this is 1 (µs)',
            'default': 2.5},
        {'id': 'stop_threshold', 'desc': 'Low at least this long is stop (µs)',
            'default': 5.0},
    )
    annotations = (
        ('7', 'start', 'Start slot'),
        ('1', 'stop', 'Stop slot'),
        ('5', 'ack', 'ACK'),
        ('0', 'nack', 'NACK'),
        ('208', 'bit', 'Data bit'),
        ('111', 'address-write', 'Address write'),
        ('112', 'address-read', 'Address read'),
        ('110', 'data', 'Data byte'),
        ('107', 'char', 'Data byte as character'),
        ('109', 'frame', 'Frame'),
        ('1000', 'warnings', 'Human-readable warnings'),
    )
    annotation_rows = (
        ('bits', 'Bits', (Ann.START, Ann.STOP, Ann.ACK, Ann.NACK, Ann.BIT)),
        ('bytes', 'Bytes', (Ann.ADDR_WRITE, Ann.ADDR_READ, Ann.DATA)),
        ('chars', 'Chars', (Ann.CHAR,)),
        ('frames', 'Frames', (Ann.FRAME,)),
        ('warnings', 'Warnings', (Ann.WARN,)),
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.pending = None
        self.reset_frame()

    def reset_frame(self):
        self.in_frame = False
        self.frame_ss = None
        self.bitcount = 0
        self.databyte = 0
        self.byte_ss = None
        self.bytes = []
        self.nack_seen = False

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putx(self, ss, es, data):
        self.put(ss, es, self.out_ann, data)

    def us(self, samples):
        return samples * 1e6 / self.samplerate

    def warn(self, ss, es, text):
        self.putx(ss, es, [Ann.WARN, [text]])

    # A slot is known once its low part has ended (rise). It is annotated when
    # the next slot starts, so that it can span up to that falling edge.
    def handle_slot(self, ss, rise, es):
        width = self.us(rise - ss)

        if width >= self.options['stop_threshold']:
            self.handle_stop(ss, rise)
            return

        bit = 1 if width < self.options['bit_threshold'] else 0

        if not self.in_frame:
            self.in_frame = True
            self.frame_ss = ss
            self.putx(ss, es, [Ann.START, ['Start', 'S']])
            return

        if self.bitcount < 8:
            if self.bitcount == 0:
                self.byte_ss = ss
            self.databyte = (self.databyte << 1) | bit
            self.bitcount += 1
            self.putx(ss, es, [Ann.BIT, ['%d' % bit]])
            if self.bitcount == 8:
                self.put_byte(self.byte_ss, es)
                if self.nack_seen:
                    self.warn(self.byte_ss, es, 'Byte after NACK')
            return

        # Ninth slot: ACK / NACK.
        if bit:
            self.nack_seen = True
            self.putx(ss, es, [Ann.NACK, ['NACK', 'N']])
        else:
            self.putx(ss, es, [Ann.ACK, ['ACK', 'A']])
        self.bitcount = 0
        self.databyte = 0

    def put_byte(self, ss, es):
        d = self.databyte
        first = not self.bytes
        self.bytes.append(d)
        if first and d == ADDRESS_WRITE:
            self.putx(ss, es, [Ann.ADDR_WRITE,
                ['Address write: %02X' % d, '%02X W' % d, '%02X' % d]])
        elif first and d == ADDRESS_READ:
            self.putx(ss, es, [Ann.ADDR_READ,
                ['Address read: %02X' % d, '%02X R' % d, '%02X' % d]])
        else:
            self.putx(ss, es, [Ann.DATA, ['%02X' % d]])
            # Printable bytes are quoted, so a real '.' differs from the
            # bare '.' shown for the others.
            c = "'%s'" % chr(d) if 32 <= d < 127 else '.'
            self.putx(ss, es, [Ann.CHAR, [c]])

    def handle_stop(self, ss, es):
        self.putx(ss, es, [Ann.STOP, ['Stop', 'P']])
        if not self.in_frame:
            self.warn(ss, es, 'Stop without start')
            return
        if self.bitcount != 0:
            self.warn(ss, es, 'Frame ended mid-byte (%d bits)' % self.bitcount)
        self.put_frame(self.frame_ss, es)
        self.reset_frame()

    def put_frame(self, ss, es):
        if not self.bytes:
            return
        if self.bytes[0] == ADDRESS_WRITE:
            prefix, data = 'W %02X: ' % ADDRESS_WRITE, self.bytes[1:]
        elif self.bytes[0] == ADDRESS_READ:
            prefix, data = 'R %02X: ' % ADDRESS_READ, self.bytes[1:]
        else:
            prefix, data = '', self.bytes
        hexs = ' '.join('%02X' % b for b in data)
        text = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
        self.putx(ss, es, [Ann.FRAME, [
            '%s%s "%s"' % (prefix, hexs, text),
            '%s%s' % (prefix, hexs),
            '%s(%d bytes)' % (prefix, len(data)),
        ]])

    def flush_pending(self, next_fall):
        ss, rise = self.pending
        self.pending = None
        if next_fall is not None and self.us(next_fall - rise) <= FRAME_TIMEOUT_US:
            self.handle_slot(ss, rise, next_fall)
            return
        # No next slot close enough: end the slot at its rise, and the frame
        # with it if the slot was not a stop.
        self.handle_slot(ss, rise, rise)
        if self.in_frame:
            self.warn(self.frame_ss, rise, 'Frame without stop')
            self.put_frame(self.frame_ss, rise)
            self.reset_frame()

    def decode(self):
        if not self.samplerate:
            raise srd.SamplerateError('Cannot decode without samplerate.')
        while True:
            self.wait({0: 'f'})
            fall = self.samplenum
            if self.pending:
                self.flush_pending(fall)
            self.wait({0: 'r'})
            self.pending = (fall, self.samplenum)
            # A stop slot needs nothing after it; show it at once.
            if self.us(self.samplenum - fall) >= self.options['stop_threshold']:
                self.flush_pending(None)
