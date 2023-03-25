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
        self.last = 0
        
        
    def get_bit(self):
        if self.pending == 0:
            if self.index == len(self.trackdata):
                return None
                
            n = self.splitlut[self.trackdata[self.index]]
            self.index += 1
    
            self.pending = 1 << n
                
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
            
        s = a * 2 + b
        if s == 1:
            bit = 1
            
        elif s == 0:
            if last == 0:
                missing_syncs += 1
                
            bit = 0
            
        elif s == 2:
            # never happens
            # if last == 1:
                # missing_syncs += 1
                
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
    totalmiss = 0
    res = bytearray()
    for i in range(count):
        byte, missync = getbyte(bs)
        if missync != 0:
            return res, missync
            
        if byte == None:
            return res, 0
            
        res.append(byte)
        
    return res, 0
        
class TrackDecoder(object):
    def __init__(self):
        self.debuglevel = 0
        self.notif = set()
        
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
                if sectorno != 65:
                    self.debug(0, "wrong sector number in DOS header, %d" % sectorno)
                else:
                    if "sector65" not in self.notif:
                        self.debug(0, "wrong sector number in DOS header, %d" % sectorno)
                        self.notif.add("sector65")
                
                return
            
            new_sectorsize = 1 << (7+sectorsizebits)
            if self.sectorsize == None:
                self.sectorsize = new_sectorsize
                if new_sectorsize != 512:
                    self.debug(1, "non-standard sector size of %d for sector %d" % (new_sectorsize, sectorno))
            else:
                if self.sectorsize != new_sectorsize:
                    #self.debug(0, "sector size changes from %d to %d during track, ignoring header for sector %d" % (self.sectorsize, new_sectorsize, sectorno))
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
                #self.debug(0, "unusually many bits since header, ignoring data as it might belong to another header", distance_to_header, self.last_header)
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
    
    def parse_mfm(self, trackdata, target_track, splits=(0x22, 0x2f)):
        self.target_track = target_track
        self.sectorsize = None
        self.bits_since_header = 0
        self.tracktype = "unknown"
        self.last_found = "nothing"
        self.known_sectors = {}
        self.bs = Bitstream(trackdata, splits)
        
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

def add_new_sector(known_sectors, trackno, sectorno, data):
    if sectorno not in known_sectors[trackno]:
        known_sectors[trackno][sectorno] = data
        #print("added sector", trackno, sectorno)
    else:
        if known_sectors[trackno][sectorno] != data:
            sector_a = known_sectors[trackno][sectorno]
            sector_b = data
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
            exit()
            
        #else:
            #print("dupe sector", trackno, sectorno)

    
def add_new_sectors(known_sectors, trackno, new_sectors):
    added = 0
    for sectorno in new_sectors:
        if sectorno not in known_sectors[trackno]:
            known_sectors[trackno][sectorno] = new_sectors[sectorno]
            added += 1
        else:
            if known_sectors[trackno][sectorno] != new_sectors[sectorno]:
                sector_a = known_sectors[trackno][sectorno]
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
                
    return added
    
def split_track(trackdata, splitlut):
    bs = Bitstream(trackdata, splitlut)
    prevsplit = 0
    
    splits = []
    check = 0
    while True:
        bit = bs.get_bit()
        if bit == None:
            break
            
        check = (check << 1) | bit
        check &= 0xffffffffffff

        if check == 0x448944894489:
            splits.append(trackdata[prevsplit:bs.index])
            prevsplit = bs.index
            check = 0
    
    splits.append(trackdata[prevsplit:])
    
    return splits
    
def split_track2(trackdata, splitlut):
    trackdata2 = bytes(splitlut[x] for x in trackdata)
    
    syncmark = bytes((3, 2, 3, 2, 1, 3, 2, 3, 2, 1, 3, 2, 3, 2))
    
    positions = [-14]
    
    pos = -1
    while True:
        try:
            pos = trackdata2.index(syncmark, pos + 1)
        except ValueError:
            break
            
        positions.append(pos)
        
    splits = []
    for i in range(len(positions)-1):
        splits.append(trackdata[positions[i]+14:positions[i+1]])
        
    if len(positions) >= 1:
        splits.append(trackdata[positions[-1]+14:])
    
    return splits
    
def split_track3(trackdata):
    prev = 0
    goal = (0x37, 0x28, 0x37, 0x28, 0x1a, 0x37, 0x28, 0x37, 0x28, 0x1a, 0x37, 0x28, 0x37, 0x28)
    for i in range(len(trackdata)-14):
        cand = trackdata[i:i+14]
        
        res = sum((cand[j] - goal[j])**2 for j in range(14))
        
        if res < 1000:
            dist = i - prev
            print("maybe", res, dist)
            prev = i
        
        

def make_lut(lo, hi):
    splitlut = [0] * 256
    for i in range(0, lo):
        splitlut[i] = 1
        splitlut[i+0x80] = 1
        
    for i in range(lo, hi):
        splitlut[i] = 2
        splitlut[i+0x80] = 2
        
    for i in range(hi, 0x80):
        splitlut[i] = 3
        splitlut[i+0x80] = 3
        
    return splitlut

def parse_header(bs):
    res, missync = getbytes(bs, 6)
    if missync != 0:
        #self.debug(2, "bit missyncs in DOS header data %d" % missync)
        return None
    
    if len(res) != 6:
        #self.debug(3, "incomplete DOS header, probably at end of track scan")
        return None
        
    crc = crc16(b"\xa1\xa1\xa1\xfe" + res)
    if crc != 0:
        #self.debug(2, "bad DOS header CRC")
        return None
        
    cyl, side, sectorno, sectorsizebits = struct.unpack("<BBBB", res[0:4])
    
    return (cyl, side, sectorno, sectorsizebits)
    
def parse_data(bs):
    res, missync = getbytes(bs, 512 + 2)
    if missync != 0:
        #self.debug(2, "bit missyncs in DOS sector data %d" % missync)
        print("missyncs", missync)
        return None
    
    if len(res) != 512 + 2:
        #self.debug(3, "incomplete DOS data, probably at end of track scan")
        print("Incomplete")
        return None
        
    crc = crc16(b"\xa1\xa1\xa1\xfb" + res)
    if crc != 0:
        #self.debug(2, "bad DOS data CRC")
        print("Bad CRC")
        return None
        
    return res[0:512]
    

luts = []
dist = 6
for i in range(-dist, dist+1):
    for j in range(-dist, dist+1):
        lo = 0x22 + i
        hi = 0x2f + j
            
        lut = make_lut(lo, hi)
    
        luts.append((abs(i) + abs(j), lo, hi, lut))
        
luts.sort()

baselut = luts[0][3]

def decode_parts(parts, lut):
    parsed = []
    for part in parts:
        bs = Bitstream(part, lut)
        byte, missyncs = getbyte(bs)
        if missyncs == 0:
            if byte == 0xfe:
                if len(part) >= 500:
                    parsed.append("oversized")
                    
                    print("oversized header", trackno, len(part))
                    split_track3(part)
                    # best = 2
                    # bestsplit = None
                    # for lo, hi, lut2 in luts:
                        # splits2 = split_track2(part, lut2)
                        # if len(splits2) >= 2:
                            # print("split %d with %02x %02x" % (len(splits2), lo, hi))
                            # res = decode_parts(splits2, lut2)
                            # print("qqqqqqqqq", res)
                    
                else:
                    header = parse_header(bs)
                    if header != None:
                        parsed.append(("header", header))
                    else:
                        parsed.append("badheader")
                        
            elif byte == 0xfb:
                data = parse_data(bs)
                if data != None:
                    parsed.append("data")
                else:
                    parsed.append("baddata")
                
            else:
                parsed.append("badbyte")
                
        else:
            parsed.append("badsync")
            
    return parsed
            
def get_best_bytes(part, quick=False):
    best = None
    for dist, lo, hi, lut in luts:
        bs = Bitstream(part, lut)
        res, missyncs = getbytes(bs, 7)
        
        if missyncs == 0 and len(res) == 7:
            if res[0] == 0xfe:
                if crc16(b"\xa1\xa1\xa1" + res) == 0:
                    if dist != 0:
                        print("had to go extra distance to get valid header", dist)
                        
                    return ("header", struct.unpack("<BBBB", res[1:5]))
                
            elif res[0] == 0xfb:
                res2, missyncs = getbytes(bs, 508)
                if missyncs == 0 and crc16(b"\xa1\xa1\xa1" + res + res2) == 0:
                    if dist != 0:
                        print("had to go extra distance to get valid data", dist)
                        
                    return ("data", res[1:] + res2[:506])
        
        if quick:
            break
            
    return ("bad", None)
    
if __name__ == "__main__":
    known_sectors = {}
    known_data = set()
    orphans = set()
    
    if len(sys.argv) == 3:
        target_track = int(sys.argv[2])
    else:
        target_track = None
        
    for passno in range(2):
        f = open(sys.argv[1], "rb")

        magic = f.read(32)
        if magic != b"cwtool raw data 3".ljust(32, b"\x00"):
            raise Exception("bad magic")
            
        target_sectors = 18
        
        print("numluts", len(luts))
        
        while True:
            trackoffset = f.tell()
            trackheader = f.read(8)
            if len(trackheader) == 0:
                break
                
            trackmagic, trackno, clock, flags, tsize = struct.unpack("<BBBBI", trackheader)
            
            # comment data
            if trackmagic == 0:
                f.read(tsize)
                continue
                
            if trackmagic != 0xca:
                raise Exception()
                
            trackdata = f.read(tsize)
            
            if trackno not in known_sectors:
                known_sectors[trackno] = {}

            if len(known_sectors[trackno]) == target_sectors:
                continue

            if trackno >= 160:
                continue
                
            if target_track != None and target_track != trackno:
                continue
                
            totalsectors = sum([len(known_sectors[x]) for x in known_sectors])
            
            print("------------- track number %d file offset %x  total good sectors %d" % (trackno, trackoffset, totalsectors))
                
            #split_track3(trackdata)
            
            parts = split_track2(trackdata, baselut)
            
            currsector = None
            for part in parts[1:]:
                if currsector != None and currsector in known_sectors[trackno] and len(part) >= 2000:
                    currsector = None
                    
                    continue
                    
                #print("%10d %s" % (len(part), part.hex()))
                
                # if currsector == 17 and trackno == 127:
                    # print(part.hex())
                    
                res = get_best_bytes(part, passno==0)
                if res[0] == "header":
                    ok = True
                    cyl, side, sectorno, sectorsizebits = res[1]
                    
                    #print("header", cyl, side, sectorno, sectorsizebits)
                    
                    if side not in (0, 1):
                        ok = False
                        
                    if side + cyl * 2 != trackno:
                        ok = False
                        
                    if sectorsizebits != 2:
                        ok = False

                    if sectorno >= 30:
                        ok = False
                        
                    if len(part) > 500:
                        ok = False
                        
                    if ok:
                        currsector = sectorno - 1
                    else:
                        currsector = None
                        
                elif res[0] == "data":
                    #print("data")
                    data = bytes(res[1])
                    fingerprint = hashlib.sha256(data).hexdigest()[0:8]
                    if currsector != None:
                        added = add_new_sector(known_sectors, trackno, currsector, data)
                        known_data.add(data)
                        if data in orphans:
                            print("connected orphan", fingerprint, "with track and sector", trackno, currsector)
                            orphans.remove(data)
                    else:
                        if data not in known_data:
                            print("orphaned data with hash", fingerprint)
                            orphans.add(data)
                        
                    currsector = None
                    
                else:
                    #print("other")
                    currsector = None
                    
                # bs = Bitstream(part, lut)
                # byte, missyncs = getbyte(bs)
                # if missyncs == 0:
                    # if byte == 0xfe:
                        # if len(part) >= 500:
                            # parsed.append("oversized")
                            
                            # print("oversized header", trackno, len(part))
                            # split_track3(part)
                            # best = 2
                            # bestsplit = None
                            # for lo, hi, lut2 in luts:
                                # splits2 = split_track2(part, lut2)
                                # if len(splits2) >= 2:
                                    # print("split %d with %02x %02x" % (len(splits2), lo, hi))
                                    # res = decode_parts(splits2, lut2)
                                    # print("qqqqqqqqq", res)
                            
                        # else:
                            # header = parse_header(bs)
                            # if header != None:
                                # parsed.append(("header", header))
                            # else:
                                # parsed.append("badheader")
                                
                    # elif byte == 0xfb:
                        # data = parse_data(bs)
                        # if data != None:
                            # parsed.append("data")
                        # else:
                            # parsed.append("baddata")
                        
                    # else:
                        # parsed.append("badbyte")
                        
                # else:
                    # parsed.append("badsync")
                    
                        
                        
            #print(parsed)
                
            # best = len(splits)
            # for lo, hi, lut in luts:
                # splits = split_track2(trackdata, lut)
                # if len(splits) > best:
                    # best = len(splits)
                    # print("new best split %d with %02x %02x" % (best, lo, hi))
                    
            # start = time.time()
            # splits = split_track(trackdata, splitlut)
            # print(trackno, len(splits), time.time() - start)
            
            # start = time.time()
            # splits2 = split_track2(trackdata, splitlut)
            # print(trackno, len(splits2), time.time() - start)
            
            # print([len(x) for x in splits2])
            # print(len(splits[0]), splits[0][0:100])
            # print(len(splits2[0]), splits2[0][0:100])
            
            #print("")
            # if trackno >= 160:
                # continue
                
            # if trackno not in known_sectors:
                # known_sectors[trackno] = {}
                
            # if trackno != 7:
                # continue
                
            # if len(known_sectors[trackno]) == target_sectors:
                # continue
                
            # totalsectors = sum([len(known_sectors[x]) for x in known_sectors])
            
            # print("------------- track number %d file offset %x  total good sectors %d" % (trackno, trackoffset, totalsectors))
            
            # tracktype, new_sectors1 = td.parse_mfm(trackdata, trackno)
            
            # stats = [0] * 0x80
            # for n in trackdata:
                # stats[n & 0x7f] += 1
                
            # loindex = 0
            # lobest = 10000000000000
            # for i in range(0x1b, 0x2b):
                # if stats[i] <= lobest:
                    # lobest = stats[i]
                    # loindex = i
                    
            # hiindex = 0
            # hibest = 10000000000000
            # for i in range(0x2b, 0x38):
                # if stats[i] <= hibest:
                    # hibest = stats[i]
                    # hiindex = i
            
            # tracktype, new_sectors2 = td.parse_mfm(trackdata, trackno, (loindex, hiindex))
            
            # for sectorno in new_sectors2:
                # if sectorno not in new_sectors1:
                    # print("Got extra sector %d with new splits %02x %02x" % (sectorno, loindex, hiindex))

            # for sectorno in new_sectors1:
                # if sectorno not in new_sectors2:
                    # print("MISSING SECTOR WITH NEW SPLITS %d splits %02x %02x" % (sectorno, loindex, hiindex))
                    
            #print("sectors", len(new_sectors1), len(new_sectors2))
            # added = add_new_sectors(known_sectors, trackno, new_sectors1)
            # added += add_new_sectors(known_sectors, trackno, new_sectors2)
            # if added != 0:
                # print("got %d new good sectors, total for track %d" % (added, len(known_sectors[trackno])))
                    

        # f.close()
        
    if target_track == None:
        writecount = 0
        of2 = open(sys.argv[1] + ".img", "wb")
        for trackno in range(160):
            missings = []
            for sectorno in range(18):
                if trackno in known_sectors and sectorno in known_sectors[trackno]:
                    of2.write(known_sectors[trackno][sectorno])
                    writecount += 1
                else:
                    of2.write(b"CWTOOLBADSECTOR!" * 32)
                    missings.append(sectorno)

            if len(missings) != 0:
                print("missing from track", trackno, ":", missings)
                
        of2.close()    
        
        print("sectors written", writecount)
    
    print("remaining orphans", orphans)