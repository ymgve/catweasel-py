import struct, sys, hashlib

def crc16(data, poly=0x8408):
    crc = 0xFFFF
    for c in data:
        for i in range(8):
            if (crc & 1) != ((c >> (7-i)) & 1):
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
                
    res = 0
    for i in range(16):
        res = (res << 1) | (crc & 1)
        crc >>= 1
        
    return res
    

class Bitstream(object):
    def __init__(self, trackdata):
        self.trackdata = trackdata
        self.index = 0
        self.pending = 0
        self.bitindex = 0
        
    def get_bit(self):
        if self.pending == 0:
            if self.index == len(self.trackdata):
                return None
                
            n = self.trackdata[self.index] & 0x7f
            self.index += 1

            if n < 0x23:
                self.pending = 2
            elif n <= 0x31:
                self.pending = 4
            else:
                self.pending = 8
            
            
        self.last = self.pending & 1
        self.pending >>= 1
        
        self.bitindex += 1
        
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
            
        s = a * 2 + b
        if s == 1:
            bit = 1
            
        elif s == 0:
            if last == 0:
                missing_syncs += 1
                
            bit = 0
            
        elif s == 2:
            if last == 1:
                missing_syncs += 1
                
            bit = 0
            
        else:
            raise Exception("DSDDS")
            
        res = (res << 1) | bit
        
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
        
def getbytes(bs, count):
    totalmiss = 0
    res = bytearray()
    for i in range(count):
        byte, missync = getbyte(bs)
        totalmiss += missync
        if byte == None:
            break
            
        res.append(byte)
        
    return res, totalmiss
        
class TrackDecoder(object):
    def __init__(self):
        self.debuglevel = 0
        
    def setdebug(self, level):
        self.debuglevel = level
        
    def debug(self, level, *msg):
        if level <= self.debuglevel:
            print("%2d %10d" % (level, self.bs.bitindex), *msg)
       
    def update_known_sectors(self, sectorno, data):
        if sectorno not in self.known_sectors:
            self.known_sectors[sectorno] = data
        else:
            if self.known_sectors[sectorno] != data:
                self.debug(0, "mismatch between sector data at sector %d" % sectorno)
                
    def parse_dos_gap(self):
        self.debug(3, "found DOS gap")
        
        if self.tracktype not in ("unknown", "dos"):
            self.debug(0, "found DOS gap on non-DOS disk")
            return
            
        byte, missync = getbyte(self.bs)
        
        if byte != 0xfc or missync != 0:
            self.debug(2, "found DOS gap header but bad gap data %r,  bit missyncs %d" % (byte, missync))
            return
            
        self.last_found = "dos_gapsync"
            
    def parse_dos_header(self):
        self.debug(3, "found DOS header")
        
        if self.tracktype not in ("unknown", "dos"):
            self.debug(0, "found DOS header on non-DOS disk")
            return
        
        byte, missync = getbyte(self.bs)
        
        if missync != 0:
            self.debug(2, "bit missyncs in DOS header type byte %d" % missync)
            return
            
        if byte not in (0xfb, 0xfe):
            self.debug(2, "wrong DOS header type byte %r" % byte)
            return
            
        self.debug(3, "found DOS header type %02x" % byte)
        
        if byte == 0xfe:
            res, missync = getbytes(self.bs, 6)
            if missync != 0:
                self.debug(2, "bit missyncs in DOS header data %d" % missync)
                return
            
            if len(res) != 6:
                self.debug(3, "incomplete DOS header, probably at end of track scan")
                return
                
            crc = crc16(b"\xa1\xa1\xa1\xfe" + res)
            if crc != 0:
                self.debug(2, "bad DOS header CRC")
                return
                
            # the header is now CRC verified and subsequent oddities should be level 0 or 1 warnings
            cyl, side, sectorno, sectorsizebits = struct.unpack("<BBBB", res[0:4])
            
            if side not in (0, 1):
                self.debug(0, "invalid side in DOS header: %d" % side)
                return
            
            trackno = cyl * 2 + side
            if trackno != self.target_track:
                self.debug(0, "wrong track number in DOS header, is %d but should be %d" % (trackno, self.target_track))
                return
                
            sectorno -= 1 # DOS sector numbers start at 1, we adjust to 0-indexed
            
            if sectorno < 0 or sectorno > 30: # upper limit dumb number picked at random
                self.debug(0, "wrong sector number in DOS header, %d" % sectorno)
                return
            
            new_sectorsize = 1 << (7+sectorsizebits)
            if self.sectorsize == None:
                self.sectorsize = new_sectorsize
                if new_sectorsize != 512:
                    self.debug(1, "non-standard sector size of %d" % new_sectorsize)
            else:
                if self.sectorsize != new_sectorsize:
                    self.debug(0, "sector size changes during track, ignoring this header")
                    return
            
            self.debug(3, "got valid sector header track %d sector %d" % (trackno, sectorno))
            
            if self.last_found == "dos_header_valid":
                self.debug(2, "encountered another sector header before data, prev header %d curr header %d" % (self.last_header, sectorno))
                
            self.header_bitindex = self.bs.bitindex
            
            self.last_found = "dos_header_valid"
            self.last_header = sectorno
            
            self.tracktype = "dos"
            
        elif byte == 0xfb:
            if self.last_found != "dos_header_valid":
                self.debug(2, "DOS data block with no header, probably at start of track scan")
                return
                
            sectorno = self.last_header
            self.debug(3, "found data block for sector header %d" % sectorno)
            
            distance_to_header = self.bs.bitindex - self.header_bitindex
            
            if distance_to_header > 1500:
                self.debug(0, "unusually many bits since header, ignoring data as it might belong to another header", distance_to_header, self.last_header)
                return
                
            res, missync = getbytes(self.bs, self.sectorsize + 2)
            if missync != 0:
                self.debug(2, "bit missyncs in DOS sector data %d" % missync)
                return
            
            if len(res) != self.sectorsize + 2:
                self.debug(3, "incomplete DOS data, probably at end of track scan")
                return
                
            crc = crc16(b"\xa1\xa1\xa1\xfb" + res)
            if crc != 0:
                self.debug(2, "bad DOS data CRC")
                return
                
            self.update_known_sectors(sectorno, res[0:-2])
            
            self.last_found = "dos_data"

            self.tracktype = "dos"

    def parse_amiga_sector(self):
        self.debug(3, "found Amiga header")
        
        if self.tracktype not in ("unknown", "amiga"):
            self.debug(2, "found Amiga header on non-Amiga disk, probably false positive")
            return
        
        words = []
        total_missing = 0
        csum = 0
        for i in range(12):
            rawres, missing_syncs = getamigaword(self.bs)
            if rawres == None:
                self.debug(3, "ran out of Amiga data, probably at end of track")
                return
                
            words.append(rawres)
            total_missing += missing_syncs
            csum ^= rawres
            
        if total_missing != 0:
            self.debug(2, "bit missyncs in Amiga header %d" % total_missing)
            return
            
        csum &= 0x55555555
        if csum != 0:
            self.debug(2, "bad Amiga header checksum")
            return
            
        header = ((words[0] & 0x55555555) << 1) | (words[1] & 0x55555555)
        
        format_id = header >> 24
        trackno = (header >> 16) & 0xff
        sectorno = (header >> 8) & 0xff
        until_end = header & 0xff
        
        if format_id != 0xff:
            self.debug(2, "wrong format ID in Amiga header %02x" % format_id)
            
        if trackno != self.target_track:
            self.debug(0, "wrong track number in Amiga header, is %d but should be %d" % (trackno, self.target_track))
            return
            
        if sectorno < 0 or sectorno > 30: # upper limit dumb number picked at random
            self.debug(0, "wrong sector number in Amiga header, %d" % sectorno)
            return
        
        self.debug(3, "got valid sector header track %d sector %d" % (trackno, sectorno))
        
        csum = 0
        words = []
        total_missing = 0
        csum = 0
        for i in range(258):
            rawres, missing_syncs = getamigaword(self.bs)
            if rawres == None:
                self.debug(3, "ran out of Amiga data, probably at end of track")
                return
                
            words.append(rawres)
            total_missing += missing_syncs
            csum ^= rawres
            
        if total_missing != 0:
            self.debug(2, "bit missyncs in Amiga data %d" % total_missing)
            return
            
        csum &= 0x55555555
        if csum != 0:
            self.debug(2, "bad Amiga data checksum")
            return
            
        data = b""
        for i in range(128):
            dataword = ((words[i+2] & 0x55555555) << 1) | (words[i+130] & 0x55555555)
            data += struct.pack(">I", dataword)
            
        self.update_known_sectors(sectorno, data)
        
        self.last_found = "amiga_data"
        
        self.tracktype = "amiga"
    
    def parse_mfm(self, trackdata, target_track):
        self.target_track = target_track
        self.sectorsize = None
        self.bits_since_header = 0
        self.tracktype = "unknown"
        self.last_found = "nothing"
        self.known_sectors = {}
        self.bs = Bitstream(trackdata)
        
        check = 0
        while True:
            bit = self.bs.get_bit()
            if bit == None:
                break
                
            check = (check << 1) | bit
            check &= 0xffffffffffff

            if check == 0x522452245224:
                self.parse_dos_gap()
                check = 0
                
            elif check & 0xffffffff0000 == 0x448944890000:
                if check == 0x448944894489:
                    self.parse_dos_header()
                else:
                    self.bs.push_back(16, check & 0xffff)
                    self.parse_amiga_sector()
                
                check = 0
                
        return self.tracktype, self.known_sectors
    
if __name__ == "__main__":
    known_sectors = {}
    f = open(sys.argv[1], "rb")

    magic = f.read(32)
    if magic != b"cwtool raw data 3".ljust(32, b"\x00"):
        raise Exception("bad magic")
        
    td = TrackDecoder()
    td.setdebug(1)
    
    while True:
        trackoffset = f.tell()
        trackheader = f.read(8)
        if len(trackheader) == 0:
            break
            
        trackmagic, trackno, clock, flags, tsize = struct.unpack("<BBBBI", trackheader)
        if trackmagic != 0xca:
            raise Exception()
        trackdata = f.read(tsize)
        
        open("temptracks\\trackdata%03d.bin" % trackno, "wb").write(trackdata)
        
        # if trackno != 25:
            # continue
            
        print("------------- track number %d file offset %x good sectors %d" % (trackno, trackoffset, len(known_sectors)))
        
        tracktype, new_sectors = td.parse_mfm(trackdata, trackno)
        for sectorno in new_sectors:
            ts = (trackno, sectorno)
            if ts not in known_sectors:
                known_sectors[ts] = new_sectors[sectorno]
            else:
                if known_sectors[ts] != new_sectors[sectorno]:
                    sector_a = known_sectors[ts]
                    sector_b = new_sectors[sectorno]
                    diff = ""
                    for i in range(512):
                        if sector_a[i] != sector_b[i]:
                            diff += "XX"
                        else:
                            diff += ".."
                            
                    print("\n\n\n!!!!!!SECTOR MISMATCH track %d sector %d" % (trackno, sectorno))
                    for i in range(0, 512, 32):
                        print(sector_a[i:i+32].hex(), sector_b[i:i+32].hex(), diff[i*2:i*2+64])
                    print("")
        

    of2 = open("_dummy.img", "wb")
    for trackno in range(160):
        for sectorno in range(10):
            ts = (trackno, sectorno)
            if ts in known_sectors:
                of2.write(known_sectors[ts])
            else:
                print("MISSING SECTOR", ts)
                of2.write(b"CWTOOLBADSECTOR!" * 32)

    of2.close()
