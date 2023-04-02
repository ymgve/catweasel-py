import struct, sys, hashlib, io, random, time, array

crclookup = []
for i in range(256):
    crc = 0
    poly = 0x1021
    for j in range(8):
        if (i & (1 << j)) != 0:
            crc ^= poly
            
        if poly & 0x8000:
            poly = (poly << 1) ^ 0x11021
        else:
            poly <<= 1
            
    crclookup.append(crc)


def crc16(data):
    crc = 0xffff
    for c in data:
        crc = ((crc & 0xff) << 8) ^ crclookup[(crc >> 8) ^ c]

    return crc

class Bitstream(object):
    def __init__(self, trackdata, splitlut):
        self.trackdata = trackdata
        self.index = 0
        self.pending = 0
        self.splitlut = splitlut
        self.last = None
        
        
    def get_bit(self):
        if self.pending == 0:
            if self.index == len(self.trackdata):
                return None
                
            n = self.splitlut[self.trackdata[self.index]]
            self.index += 1
    
            self.pending = n
                
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last
    
    def push_back(self, nbits, value):
        for i in range(nbits):
            self.pending <<= 1
            self.pending |= value & 1
            value >>= 1
            
        self.bitindex -= nbits
        
        
def getbyte(bs):
    res = 0
    missing_syncs = 0
    for i in range(8):
        last = bs.last
        a = bs.get_bit()
        b = bs.get_bit()
        if a == None or b == None:
            return None, missing_syncs
            
        if b == 0 and last == a:
            missing_syncs += 1
            
        res = (res << 1) | b
        
    return res, missing_syncs
           
def getamigaword(bs):
    rawres = 0
    missing_syncs = 0
    for i in range(16):
        last = bs.last
        a = bs.get_bit()
        b = bs.get_bit()
        if a == None or b == None:
            return None, missing_syncs
            
        s = a * 2 + b
        rawres = (rawres << 2) | s
        
        if s == 1:
            pass
            
        elif s == 0:
            if last == 0:
                missing_syncs += 1
            
        elif s == 2:
            if last == 1:
                missing_syncs += 1
            
        else:
            raise Exception("DSDDS")
            
    return rawres, missing_syncs
        
# def getbytes(bs, count):
    # totalmiss = 0
    # res = bytearray()
    # for i in range(count):
        # byte, missync = getbyte(bs)
        # totalmiss += missync
        # if byte == None:
            # break
            
        # res.append(byte)
        
    # return res, totalmiss

def getbytes(bs, count):
    res = bytearray()
    for i in range(count):
        byte, missync = getbyte(bs)
        if missync != 0:
            return res, missync
            
        if byte == None:
            return res, 0
            
        res.append(byte)
        
    return res, 0
        
def make_lut(lo, hi):
    splitlut = [0] * 256
    for i in range(0, lo):
        splitlut[i] = 2
        splitlut[i+0x80] = 2
        
    for i in range(lo, hi):
        splitlut[i] = 4
        splitlut[i+0x80] = 4
        
    for i in range(hi, 0x80):
        splitlut[i] = 8
        splitlut[i+0x80] = 8
        
    return splitlut
    
data = bytes.fromhex("1f191c1a1c191d251c1a1d181e1a1a1a1c1a1c171e1a1b161d1b1c1b1f2320251d1b1c1b2836392f24261e181a1f242430372b271c1c27282b291e19282a29271c1b282a2b261d1b282a29271c1d272929281c1b2a2929261e1a292a29261b1e28292826")

for c in data:
    ldiff = abs(c - 0x1a)
    mdiff = abs(c - 0x28)
    hdiff = abs(c - 0x37)
    
    if ldiff < mdiff and ldiff < hdiff:
        best = c - 0x1a
        
    if mdiff < ldiff and mdiff < hdiff:
        best = c - 0x28
        
    if hdiff < ldiff and hdiff < mdiff:
        best = c - 0x37
        
    print("%02x %3d" % (c, best))
    
bs = Bitstream(data, make_lut(0x22, 0x2f))

while True:
    b, e = getbyte(bs)
    if b == None:
        break
    print("%02x %d" % (b, e))
    
print(hex(crc16(b"\xa1\xa1\xa1\xfe\x00\x03\x02\xa9\xf2")))

bs = Bitstream(data, make_lut(0x22, 0x2f))

s = ""
while True:
    b = bs.get_bit()
    if b == None:
        break
    s += str(b)
    
print(s)
# print(hex(crc16(b"\xa1\xa1\xa1\xfe\x00\x03\x02\xe0\x1b")))

# a9 f2
#  1 0 1 0 1 0 0 1 1 1 1 1 0 0 1 0
# 01 0001 0001 001 001 01010101001 001 00
# e0 1b
#  1 1 1 0 0 0 0 0 0 0 0 1 1 0 1 1
# 01 0101 001  01  01  01010101001  01 000101
    
#

# 0101010101010100 fe
# 1010101010101010 00
# 1010101010101010 00
# 1010101010100101 03
# 0010101010100100 02
# 0100010001001001 a9
# 0101010100100100 f2
# 0100010010010101
# 0010010010010101
# 0010010010010101
# 00100100100101010010010010010101001001001001010100100100100101010010010010010101001001001001
#