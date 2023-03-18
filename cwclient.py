import socket, struct, sys, os, time

import rawparser

CW_TRACKINFO_CLOCK_14MHZ = 0
CW_TRACKINFO_CLOCK_28MHZ = 1
CW_TRACKINFO_CLOCK_56MHZ = 2

CW_TRACKINFO_MODE_NORMAL = 0
CW_TRACKINFO_MODE_INDEX_WAIT = 1
CW_TRACKINFO_MODE_INDEX_STORE = 2

HEADER_FLAG_INDEX_STORED = 2
HEADER_FLAG_INDEX_ALIGNED = 4

headermagic = b"cwtool raw data 3".ljust(32, b"\x00")
trackmagic = 0xca

def recv_all(sc, size):
    res = b""
    while len(res) < size:
        rec = sc.recv(size - len(res))
        if len(rec) == 0:
            raise Exception("DASDSADS")
            
        res += rec
        
    return res

        
sc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sc.connect(("192.168.0.46", 12322))

filename = sys.argv[1]

if not os.path.isfile(filename):
    of = open(filename, "wb")
    of.write(headermagic)
    
else:
    of = open(filename, "ab")

assumed_tps = -1
highest_with_data = 0
target_retry = 10
prevblockdata = None

allknown = {}
for trackno in range(168):
    known_sectors = {}
    highest_sector = -1
    
    retry = 0
    retrycount = target_retry
    while retry < retrycount:
        track_seek = trackno // 2
        track = trackno // 2
        side = trackno % 2
        clock = CW_TRACKINFO_CLOCK_14MHZ
        mode = CW_TRACKINFO_MODE_INDEX_STORE
        flags = 0
        
        if retry == 0:
            timeout = 230
        else:
            timeout = 500
        
        while True:
            sc.sendall(b"\x01" + struct.pack("<BBBBBII", track_seek, track, side, clock, mode, flags, timeout))

            blocksize = recv_all(sc, 4)
            blocksize, = struct.unpack("<I", blocksize)
            blockdata = recv_all(sc, blocksize)
            
            if prevblockdata == blockdata:
                print("Exact raw data repeated, assuming some catweasel error")
            else:
                prevblockdata = blockdata
                break
                
        trackheader = struct.pack("<BBBBI", trackmagic, trackno, clock, HEADER_FLAG_INDEX_STORED, blocksize)
        of.write(trackheader + blockdata)

        new_sectors = rawparser.try_parse_mfm(blockdata)
        for sector_header in new_sectors:
            cyl, side, sectorno, sz = sector_header
            if trackno != cyl * 2 + side:
                print("Sector on wrong track!", trackno, cyl * 2 + side, sectorno)
            else:
                highest_sector = max(highest_sector, sectorno)
                if sectorno not in known_sectors:
                    known_sectors[sectorno] = new_sectors[sector_header]
                else:
                    if known_sectors[sectorno] != new_sectors[sector_header]:
                        print("SECTOR MISMATCH", trackno, sector_header)
                    
        if assumed_tps < highest_sector:
            assumed_tps = highest_sector
            
        sectormap = ""
        if assumed_tps != -1:
            for i in range(assumed_tps):
                if i + 1 in known_sectors:
                    sectormap += "@ "
                else:
                    sectormap += ". "
                    
        print("Track %3d try %2d: %5x bytes, %2d/%2d sectors  %s" % (trackno, retry, blocksize, len(known_sectors), assumed_tps, sectormap))
        
        if len(known_sectors) == assumed_tps:
            break
                
        if len(known_sectors) == 0:
            if trackno >= 160:
                retrycount = min(2, target_retry)
        else:
            retrycount = target_retry
            
        retry += 1
    
    allknown[trackno] = known_sectors
    if len(known_sectors) > 0:
        highest_with_data = trackno

of.close()
    
badsectors = []
goodcount = 0
numtracks = highest_with_data + 1

of2 = open(filename + ".img", "wb")
for trackno in range(numtracks):
    for sectorno in range(1, assumed_tps + 1):
        if sectorno in allknown[trackno]:
            of2.write(allknown[trackno][sectorno])
            goodcount += 1
        else:
            of2.write(b"CWTOOLBADSECTOR!" * 32)
            badsectors.append((trackno, sectorno-1))
of2.close()

print("%3d (%3d) tracks read (sectors: good %4d  bad %4d)" % (numtracks, numtracks // 2, goodcount, len(badsectors)))
for trackno in range(numtracks):
    s = ""
    for trackno2, sectorno in badsectors:
        if trackno == trackno2:
            s += " %02d" % sectorno
            
    if s != "":
        print("track %3d: %s" % (trackno, s))
        
        