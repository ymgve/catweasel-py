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
        
def parse_gap(bs):
    # byte, missync = getbyte(bs)
    # print hex(byte), missync
    # if byte != 0xc2 or missync != 1:
        # raise Exception("Bad gap")

    # byte, missync = getbyte(bs)
    # print hex(byte), missync
    # if byte != 0xc2 or missync != 1:
        # raise Exception("Bad gap")
        
    byte, missync = getbyte(bs)
    #print hex(byte), missync
    if byte != 0xfc or missync != 0:
        return False
        
    return True
        
def parse_head(bs, sectorsize, curr_header):
    byte, missync = getbyte(bs)
    if missync != 0:
        return None
        
    if byte not in (0xfb, 0xfe):
        return None
        
    if byte == 0xfe:
        res, missync = getbytes(bs, 6)
        if missync != 0:
            #print("missyncs in weird place!!")
            pass
        
        if len(res) != 6:
            return None
            
        crc = crc16(b"\xa1\xa1\xa1\xfe" + res)
        if crc != 0:
            #print("bad header CRC")
            return None
            
        cyl, side, sec, sz = struct.unpack("<BBBB", res[0:4])
        return ("header", cyl, side, sec, sz)
        
    elif byte == 0xfb:
        if curr_header != None and curr_header[2] == 11 and sectorsize != 512:
            print("SKIPPING STRANGE TRAILING SECTOR")
            return None
            
        res, missync = getbytes(bs, sectorsize + 2)
        if missync != 0:
            #print("missyncs in weird place!!")
            pass
        
        if len(res) != sectorsize + 2:
            return None
            
        crc = crc16(b"\xa1\xa1\xa1\xfb" + res)
        if crc != 0:
            #print("bad data CRC")
            return None
            
        return ("data", res[0:sectorsize])

    
def try_parse_mfm(trackdata):

    known_sectors = {}
    curr_header = None
    bits_since_header = 0
    known_cylside = None
    sectorsize = 512
    
    bs = Bitstream(trackdata)
    
    buffer = []
    check = 0
    while True:
        bit = bs.get_bit()
        if bit == None:
            break
            
        buffer.append(bit)
        check = (check << 1) | bit
        check &= 0xffffffffffff

        bits_since_header += 1
        
        if check == 0x522452245224:
            res = parse_gap(bs)
            if res != None:
                # print "FOUND GAP"
                # print "extra data size", len(buffer)
                buffer = []
                curr_header = None
            
        if check == 0x448944894489:
            # print "FOUND HEAD"
            # print "extra data size", len(buffer)
                
            res = parse_head(bs, sectorsize, curr_header)
            if res != None:
                buffersize = len(buffer)
                buffer = []
                if res[0] == "header":
                    if curr_header != None:
                        #print("Reached another header before data!")
                        pass
                        
                    cyl, side, sec, sz = res[1:]
                    #print("found sector header cyl %d side %d sec %d" % (cyl, side, sec))
                    cylside = (cyl, side)
                    if sz not in (1, 2):
                        raise Exception("bad sector size! %d" % sz)
                        
                    sectorsize2 = 1 << (7+sz)
                    if sectorsize != sectorsize2:
                        print("Changing sector size from %d to %d for sector %d" % (sectorsize, sectorsize2, sec))
                        sectorsize = sectorsize2
                        
                    if known_cylside == None:
                        known_cylside = cylside
                    else:
                        if known_cylside != cylside:
                            print("sector header at wrong track", known_cylside, cylside, sec)
                            
                    curr_header = (cyl, side, sec, sz)
                    bits_since_header = 0
                    
                elif res[0] == "data":
                    if bits_since_header > 1500 and curr_header != None:
                        print("unusual many bits since header, ignoring data as it might belong to another header", bits_since_header, curr_header)
                        curr_header = None
                    
                        
                    if curr_header is None:
                        #print("sector data with no header")
                        pass
                    else:
                        if curr_header in known_sectors:
                            if known_sectors[curr_header] != res[1]:
                                print("DATA MISMATCH")
                                
                        else:
                            known_sectors[curr_header] = res[1]
                            #print("OK data for sector", curr_header, hashlib.sha256(res[1]).hexdigest()[0:16])
                            # for ii in range(16):
                                # print(res[1][ii*32:ii*32+32].hex())
                            
                        curr_header = None
            #exit()
        
    return known_sectors
    
if __name__ == "__main__":
    known_sectors = {}
    f = open(sys.argv[1], "rb")

    magic = f.read(32)
    if magic != b"cwtool raw data 3".ljust(32, b"\x00"):
        raise Exception("bad magic")
        
        
    while True:
        trackoffset = f.tell()
        trackheader = f.read(8)
        if len(trackheader) == 0:
            break
            
        trackmagic, trackno, clock, flags, tsize = struct.unpack("<BBBBI", trackheader)
        if trackmagic != 0xca:
            raise Exception()
        trackdata = f.read(tsize)
        
        #open("tracks\\trackdata%03d.bin" % trackno, "wb").write(trackdata)
        
        # if trackno != 25:
            # continue
            
        print("------------- track number %d file offset %x" % (trackno, trackoffset))
        
        new_sectors = try_parse_mfm(trackdata)
        for sector_header in new_sectors:
            cyl, side, sectorno, sz = sector_header
            if trackno != cyl * 2 + side:
                print("Sector on wrong track!", trackno, cyl * 2 + side, sectorno)
            else:
                ts = (trackno, sectorno)
                if ts not in known_sectors:
                    known_sectors[ts] = new_sectors[sector_header]
                else:
                    if known_sectors[ts] != new_sectors[sector_header]:
                        print("SECTOR MISMATCH", trackno, sector_header)
        
        #print(len(known_sectors))

        #break
        