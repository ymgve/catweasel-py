import io, struct, sys

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


def make_lut(trackdata):
    stats = [0] * 1024
    for n in trackdata:
        stats[n] += 1
        
    lowestpos_lo = 0
    lowest = 9999999999
    zeros = 0
    bestzeros = 0
    bestzeropos = None
    for i in range(288, 426):
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
    bestzeros = 0
    bestzeropos = None
    for i in range(426, 564):
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
    
    sector_label = b""
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
        
    data = b""
    for i in range(128):
        dataword = ((words[i+2] & 0x55555555) << 1) | (words[i+130] & 0x55555555)
        data += struct.pack(">I", dataword)
        
    # if total_missing != 0:
        # print(data.hex())
        
    return header, data
    

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

def find_amiga_syncs_fast(trackdata, splitlut):
    trackdata2 = bytes(splitlut[x] for x in trackdata)
    
    syncmark = bytes((8, 4, 8, 4, 2, 8, 4, 8, 4))
    
    positions = []
    
    pos = -1
    while True:
        try:
            pos = trackdata2.index(syncmark, pos + 1)
        except ValueError:
            break
            
        positions.append(pos)
        
    return set(positions)
    
def quick_scan_dos(trackdata, syncs, lut, use_skew=False):
    known_sectors = {}
    found_data = {}
    
    syncs = sorted(syncs)
    
    # map out headers and candidate data
    for idx in range(len(syncs)-1):
        startpos = syncs[idx]+14
        endpos = syncs[idx+1]
        segment = trackdata[startpos:endpos]
        if not use_skew:
            bs = Bitstream(segment, lut)
        else:
            bs = Bitstream_skew(segment, lut)
        
        data = get_data(bs, 0, False) # only want first bytes of data right now
        if data != None:
            if data[0] == 0xfe:
                cyl, side, rawsectorno, sectorsizebits = struct.unpack("<BBBB", data[1:5])
                htrackno = side + cyl * 2
                sectorsize = 1 << (7 + sectorsizebits)
                if sectorsize != 512:
                    print("Nonstandard header sectorsize", sectorsize, "for sector", rawsectorno - 1)
                    
                ok = True
        
                if side not in (0, 1):
                    print("side not 0 or 1")
                    ok = False
                    
                if rawsectorno >= 30:
                    if rawsectorno != 66:
                        print("raw sector number too large", rawsectorno)
                    ok = False
                    
                if ok:
                    found_data[startpos] = ("header", htrackno, rawsectorno - 1, sectorsize)
                
            elif data[0] == 0xfb:
                found_data[startpos] = ("datastub",)
                
    for idx in range(len(syncs)-1):
        startpos = syncs[idx]+14
        endpos = syncs[idx+1]
        
        if startpos in found_data and found_data[startpos][0] == "header":
            _, htrackno, sectorno, sectorsize = found_data[startpos]
            startpos2 = syncs[idx+1]+14
            if startpos2 in found_data and found_data[startpos2][0] == "datastub":
                distance = startpos2 - startpos
                if distance < 500:
                    if distance > 350:
                        print("unusually long distance between header and data?", distance, sectorno)
                        
                    segment = trackdata[startpos2:]
                    if not use_skew:
                        bs = Bitstream(segment, lut)
                    else:
                        bs = Bitstream_skew(segment, lut)

                    data = get_data(bs, sectorsize, True)
                    if data != None:
                        if data[0] != 0xfb:
                            raise Exception("WTF?!?!")
                            
                        data = data[1:]
                        
                        ts = (htrackno, sectorno)
                        if ts not in known_sectors:
                            known_sectors[ts] = data
                        else:
                            if known_sectors[ts] != data:
                                print("SECTOR MISMATCH!")
                                compare_sectors(known_sectors[ts], data)

                        found_data[startpos2] = ("data",)
                        
                        if sectorsize != 512:
                            print("Added sector %d,%d with nonstandard sectorsize %d" % (htrackno, sectorno, sectorsize))
                         
    return known_sectors

def quick_scan_amiga(trackdata, syncs, lut, use_skew=False):
    known_sectors = {}

    syncs = sorted(syncs)
    for idx in range(len(syncs)-1):
        syncpos = syncs[idx]
        startpos = syncpos+9
        endpos = syncs[idx+1]
        segment = trackdata[startpos:endpos]
            
        if not use_skew:
            bs = Bitstream(segment, lut)
        else:
            bs = Bitstream_skew(segment, lut)

        header, data = parse_amiga_sector(bs)
        if header != None:
            htrackno, sectorno, until_end, sector_label = header
            if data != None:
                ts = (htrackno, sectorno)
                if ts not in known_sectors:
                    known_sectors[ts] = data
                else:
                    if known_sectors[ts] != data:
                        print("SECTOR MISMATCH!")
                        compare_sectors(known_sectors[ts], data)

    return known_sectors
    
def quick_scan_track(trackdata):
    syncs = find_dos_syncs_fast(trackdata, mfmdd_lut)
    if len(syncs) != 0:
        return "dos", quick_scan_dos(trackdata, syncs, mfmdd_lut), len(syncs)
        
    syncs = find_amiga_syncs_fast(trackdata, mfmdd_lut)
    if len(syncs) != 0:
        return "amiga", quick_scan_amiga(trackdata, syncs, mfmdd_lut), len(syncs)
        
    return "unknown", [], 0

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
    
def main():
    known_sectors = {}
    
    highest_sector = 8
    highest_with_data = 0
    
    f = open(sys.argv[1], "rb")

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
            #print("comment:", comment)
            
        elif datatype != b"\xca":
            raise Exception()
            
        else:
            trackno, indexsize, fluxsize = struct.unpack("<BII", f.read(9))
            f.read(indexsize)
            
            fluxdata = f.read(fluxsize)

            if "even" in sys.argv and trackno % 2 != 0:
                continue
                
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

            totalsectors = sum([len(known_sectors[x]) for x in known_sectors])
            
            print("--------- track number %d file offset %x  total good sectors %d" % (trackno, trackoffset, totalsectors))

            if trackno not in known_sectors:
                known_sectors[trackno] = {}
                
            if "hd" in sys.argv:
                tracktype, new_sectors, synccount = quick_scan_hd_track(trackdata)
                tracktype2, new_sectors2, synccount2 = deeper_scan_hd_track(trackdata)
            else:
                tracktype, new_sectors, synccount = quick_scan_track(trackdata)
                tracktype2, new_sectors2, synccount2 = deeper_scan_track(trackdata)
            
            if len(new_sectors) + len(new_sectors2) > 0:
                if len(new_sectors) > len(new_sectors2):
                    print("quick scan wins!  quick %2d  deep %2d" % (len(new_sectors), len(new_sectors2)))
                    
                elif len(new_sectors) < len(new_sectors2):
                    print("deeper scan wins! quick %2d  deep %2d" % (len(new_sectors), len(new_sectors2)))
                    
            if len(new_sectors) > 0 or len(new_sectors2) > 0:
                highest_with_data = max(highest_with_data, trackno)
                
            for ts in new_sectors:
                htrackno, sectorno = ts
                if htrackno != trackno:
                    print("sector %d on wrong track, claims %d but should be %d" % (sectorno, htrackno, trackno))
                    print("adding anyway!")
                    
                if sectorno not in known_sectors[trackno]:
                    known_sectors[trackno][sectorno] = new_sectors[ts]
                else:
                    if known_sectors[trackno][sectorno] != new_sectors[ts]:
                        #raise Exception("MISMATCHING SECTORS")
                        print("SECTOR MISMATCH", trackno, sectorno)
                        compare_sectors(known_sectors[trackno][sectorno], new_sectors[ts])
                        # use the quick scan one?
                        known_sectors[trackno][sectorno] = new_sectors[ts]
                        
                if trackno < 160:
                    highest_sector = max(highest_sector, sectorno)

            for ts in new_sectors2:
                htrackno, sectorno = ts
                if htrackno != trackno:
                    print("sector %d on wrong track, claims %d but should be %d" % (sectorno, htrackno, trackno))
                    print("adding anyway!")
                    
                if sectorno not in known_sectors[trackno]:
                    known_sectors[trackno][sectorno] = new_sectors2[ts]
                    print("Added another sector from deeper scan!", trackno, sectorno)
                else:
                    if known_sectors[trackno][sectorno] != new_sectors2[ts]:
                        #raise Exception("MISMATCHING SECTORS")
                        print("SECTOR MISMATCH", trackno, sectorno)
                        compare_sectors(known_sectors[trackno][sectorno], new_sectors2[ts])
                        
                if trackno < 160:
                    highest_sector = max(highest_sector, sectorno)
                     
    if 0 in known_sectors and 0 in known_sectors[0]:
        bootsector = known_sectors[0][0]
        
        bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads = struct.unpack("<HBxxxxxHxxxHH", bootsector[0x0b:0x1c])
            
        print("    BPB: %d bytes/sector, %d sectors per cluster, %d total sectors, %d sectors per track, %d heads" % (bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads))
        if bpb_spt != 0 and (bpb_tot % bpb_spt) == 0:
            print("    Total tracks according to BPB: %d" % (bpb_tot // bpb_spt,))
            
    writecount = 0
    imgfilename = sys.argv[1] + ".img"
    of2 = open(imgfilename, "wb")
    for trackno in range(0, highest_with_data + 1):
        if "even" in sys.argv and trackno % 2 == 1:
            continue
            
        missings = []
        for sectorno in range(highest_sector + 1):
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

                    
            
if __name__ == "__main__":
    main()