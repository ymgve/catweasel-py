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

highest_sector = 8
highest_with_data = 0


clock = CW_TRACKINFO_CLOCK_14MHZ
target_retry = 3

splits = (0x22, 0x2f)


prevblockdata = None

td = rawparser.TrackDecoder()
td.setdebug(1)
tracktypecounts = {}

allknown = {}
tested_tracks = []
for trackno in range(0, 168, 1):
    known_sectors = {}
    
    retry = 0
    retrycount = target_retry
    while retry < retrycount:
        track_seek = trackno // 2
        track = trackno // 2
        side = trackno % 2
        mode = CW_TRACKINFO_MODE_INDEX_STORE
        flags = 0
        
        if retry == 0:
            timeout = 230
        else:
            if clock == CW_TRACKINFO_CLOCK_14MHZ:
                timeout = 560
        
        while True:
            sc.sendall(b"\x01" + struct.pack("<BBBBBII", track_seek, track, side, clock, mode, flags, timeout))

            while True:
                cmd = recv_all(sc, 1)
                
                if cmd == b"\x00":
                    msgsize = recv_all(sc, 4)
                    msgsize, = struct.unpack("<I", msgsize)
                    msg = recv_all(sc, msgsize)
                    print(repr(msg))
                    
                elif cmd == b"\x01":
                    blocksize = recv_all(sc, 4)
                    blocksize, = struct.unpack("<I", blocksize)
                    blockdata = recv_all(sc, blocksize)
                    
                    break
                    
                else:
                    raise Exception("Strange command", cmd)
            
            if prevblockdata == blockdata:
                print("Exact raw data repeated, assuming some catweasel error")
            else:
                prevblockdata = blockdata
                break

        trackheader = struct.pack("<BBBBI", trackmagic, trackno, clock, HEADER_FLAG_INDEX_STORED, blocksize)
        of.write(trackheader + blockdata)
                
        splits2txt = ""
        curr_status = {}
        for searchpass in range(2):
            if searchpass == 0:
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
                        
                splits2 = (loindex, hiindex)
                splits2txt = "splits %02x %02x" % splits2
                tracktype, new_sectors = td.parse_mfm(blockdata, trackno, splits2)
                
            elif searchpass == 1:
                tracktype, new_sectors = td.parse_mfm(blockdata, trackno, splits)
                
            if tracktype == "amiga":
                highest_sector = max(10, highest_sector)
                
            if len(new_sectors) > 0:
                highest_sector = max(highest_sector, max(new_sectors))
            
            if tracktype not in tracktypecounts:
                tracktypecounts[tracktype] = 0
            tracktypecounts[tracktype] += 1
                
            for sectorno in new_sectors:
                if sectorno not in known_sectors:
                    known_sectors[sectorno] = new_sectors[sectorno]
                else:
                    if known_sectors[sectorno] != new_sectors[sectorno]:
                        print("SECTOR MISMATCH", trackno, sectorno)

                if sectorno not in curr_status:
                    curr_status[sectorno] = searchpass
                    
            if len(known_sectors) == highest_sector + 1:
                break
                        
        sectormap = ""
        for i in range(highest_sector+1):
            if i in known_sectors:
                sectormap += "@ "
            else:
                sectormap += ". "
                    
        passmap = ""
        for i in range(highest_sector+1):
            if i in curr_status:
                passmap += str(curr_status[i] + 1) + " "
            else:
                passmap += ". "
                
        print("Track %3d try %2d: %5x bytes, %2d/%2d sectors  %s  track type %s %s %s" % (trackno, retry, blocksize, len(known_sectors), highest_sector + 1, sectormap, tracktype, passmap, splits2txt))
        
        if len(known_sectors) == highest_sector + 1:
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

    tested_tracks.append(trackno)
    
of.close()
    
badsectors = []
goodcount = 0
numtracks = highest_with_data + 1

of2 = open(filename + ".img", "wb")
for trackno in tested_tracks:
    if trackno <= highest_with_data:
        for sectorno in range(highest_sector + 1):
            if sectorno in allknown[trackno]:
                of2.write(allknown[trackno][sectorno])
                goodcount += 1
            else:
                of2.write(b"CWTOOLBADSECTOR!" * 32)
                badsectors.append((trackno, sectorno))
of2.close()

print("track type stats", tracktypecounts)
print("%3d (%3d) tracks read (sectors: good %4d  bad %4d)" % (numtracks, numtracks // 2, goodcount, len(badsectors)))
for trackno in range(numtracks):
    s = ""
    for trackno2, sectorno in badsectors:
        if trackno == trackno2:
            s += " %02d" % sectorno
            
    if s != "":
        print("track %3d: %s" % (trackno, s))
        
        