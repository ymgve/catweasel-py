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
    if trackno not in known_sectors:
        print("Track number outside known tracks!", trackno)
        return
        
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
    
def find_dos_syncs_fast(trackdata, splitlut):
    trackdata2 = bytes(splitlut[x] for x in trackdata)
    
    syncmark = bytes((8, 4, 8, 4, 2, 8, 4, 8, 4, 2, 8, 4, 8, 4))
    
    positions = []
    
    pos = -1
    while True:
        try:
            pos = trackdata2.index(syncmark, pos + 1)
        except ValueError:
            break
            
        positions.append(pos)
        
    return set(positions)
    
def find_dos_sync_deep(trackdata):
    positions = []
    goal = (0x37, 0x28, 0x37, 0x28, 0x1a, 0x37, 0x28, 0x37, 0x28, 0x1a, 0x37, 0x28, 0x37, 0x28)
    for i in range(len(trackdata)-14):
        cand = trackdata[i:i+14]
        
        score = sum((cand[j] - goal[j])**2 for j in range(14))
        
        if score < 1000:
            positions.append((i, score))
            
    return positions
        
        

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
dist = 5
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


def get_data(bs, sectorsize, want_sectordata=True):
    res, missyncs = getbytes(bs, 7)
    if missyncs == 0 and len(res) == 7:
        if res[0] == 0xfe:
            if crc16(b"\xa1\xa1\xa1" + res) == 0:
                return res[:-2]
                
        elif res[0] == 0xfb:
            if want_sectordata:
                res2, missyncs = getbytes(bs, sectorsize - 4)
                if missyncs == 0 and len(res2) == sectorsize - 4 and crc16(b"\xa1\xa1\xa1" + res + res2) == 0:
                    data = res + res2[:-2]
                    return data
                    
            else:
                return res
                
    return None
    
def make_custom_track_lut(blockdata):
    stats = [0] * 0x80
    for n in blockdata:
        stats[n & 0x7f] += 1
        
    loindex = 0
    lobest = 10000000000000
    for i in range(0x1b, 0x2b):
        if stats[i] < lobest:
            lobest = stats[i]
            loindex = i
            
    hiindex = 0
    hibest = 10000000000000
    for i in range(0x2b, 0x38):
        if stats[i] < hibest:
            hibest = stats[i]
            hiindex = i
            
    return make_lut(loindex, hiindex)


class Trackscan(object):
    def __init__(self, trackoffset, trackno, clock, flags, trackdata):
        self.trackoffset = trackoffset
        self.trackno = trackno
        self.clock = clock
        self.flags = flags
        self.trackdata = trackdata
        self.claimed_trackno = None
        self.claimed_sectorsize = None
        self.positions = set()
        self.found_data = {}
        

if __name__ == "__main__":
    known_sectors = {}
    # known_data = set()
    # orphans = set()

    target_sectors = 9
    
    
    # if len(sys.argv) == 3:
        # target_track = int(sys.argv[2])
    # else:
        # target_track = None
        
    f = open(sys.argv[1], "rb")

    magic = f.read(32)
    if magic != b"cwtool raw data 3".ljust(32, b"\x00"):
        raise Exception("bad magic")
        
    scans = []
    
    maxtracks = 168
    
    while True:
        trackoffset = f.tell()
        trackheader = f.read(8)
        if len(trackheader) == 0:
            break
            
        trackmagic, trackno, clock, flags, tsize = struct.unpack("<BBBBI", trackheader)
        trackdata = f.read(tsize)
        
        # comment data
        if trackmagic == 0:
            continue
            
        if trackmagic != 0xca:
            raise Exception()

        # skipping tracks 160+ for now
        # TODO handle when sectors on tracks 160+ collide with sectors on tracks 159-
        if trackno >= maxtracks:
            continue
            
        # if trackno % 2 == 1:
            # continue
            
        # if trackno != 0:
            # continue

        scan = Trackscan(trackoffset, trackno, clock, flags, trackdata)
        
        scans.append(scan)
        
        known_sectors[trackno] = {}
        
    # fast scan
    for scan in scans:
        # assume all track numbers are valid and ignore tracks based on that
        # if len(known_sectors[scan.trackno]) == target_sectors:
            # continue

        totalsectors = sum([len(known_sectors[x]) for x in known_sectors])
        
        print("--------- scan level 1: track number %d file offset %x  total good sectors %d" % (scan.trackno, scan.trackoffset, totalsectors))

        scan.positions = find_dos_syncs_fast(scan.trackdata, baselut)
        # print("number of syncs found", len(scan.positions))
        # if len(scan.positions) < 30 and scan.trackno == 0:
            # testlut = make_custom_track_lut(scan.trackdata)
            # print(scan.positions)
            # pos2 = find_dos_sync_deep(scan.trackdata)
            # print(len(pos2))
            # prevpos = 0
            # for i in range(1, len(pos2)-1):
                # startpos = pos2[i][0]+14
                # endpos = pos2[i+1][0]
                # segment = scan.trackdata[startpos:endpos]
                
                # print(pos2[i], len(segment))
                # bs = Bitstream(segment, testlut)
                # data = get_data(bs, 512, False)
                # if data != None:
                    # print(data.hex())
                # else:
                    # print("raw", segment[0:100].hex())
            # exit()
        
        scan.found_data = {}
        
        currsector = None
        
        poslist = sorted(scan.positions)
        
        for pos in range(len(poslist)-1):
            startpos = poslist[pos]+14
            endpos = poslist[pos+1]
            segment = scan.trackdata[startpos:endpos]
            bs = Bitstream(segment, baselut)
            
            added = False
            sector_set = False
            
            want_sectordata = True
            if currsector == None or (scan.claimed_trackno in known_sectors and currsector in known_sectors[scan.claimed_trackno]):
                want_sectordata = False
            
            data = get_data(bs, scan.claimed_sectorsize, want_sectordata)
            if data != None:
                if data[0] == 0xfe:
                    cyl, side, sectorno, sectorsizebits = struct.unpack("<BBBB", data[1:5])
                    header_trackno = side + cyl * 2
                    sectorsize = 1 << (7 + sectorsizebits)
                    ok = True
            
                    if side not in (0, 1):
                        print("side not 0 or 1")
                        ok = False
                        
                    if scan.claimed_trackno != None:
                        if header_trackno != scan.claimed_trackno:
                            print("track number different from other track number on track", header_trackno, scan.claimed_trackno)
                            ok = False
                        
                    if scan.claimed_sectorsize != None:
                        if sectorsize != scan.claimed_sectorsize:
                            print("sector size changed", sectorsize, scan.claimed_sectorsize)
                            ok = False

                    if sectorno >= 30:
                        if sectorno != 66:
                            print("sector number too large", sectorno)
                        ok = False
                        
                    if ok:
                        if len(segment) < 500:
                            currsector = sectorno - 1
                            sector_set = True

                            scan.found_data[startpos] = ("validheader", header_trackno, sectorno - 1)
                        else:
                            scan.found_data[startpos] = ("header", header_trackno, sectorno - 1)
                        
                            
                        scan.claimed_trackno = header_trackno
                        scan.claimed_sectorsize = sectorsize
                        
                        added = True
                    
                elif data[0] == 0xfb:
                    if want_sectordata:
                        add_new_sector(known_sectors, scan.claimed_trackno, currsector, data[1:])
                        if currsector + 1 > target_sectors:
                            target_sectors = currsector + 1
                            print("increasing targetsectors", target_sectors)
                        
                        scan.found_data[startpos] = ("data", len(segment))
                        added = True
                        
                    else:
                        if currsector != None:
                            scan.found_data[startpos] = ("assumed_known_data", len(segment))
                            added = True
                        else:
                            scan.found_data[startpos] = ("assumed_data", len(segment))
                            added = True
            
            if not added:
                scan.found_data[startpos] = ("unknown", len(segment))
                    
            if not sector_set:
                currsector = None

    for scan in scans:
        # assume all track numbers are valid and ignore tracks based on that
        # if len(known_sectors[scan.trackno]) == target_sectors:
            # continue

        totalsectors = sum([len(known_sectors[x]) for x in known_sectors])
        
        print("--------- scan level 2: track number %d file offset %x  total good sectors %d" % (scan.trackno, scan.trackoffset, totalsectors))

        customlut = make_custom_track_lut(scan.trackdata)
        newpositions = find_dos_syncs_fast(scan.trackdata, customlut)
        
        added = newpositions - scan.positions
        if len(added) > 0:
            print("new", added)
            
        scan.positions = scan.positions | newpositions
        
        currsector = None
        
        poslist = sorted(scan.positions)
        
        for pos in range(len(poslist)-1):
            startpos = poslist[pos]+14
            endpos = poslist[pos+1]

            sector_set = False
            
            skip = False
            if startpos in scan.found_data:
                prevtype = scan.found_data[startpos][0]
                if prevtype == "validheader":
                    currsector = scan.found_data[startpos][2]
                    sector_set = True
                    skip = True
                    
                elif prevtype in ("data", "assumed_known_data"):
                    skip = True
                    
                else:
                    print("Replacing data of type", prevtype)
            if skip:
                continue
                
            added = False
            
            segment = scan.trackdata[startpos:endpos]
            bs = Bitstream(segment, customlut)
            
            want_sectordata = True
            if currsector == None or (scan.claimed_trackno in known_sectors and currsector in known_sectors[scan.claimed_trackno]):
                want_sectordata = False
            
            data = get_data(bs, scan.claimed_sectorsize, want_sectordata)
            if data != None:
                if data[0] == 0xfe:
                    cyl, side, sectorno, sectorsizebits = struct.unpack("<BBBB", data[1:5])
                    header_trackno = side + cyl * 2
                    sectorsize = 1 << (7 + sectorsizebits)
                    ok = True
            
                    if side not in (0, 1):
                        print("side not 0 or 1")
                        ok = False
                        
                    if scan.claimed_trackno != None:
                        if header_trackno != scan.claimed_trackno:
                            print("track number different from other track number on track", header_trackno, scan.claimed_trackno)
                            ok = False
                        
                    if scan.claimed_sectorsize != None:
                        if sectorsize != scan.claimed_sectorsize:
                            print("sector size changed", sectorsize, scan.claimed_sectorsize)
                            ok = False

                    if sectorno >= 30:
                        if sectorno != 66:
                            print("sector number too large", sectorno)
                        ok = False
                        
                    if ok:
                        if len(segment) < 500:
                            currsector = sectorno - 1
                            sector_set = True

                            print("Got new valid header", currsector)
                            scan.found_data[startpos] = ("validheader", header_trackno, sectorno - 1)
                        else:
                            scan.found_data[startpos] = ("header", header_trackno, sectorno - 1)
                        
                                
                        scan.claimed_trackno = header_trackno
                        scan.claimed_sectorsize = sectorsize
                        
                        added = True
                    
                elif data[0] == 0xfb:
                    if want_sectordata:
                        add_new_sector(known_sectors, scan.claimed_trackno, currsector, data[1:])
                        print("Got new valid data", currsector)
                        scan.found_data[startpos] = ("data", len(segment))
                        added = True
                                
                    else:
                        if currsector != None:
                            scan.found_data[startpos] = ("assumed_known_data", len(segment))
                            added = True
                        else:
                            scan.found_data[startpos] = ("assumed_data", len(segment))
                            added = True

            if not added:
                scan.found_data[startpos] = ("unknown", len(segment))
                    
            if not sector_set:
                currsector = None
    
    for scan in scans[::-1]:
        # assume all track numbers are valid and ignore tracks based on that
        if len(known_sectors[scan.trackno]) == target_sectors:
            continue

        totalsectors = sum([len(known_sectors[x]) for x in known_sectors])
        
        print("--------- scan level 3: track number %d file offset %x  total good sectors %d" % (scan.trackno, scan.trackoffset, totalsectors))
        
        # for pos in sorted(scan.positions):
            # startpos = pos + 14
            # if startpos in scan.found_data:
                # entry = scan.found_data[startpos]
                # print("%6d %s" % (startpos, entry))
            # else:
                # print("%6d [MISSING]" % startpos)

        # assume sector size if not set
        sectorsize = scan.claimed_sectorsize
        if sectorsize == None:
            print("had to assume sectorsize 512")
            sectorsize = 512
        
        newpositions = find_dos_sync_deep(scan.trackdata)
        
        for pos, score in newpositions:
            startpos = pos + 14
            
            skip = False
            if startpos in scan.found_data:
                prevtype = scan.found_data[startpos][0]
                if prevtype in ("header", "validheader", "data"):
                    skip = True
                    
            if skip:
                continue
                
            data = None
            for dist, lo, hi, lut in luts:
                segment = scan.trackdata[startpos:]
                bs = Bitstream(segment, lut)
                data = get_data(bs, sectorsize, True)
                if data != None:
                    #print("Got extra data with different lut", dist, startpos in scan.found_data)
                    break
                    
            if data != None:
                if data[0] == 0xfe:
                    cyl, side, sectorno, sectorsizebits = struct.unpack("<BBBB", data[1:5])
                    header_trackno = side + cyl * 2
                    sectorsize = 1 << (7 + sectorsizebits)
                    ok = True
            
                    if side not in (0, 1):
                        print("side not 0 or 1")
                        ok = False
                        
                    if scan.claimed_trackno != None:
                        if header_trackno != scan.claimed_trackno:
                            print("track number different from other track number on track", header_trackno, scan.claimed_trackno)
                            ok = False
                        
                    if scan.claimed_sectorsize != None:
                        if sectorsize != scan.claimed_sectorsize:
                            print("sector size changed", sectorsize, scan.claimed_sectorsize)
                            ok = False

                    if sectorno >= 30:
                        if sectorno != 66:
                            print("sector number too large", sectorno)
                        ok = False
                        
                    if ok:
                        scan.found_data[startpos] = ("header", header_trackno, sectorno - 1)
                                
                        scan.claimed_trackno = header_trackno
                        scan.claimed_sectorsize = sectorsize
                        
                        added = True
                    
                elif data[0] == 0xfb:
                    closest = None
                    for startpos2 in sorted(scan.found_data):
                        if startpos2 < startpos:
                            closest = startpos2
                        else:
                            break
                            
                    if closest != None:
                        if startpos - closest < 500 and scan.found_data[closest][0] in ("header", "validheader"):
                            currsector = scan.found_data[closest][2]
                            if currsector not in known_sectors[scan.claimed_trackno]:
                                print("got new sector %d at position %d with header at position %d distance %d" % (currsector, startpos, closest, startpos - closest))
                                
                            add_new_sector(known_sectors, scan.claimed_trackno, currsector, data[1:])
                            scan.found_data[startpos] = ("data")
                            added = True
                
            if not added:
                scan.found_data[startpos] = ("unknown", len(segment))

if 0 in known_sectors and 0 in known_sectors[0]:
    bootsector = known_sectors[0][0]
    
    bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads = struct.unpack("<HBxxxxxHxxxHH", bootsector[0x0b:0x1c])
        
    print("    BPB: %d bytes/sector, %d sectors per cluster, %d total sectors, %d sectors per track, %d heads" % (bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads))
    if bpb_spt != 0 and (bpb_tot % bpb_spt) == 0:
        print("    Total tracks according to BPB: %d" % (bpb_tot // bpb_spt,))
        
        
highest_with_data = 0
for trackno in range(0, maxtracks):
    if trackno in known_sectors and len(known_sectors[trackno]) != 0:
        highest_with_data = trackno
        
# if target_track == None:
writecount = 0
imgfilename = sys.argv[1] + ".img"
of2 = open(imgfilename, "wb")
for trackno in range(0, highest_with_data + 1):
    missings = []
    for sectorno in range(target_sectors):
        if trackno in known_sectors and sectorno in known_sectors[trackno]:
            of2.write(known_sectors[trackno][sectorno])
            writecount += 1
        else:
            of2.write(b"CWTOOLBADSECTOR!" * 32)
            missings.append(sectorno)

    if len(missings) != 0:
        print("    missing from track", trackno, ":", missings)
        
of2.close()    

print("    sectors written to %s: %d" % (imgfilename, writecount))

