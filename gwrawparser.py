import io, struct, sys, argparse, hashlib

width = 30
mfmdd_drivestats = [-2] * 1024
for i in range(288 - width, 288 + width):
    mfmdd_drivestats[i] = 1

for i in range(426 - width, 426 + width):
    mfmdd_drivestats[i] = 1

for i in range(564 - width, 564 + width):
    mfmdd_drivestats[i] = 1



width = 15
mfmhd_drivestats = [-2] * 1024
for i in range(144 - width, 144 + width):
    mfmhd_drivestats[i] = 1

for i in range(213 - width, 213 + width):
    mfmhd_drivestats[i] = 1

for i in range(282 - width, 282 + width):
    mfmhd_drivestats[i] = 1



mfmdd_lut = [0] * 1024
for i in range(0, 357):
    mfmdd_lut[i] = 2

for i in range(357, 495):
    mfmdd_lut[i] = 4

for i in range(495, 1024):
    mfmdd_lut[i] = 8


mfmhd_lut = [0] * 1024
for i in range(0, 178):
    mfmhd_lut[i] = 2

for i in range(178, 247):
    mfmhd_lut[i] = 4

for i in range(247, 1024):
    mfmhd_lut[i] = 8


mfmdd_lut2 = [None] * 1024
for i in range(0, 357):
    skew = (i - 288) // 2
    if skew < -69:
        skew = -69
        
    mfmdd_lut2[i] = (2, skew)

for i in range(357, 495):
    skew = (i - 426) // 2
    mfmdd_lut2[i] = (4, skew)

for i in range(495, 1024):
    skew = (i - 564) // 2
    if skew > 69:
        skew = 69
    
    mfmdd_lut2[i] = (8, skew)
    

mfmhd_lut2 = [None] * 1024
for i in range(0, 178):
    skew = (i - 144) // 2
    if skew < -35:
        skew = -35
        
    mfmhd_lut2[i] = (2, skew)

for i in range(178, 247):
    skew = (i - 213) // 2
    mfmhd_lut2[i] = (4, skew)

for i in range(247, 1024):
    skew = (i - 282) // 2
    if skew > 35:
        skew = 35
    
    mfmhd_lut2[i] = (8, skew)


def make_lut(trackdata, low, med, high):
    stats = [0] * 1024
    for n in trackdata:
        stats[n] += 1
        
    lowestpos_lo = 0
    lowest = 9999999999
    zeros = 0
    bestzeros = 6 # converting from 14mhz catweasel data WILL leave holes, so make sure we ignore them
    bestzeropos = None
    for i in range(low, med):
        if stats[i] < lowest:
            lowest = stats[i]
            lowestpos_lo = i
            
        if stats[i] == 0:
            zeros += 1
        else:
            if zeros > 0:
                if zeros > bestzeros:
                    bestzeropos = i - (zeros // 2)
                    bestzeros = zeros
                    
            zeros = 0
            
    if bestzeropos != None:
        lowestpos_lo = bestzeropos
        
    lowestpos_hi = 0
    lowest = 9999999999
    zeros = 0
    bestzeros = 6
    bestzeropos = None
    for i in range(med, high):
        if stats[i] < lowest:
            lowest = stats[i]
            lowestpos_hi = i
            
        if stats[i] == 0:
            zeros += 1
        else:
            if zeros > 0:
                if zeros > bestzeros:
                    bestzeropos = i - (zeros // 2)
                    bestzeros = zeros
                    
            zeros = 0
            
    if bestzeropos != None:
        lowestpos_hi = bestzeropos
        
    lut = [0] * 1024
    for i in range(0, lowestpos_lo):
        lut[i] = 2

    for i in range(lowestpos_lo, lowestpos_hi):
        lut[i] = 4

    for i in range(lowestpos_hi, 1023):
        lut[i] = 8
        
    return lut
    
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

def compare_sectors(sector_a, sector_b):
    diff = ""
    for i in range(512):
        if sector_a[i] != sector_b[i]:
            diff += "XX"
        else:
            diff += ".."
            
    for i in range(0, 512, 32):
        print(sector_a[i:i+32].hex(), sector_b[i:i+32].hex(), diff[i*2:i*2+64])
    print("")
    

class Bitstream(object):
    def __init__(self, trackdata, splitlut):
        self.trackdata = [splitlut[x] for x in trackdata]
        self.index = 0
        self.pending = 0
        self.last = None
        
    def get_bit(self):
        if self.pending == 0:
            try:
                self.pending = self.trackdata[self.index]
            except:
                return None
            
            self.index += 1
                
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last

class Bitstream_skew(object):
    def __init__(self, trackdata, splitlut):
        self.trackdata = trackdata
        self.index = 0
        self.pending = 0
        self.splitlut = splitlut
        self.last = None
        self.skew = 0
        
    def get_bit(self):
        if self.pending == 0:
            try:
                t = self.trackdata[self.index]
            except:
                return None

            n = t + self.skew
            if n < 0:
                n = 0
            if n > 1023:
                n = 1023
                
            self.pending, self.skew = self.splitlut[n]
            
            self.index += 1
                
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last
    
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
    
def getamigaword(bs):
    rawres = 0
    missing_syncs = 0
    for i in range(16):
        last = bs.last
        a = bs.get_bit()
        b = bs.get_bit()
        if a == None or b == None:
            return None, missing_syncs
            
        if b == 0 and last == a:
            missing_syncs += 1
            
        rawres = (rawres << 2) | (a << 1) | b
        
    return rawres, missing_syncs
    
def parse_amiga_sector(bs):
    words = []
    total_missing = 0
    csum = 0
    for i in range(12):
        rawres, missing_syncs = getamigaword(bs)
        if rawres == None or missing_syncs != 0:
            #print("bad header data")
            return None, None
            
        words.append(rawres)
        csum ^= rawres
        
    csum &= 0x55555555
    if csum != 0:
        #print("bad Amiga header checksum", hex(csum))
        return None, None
        
    #print("OK Amiga header checksum")
        
    headerdata = ((words[0] & 0x55555555) << 1) | (words[1] & 0x55555555)
    
    format_id = headerdata >> 24
    trackno = (headerdata >> 16) & 0xff
    sectorno = (headerdata >> 8) & 0xff
    until_end = headerdata & 0xff

    if format_id != 0xff:
        #print("Bad format ID", format_id)
        return None, None
        
    if sectorno > 30: # upper limit dumb number picked at random
        #print("Bad sectorno", sectorno)
        return None, None
    
    if until_end > 30: # upper limit dumb number picked at random
        #print("Strange until_end value", until_end)
        return None, None
    
    sector_label = bytearray()
    for i in range(4):
        n = ((words[i+2] & 0x55555555) << 1) | (words[i+6] & 0x55555555)
        sector_label += struct.pack(">I", n)
        
    sector_label = bytes(sector_label)
    if sector_label != bytes(16):
        print("strange sector label", sector_label.hex())
    
    header = (trackno, sectorno, until_end, sector_label)
    
    csum = 0
    words = []
    total_missing = 0
    csum = 0
    for i in range(258):
        rawres, missing_syncs = getamigaword(bs)
        if rawres == None or missing_syncs != 0:
            #print("bad sector data", i, bs.index, rawres, missing_syncs)
            return header, None

        # if rawres == None:
            # print("bad sector data", i, rawres, missing_syncs)
            # return header, None
            
        # if missing_syncs != 0:
            # print("bad sector data", i, trackno, sectorno, bs.index, hex(rawres), missing_syncs)
        
        words.append(rawres)
        csum ^= rawres
        total_missing += missing_syncs
        
    csum &= 0x55555555
    if csum != 0:
        #print("bad data crc", sectorno, hex(csum))
        return header, None
        
    data = bytearray()
    for i in range(128):
        dataword = ((words[i+2] & 0x55555555) << 1) | (words[i+130] & 0x55555555)
        data += struct.pack(">I", dataword)
        
    # if total_missing != 0:
        # print(data.hex())
        
    return header, data
    
# 1 data OK
# -1 CRC error
# -2 undersized/corrupted data

def get_data(bs, sectorsize, want_sectordata=True):
    res, missyncs = getbytes(bs, 7)
    if missyncs == 0 and len(res) == 7:
        if res[0] == 0xfe:
            if crc16(b"\xa1\xa1\xa1" + res) == 0:
                return 1, res[:-2]
            else:    
                return -1, res
                
        elif res[0] == 0xfb:
            if want_sectordata:
                res2, missyncs = getbytes(bs, sectorsize - 4)
                if missyncs == 0 and len(res2) == sectorsize - 4:
                    if crc16(b"\xa1\xa1\xa1" + res + res2) == 0:
                        return 1, res + res2[:-2]
                    else:
                        return -1, res + res2
                else:
                    return -2, res + res2
                    
            else:
                return 1, res
                
    return -2, res
    
    
def find_dos_syncs_fast(trackdata2):
    syncmark = bytes((8, 4, 8, 4, 2, 8, 4, 8, 4, 2, 8, 4, 8, 4))
    
    syncs = []
    
    pos = 0
    while True:
        try:
            pos = trackdata2.index(syncmark, pos)
        except ValueError:
            break
            
        syncs.append(pos)
        pos += 14
        
    return syncs

def find_amiga_syncs_fast(trackdata2):
    syncmark = bytes((8, 4, 8, 4, 2, 8, 4, 8, 4))
    
    syncs = []
    
    pos = 0
    while True:
        try:
            pos = trackdata2.index(syncmark, pos)
        except ValueError:
            break
            
        syncs.append(pos)
        pos += 9
        
    return syncs
    
def quick_scan_dos(args, rawtrack, new_sectors, lut, quality, sourcefunc, use_skew=False):
    syncs = sorted(rawtrack.syncs)
    
    # map out headers and candidate data
    for idx in range(len(syncs)-1):
        startpos = syncs[idx]+14
        endpos = syncs[idx+1]
        
        if startpos in rawtrack.found_data:
            continue
            
        segment = rawtrack.trackdata[startpos:endpos]
        if not use_skew:
            bs = Bitstream(segment, lut)
        else:
            bs = Bitstream_skew(segment, lut)
        
        res, data = get_data(bs, 0, False) # only want first bytes of data right now
        if res == 1:
            if data[0] == 0xfe:
                cyl, side, rawsectorno, sectorsizebits = struct.unpack("<BBBB", data[1:5])
                htrackno = side + cyl * 2
                sectorsize = 1 << (7 + sectorsizebits)
                if sectorsize != 512:
                    print("Nonstandard header sectorsize", sectorsize, "for sector", rawsectorno - 1)
                    
                ok = True
        
                if side not in (0, 1):
                    print("header side not 0 or 1!!!")
                    ok = False
                    
                #if rawsectorno >= 30:
                    #if rawsectorno != 66:
                    #print("raw sector number too large", rawsectorno)
                    #ok = False
                    
                if ok:
                    rawtrack.found_data[startpos] = ["header", htrackno, rawsectorno - 1, sectorsize]
                
            elif data[0] == 0xfb:
                rawtrack.found_data[startpos] = ["datastub"]
                
    for idx in range(len(syncs)-1):
        startpos = syncs[idx]+14
        endpos = syncs[idx+1]
        
        if startpos in rawtrack.found_data and rawtrack.found_data[startpos][0] == "header":
            _, htrackno, sectorno, sectorsize = rawtrack.found_data[startpos]
            startpos2 = syncs[idx+1]+14
            if startpos2 in rawtrack.found_data and rawtrack.found_data[startpos2][0] == "datastub":
                distance = startpos2 - startpos
                if distance < 500:
                    if distance > 350:
                        print("unusually long distance between header and data?", distance, sectorno)
                        
                    segment = rawtrack.trackdata[startpos2:]
                    if not use_skew:
                        bs = Bitstream(segment, lut)
                    else:
                        bs = Bitstream_skew(segment, lut)

                    res, data = get_data(bs, sectorsize, True)
                    if res == 1:
                        if data[0] != 0xfb:
                            raise Exception("WTF?!?!")
                            
                        data = bytes(data[1:])
                        
                        sec = Sector(htrackno, sectorno, sectorsize, quality, "dos", sourcefunc, rawtrack, startpos, data)

                        rawtrack.found_data[startpos][0] = "usedheader"
                        rawtrack.found_data[startpos2] = ["data", htrackno, sectorno, sectorsize, sec]
                        
                        if rawtrack.add_sector(sec):
                            new_sectors.append(sec)
                    else:
                        # handle broken sector here, with logging or something
                        pass


def quick_scan_amiga(args, rawtrack, new_sectors, lut, quality, sourcefunc, use_skew=False):
    syncs = sorted(rawtrack.syncs)
    
    for idx in range(len(syncs)-1):
        startpos = syncs[idx]+9
        endpos = syncs[idx+1]
        
        if startpos in rawtrack.found_data:
            continue
            
        segment = rawtrack.trackdata[startpos:endpos]
            
        if not use_skew:
            bs = Bitstream(segment, lut)
        else:
            bs = Bitstream_skew(segment, lut)

        header, data = parse_amiga_sector(bs)
        if header != None:
            htrackno, sectorno, until_end, sector_label = header
            if data != None:
                
                sec = Sector(htrackno, sectorno, 512, quality, "amiga", sourcefunc, rawtrack, startpos, bytes(data))
                rawtrack.found_data[startpos] = ["data", htrackno, sectorno, 512, sec]
                
                if rawtrack.add_sector(sec):
                    new_sectors.append(sec)

    
def quick_scan_track(args, rawtrack):
    new_sectors = []
    
    if args.hd:
        lut = mfmhd_lut
    else:
        lut = mfmdd_lut
        
    trackdata2 = bytes(lut[x] for x in rawtrack.trackdata)
    
    syncs = find_dos_syncs_fast(trackdata2)
    rawtrack.add_syncs(syncs, "dos")
    if rawtrack.has_syncs("dos"):
        quick_scan_dos(args, rawtrack, new_sectors, lut, 3, "quick_dos_standardlut")
        
    syncs = find_amiga_syncs_fast(trackdata2)
    rawtrack.add_syncs(syncs, "amiga")
    if rawtrack.has_syncs("amiga"):
        quick_scan_amiga(args, rawtrack, new_sectors, lut, 3, "quick_amiga_standardlut")
        
    return new_sectors

def quick_scan_track_customlut(args, rawtrack):
    new_sectors = []
    
    if args.hd:
        lut = make_lut(rawtrack.trackdata, 144, 213, 282)
    else:
        lut = make_lut(rawtrack.trackdata, 288, 426, 564)
        
    trackdata2 = bytes(lut[x] for x in rawtrack.trackdata)
    
    syncs = find_dos_syncs_fast(trackdata2)
    rawtrack.add_syncs(syncs, "dos")
    if rawtrack.has_syncs("dos"):
        quick_scan_dos(args, rawtrack, new_sectors, lut, 2, "quick_dos_customlut")
        
    syncs = find_amiga_syncs_fast(trackdata2)
    rawtrack.add_syncs(syncs, "amiga")
    if rawtrack.has_syncs("amiga"):
        quick_scan_amiga(args, rawtrack, new_sectors, lut, 2, "quick_amiga_customlut")
        
    return new_sectors

def quick_scan_track_skew(args, rawtrack):
    new_sectors = []
    
    if args.hd:
        lut = mfmhd_lut
        lut2 = mfmhd_lut2
    else:
        lut = mfmdd_lut
        lut2 = mfmdd_lut2
        
    trackdata2 = bytes(lut[x] for x in rawtrack.trackdata)
    
    syncs = find_dos_syncs_fast(trackdata2)
    rawtrack.add_syncs(syncs, "dos")
    if rawtrack.has_syncs("dos"):
        quick_scan_dos(args, rawtrack, new_sectors, lut2, 1, "quick_dos_skew", True)
        
    syncs = find_amiga_syncs_fast(trackdata2)
    rawtrack.add_syncs(syncs, "amiga")
    if rawtrack.has_syncs("amiga"):
        quick_scan_amiga(args, rawtrack, new_sectors, lut2, 1, "quick_amiga_skew", True)
        
    return new_sectors


def quick_scan_hd_track(trackdata):
    syncs = find_dos_syncs_fast(trackdata, mfmhd_lut)
    if len(syncs) != 0:
        return "dos", quick_scan_dos(trackdata, syncs, mfmhd_lut), len(syncs)
        
    syncs = find_amiga_syncs_fast(trackdata, mfmhd_lut)
    if len(syncs) != 0:
        return "amiga", quick_scan_amiga(trackdata, syncs, mfmhd_lut), len(syncs)
        
    return "unknown", [], 0

def deeper_scan_track(trackdata):
    #lut = make_lut(trackdata)
    
    syncs = find_dos_syncs_fast(trackdata, mfmdd_lut)
    if len(syncs) != 0:
        return "dos", quick_scan_dos(trackdata, syncs, mfmdd_lut2, True), len(syncs)
        
    syncs = find_amiga_syncs_fast(trackdata, mfmdd_lut)
    if len(syncs) != 0:
        return "amiga", quick_scan_amiga(trackdata, syncs, mfmdd_lut2, True), len(syncs)
        
    return "unknown", [], 0

def deeper_scan_hd_track(trackdata):
    #lut = make_lut(trackdata)
    
    syncs = find_dos_syncs_fast(trackdata, mfmhd_lut)
    if len(syncs) != 0:
        return "dos", quick_scan_dos(trackdata, syncs, mfmhd_lut2, True), len(syncs)
        
    syncs = find_amiga_syncs_fast(trackdata, mfmhd_lut)
    if len(syncs) != 0:
        return "amiga", quick_scan_amiga(trackdata, syncs, mfmhd_lut2, True), len(syncs)
        
    return "unknown", [], 0
    
class Sector:
    def __init__(self, htrackno, sectorno, sectorsize, quality, sectortype, sourcefunc, rawtrack, position, data):
        self.htrackno = htrackno
        self.sectorno = sectorno
        self.sectorsize = sectorsize
        self.quality = quality
        self.sectortype = sectortype
        self.sourcefunc = sourcefunc
        self.rawtrack = rawtrack
        self.position = position # this is the position of the header preceding the data
        self.data = data
        
class RawTrack:
    def __init__(self, filename, trackoffset, trackno, trackdata):
        self.filename = filename
        self.trackoffset = trackoffset
        self.trackno = trackno
        self.trackdata = trackdata
        self.syncs = {}
        self.found_data = {}
        self.known_sectors = {}
        self.highest_sector = -1
        
    def add_syncs(self, syncs, synctype):
        new_syncs = False
        for syncpos in syncs:
            if syncpos not in self.syncs:
                self.syncs[syncpos] = synctype
                new_syncs = True
            else:
                if self.syncs[syncpos] == "amiga" and synctype == "dos":
                    # we found a longer DOS sync as a subset of an Amiga sync, override it
                    self.syncs[syncpos] = synctype
                    new_syncs = True
                    
        return new_syncs
        
    def has_syncs(self, synctype):
        for syncpos in self.syncs:
            if self.syncs[syncpos] == synctype:
                return True
                
        return False
        
    def add_sector(self, sec):
        ts = (sec.htrackno, sec.sectorno)
        if ts not in self.known_sectors:
            if sec.sectorno >= 30:
                print("sector with too large sector number!!!!!!!!!", sec.sectorno)
                return False
                
            if sec.sectorsize != 512:
                print("Added sector %d,%d with nonstandard sectorsize %d" % (sec.htrackno, sec.sectorno, sec.sectorsize))

            if sec.htrackno != self.trackno:
                print("Mismatch between rawtrack trackno %d and header trackno %d" % (self.trackno, sec.htrackno))
                
            self.known_sectors[ts] = {}
            self.known_sectors[ts][sec.data] = [sec]
            
            self.highest_sector = max(self.highest_sector, sec.sectorno)
            return True
            
        else:
            if sec.data in self.known_sectors[ts]:
                self.known_sectors[ts][sec.data].append(sec)
                return False
                
            else:
                print("SECTOR MISMATCH INSIDE RAW TRACK trackno %d htrackno %d sector %d" % (self.trackno, sec.htrackno, sec.sectorno))
                self.known_sectors[ts][sec.data] = [sec]
                return True
                
                #compare_sectors(self.known_sectors[ts].data, sec.data)
                
                # if self.known_sectors[ts].quality > sec.quality:
                    # print("USING NEW SECTOR BECAUSE OF QUALITY")
                    # self.known_sectors[ts] = sec
                    # return True

        return False
        
    def get_descr(self):
        # unused_headers = set()
        # for startpos in self.found_data:
            # if self.found_data[startpos][0] == "header":
                # _, htrackno, sectorno, sectorsize = self.found_data[startpos]
                # if htrackno != self.trackno:
                    # unused_headers.add("!%d,%d" % (htrackno, sectorno))
                # else:
                    # unused_headers.add(str(sectorno))
                    
        # return " ".join(sorted(unused_headers))
        
        s = ""
        for syncpos in sorted(self.syncs):
            if self.syncs[syncpos] == "dos":
                startpos = syncpos + 14
            else:
                startpos = syncpos + 9
                
            if startpos in self.found_data:
                datainfo = self.found_data[startpos]
                datatype = datainfo[0]
                if datatype == "header":
                    s += "H%d " % datainfo[2]
                elif datatype == "datastub":
                    s += "D "
                elif datatype == "usedheader":
                    s += "h%d " % datainfo[2]
                elif datatype == "data":
                    s += "d "
                else:
                    s += "! "
            else:
                s += "? "
                
        return s

def gather_rawtracks(args, target_tracks):
    rawtracks = []
    
    for filename in args.filenames:
        f = open(filename, "rb")

        magic = f.read(32)
        if magic != b"gwreader raw data".ljust(32, b"\x00"):
            raise Exception("bad magic")
            
        while True:
            trackoffset = f.tell()
            datatype = f.read(1)
            if len(datatype) == 0:
                break
                
            if datatype == b"\x00":
                sz = struct.unpack("<I", f.read(4))[0]
                comment = f.read(sz)
                
            elif datatype != b"\xca":
                raise Exception()
                
            else:
                trackno, indexsize, fluxsize = struct.unpack("<BII", f.read(9))
                f.read(indexsize) # ignore indexes for now
                fluxdata = f.read(fluxsize)

                if trackno in target_tracks:
                    bio = io.BytesIO(fluxdata)
                    trackdata = []
                    while True:
                        b = bio.read(2)
                        if len(b) == 0:
                            break
                            
                        flux = struct.unpack("<H", b)[0]
                        if flux == 0xffff:
                            flux = struct.unpack("<Q", bio.read(8))[0]
                        trackdata.append(flux)

                    trackdata = [min(x, 1023) for x in trackdata]
                    
                    rt = RawTrack(filename, trackoffset, trackno, trackdata)
                    rawtracks.append(rt)
                
                
    return rawtracks

class Processor:
    def __init__(self, args):
        self.args = args
        self.known_sectors = {}
        self.highest_sector = -1
        self.highest_track = -1
        
    def process_tracks(self, rawtracks, scanner_func):
        for rawtrack in rawtracks:
            new_sectors = scanner_func(self.args, rawtrack)
            
            added = 0
            
            for sec in new_sectors:
                ts = (sec.htrackno, sec.sectorno)
                if ts not in self.known_sectors:
                    if sec.htrackno != rawtrack.trackno:
                        if not self.args.ignoreht:
                            continue
                            
                        print("adding sector htrack %d sector %d even though it's actually on track %d" % (sec.htrackno, sec.sectorno, rawtrack.trackno))
                        
                    self.known_sectors[ts] = {}
                    self.known_sectors[ts][sec.data] = [sec]
                     
                    if rawtrack.trackno < 150:  # some disks "end" below 160 too but have more data after
                        self.highest_sector = max(self.highest_sector, sec.sectorno)
                        
                    self.highest_track = max(self.highest_track, rawtrack.trackno)
                    
                    added += 1
                else:
                    if sec.data in self.known_sectors[ts]:
                        self.known_sectors[ts][sec.data].append(sec)
                    else:
                        print("SECTOR MISMATCH BETWEEN RAW TRACKS trackno %d htrackno %d sector %d" % (rawtrack.trackno, sec.htrackno, sec.sectorno))
                        self.known_sectors[ts][sec.data] = [sec]
                        added += 1
                        
            if added > 0:
                print("got %d new sectors after processing track %d, now in total %d | %s" % (added, rawtrack.trackno, len(self.known_sectors), rawtrack.get_descr()))
        
        
def main():
    parser = argparse. ArgumentParser()
    parser.add_argument("filenames", nargs="+")

    parser.add_argument("-t", "--tracks")
    parser.add_argument("--odd", action="store_true")
    parser.add_argument("--even", action="store_true")

    parser.add_argument("--nsectors", type=int, default=-1)
    parser.add_argument("--hd", action="store_true")
    parser.add_argument("--ignoreht", action="store_true")
    parser.add_argument("--selected")
    
    args = parser.parse_args()
    
    if args.tracks:
        if "-" in args.tracks:
            start, end = args.tracks.split("-")
            target_tracks = set(range(int(start), int(end)+1))
            
        else:
            target_tracks = set([int(x) for x in args.tracks.split(",")])
            
    else:
        if args.even:
            target_tracks = set(range(0, 168, 2))
        elif args.odd:
            target_tracks = set(range(1, 168, 2))
        else:
            target_tracks = set(range(0, 168, 1))
            
            
    rawtracks = gather_rawtracks(args, target_tracks)
    
    
    proc = Processor(args)
    
    print("starting normal scan")
    proc.process_tracks(rawtracks, quick_scan_track)
    
    print("starting custom lut scan")
    proc.process_tracks(rawtracks, quick_scan_track_customlut)
    
    print("starting skew lut scan")
    proc.process_tracks(rawtracks, quick_scan_track_skew)


    if args.selected:
        selected = args.selected.split(",")
    else:
        selected = []
    
    sectorchoices = {}
    for ts in proc.known_sectors:
        trackno, sectorno = ts
        known = proc.known_sectors[ts]
        variants = len(known)

        if variants == 1:
            secs = list(known.values())[0]
            sec = secs[0] # pick the first as representative
            sectorchoices[ts] = (sec, len(secs))
            
        else:
            print("MULTIPLE CONFLICTING SECTORS FOR TRACK %d SECTOR %d" % (trackno, sectorno))
            votedata = []
            pickedsector = None
            for seckey in known:
                votes = len(known[seckey])
                quality = 0
                for sec in known[seckey]:
                    quality += sec.quality
                    
                fingerprint = hashlib.sha256(known[seckey][0].data).hexdigest()[0:12]
                if fingerprint in selected:
                    if pickedsector != None:
                        raise Exception("picked multiple selected from conflicting sectors")
                        
                    pickedsector = known[seckey][0]
                    print("picked sector based on given fingerprint")
                    
                votedata.append((votes, quality, seckey, fingerprint))
                
            sortedvotes = sorted(votedata)[::-1]
            
            if pickedsector == None:
                votes, quality, seckey, fingerprint = sortedvotes[0]
                pickedsector = known[seckey][0]
                sectorchoices[ts] = (pickedsector, votes)
            
            if sortedvotes[0][0] == sortedvotes[1][0] and sortedvotes[0][1] == sortedvotes[1][1]:
                print("WARNING TOP 2 SECTORS WITH EQUAL VOTES AND QUALITY")
                
            for votes, quality, seckey, fingerprint in sortedvotes:
                desc = "fp %s  %d votes:" % (fingerprint, votes)
                for sec in known[seckey]:
                    desc += " %s,%d" % (sec.sourcefunc, sec.quality)
                    
                sec = known[seckey][0]
                if sec == pickedsector:
                    print("SELECTED", desc)
                    for i in range(0, 512, 32):
                        print(sec.data[i:i+32].hex())
                        
                    print("")
                else:
                    print(desc)
                    compare_sectors(sec.data, pickedsector.data)

    
    
    if args.nsectors != -1:
        nsectors = args.nsectors
    else:
        nsectors = proc.highest_sector + 1
        
    target_sectorsize = 512
    
    remaining_ts = set(sectorchoices)
    goodcount = 0
    badcount = 0
    
    sectortypestats = {}
    output = bytearray()
    for trackno in target_tracks:
        # skip empty tracks
        if trackno > proc.highest_track:
            continue
            
        trackdesc = "%3d: " % trackno
        
        missings = []
        
        for sectorno in range(nsectors):
            added = False
            ts = (trackno, sectorno)
            if ts in sectorchoices:
                sec, count = sectorchoices[ts]
                if sec.sectorsize == target_sectorsize:
                    output += sec.data
                    trackdesc += "%3d " % count
                    
                    if sec.sectortype not in sectortypestats:
                        sectortypestats[sec.sectortype] = 0
                    sectortypestats[sec.sectortype] += 1
                    
                    added = True
                    remaining_ts.remove(ts)
                    goodcount += 1
                    
                else:
                    print("skipping sector because different sector size %d" % sec.sectorsize)
                    
            if not added:
                output += b"CWTOOLBADSECTOR!" * 32
                missings.append(sectorno)
                trackdesc += "--- "
                badcount += 1
                
        if len(missings) != 0:
            print(trackdesc, "missing", missings)
        
    if (0,0) in proc.known_sectors:
        secs = proc.known_sectors[(0,0)]
        if len(secs) > 1:
            print("DUPLICATE SECTOR 0,0!")
            
        elif len(secs) == 1:
            sec = list(secs.values())[0][0]
            if sec.sectortype == "dos":
                bootsector = sec.data
                bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads = struct.unpack("<HBxxxxxHxxxHH", bootsector[0x0b:0x1c])
                    
                print("    BPB: %d bytes/sector, %d sectors per cluster, %d total sectors, %d sectors per track, %d heads" % (bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads))
                if bpb_spt != 0 and (bpb_tot % bpb_spt) == 0:
                    print("    Total tracks according to BPB: %d" % (bpb_tot // bpb_spt,))
        
    imgfilename = sys.argv[1] + ".img"
    of2 = open(imgfilename, "wb")
    of2.write(output)
    of2.close()    

    print("    sector type stats", sectortypestats)
    print("    sectors written to %s: %d good    %d bad" % (imgfilename, goodcount, badcount))
          
    for ts in sorted(remaining_ts):
        print("Not included in image: track %d sector %d" % ts)
        sec, count = sectorchoices[ts]
        empty = False
        if sec.data == bytes(512):
            empty = True
            
        if empty:
            print("Empty")
        else:
            for i in range(0, 512, 32):
                print(sec.data[i:i+32].hex())
                
        print("")
            
if __name__ == "__main__":
    main()