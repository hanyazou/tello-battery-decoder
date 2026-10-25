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

'''
Single-wire bus between a DJI Tello and its battery.

The bus idles high. Every bit is a slot that starts with a falling edge,
and the length of the low part tells the bit: a short low is 1, a long low
is 0. A frame is a start slot, bytes of 8 bits (MSB first) each followed by
an ACK (0) or NACK (1) slot, and a stop slot with an even longer low.
The framing follows I²C: 0xA0 / 0xA1 address the battery for write / read.
'''

from .pd import Decoder
