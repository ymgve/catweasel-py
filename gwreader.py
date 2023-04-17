import os, struct, sys, time

from greaseweazle.tools import util
from greaseweazle import usb as USB

from current_drive_config import *

import gwrawparser

def readtest(usb, args):
    if not os.path.isfile(args.filename):
        of = open(args.filename, "wb")
        
        # yet another invented file format!
        of.write(b"gwreader raw data".ljust(32, b"\x00"))
        
    else:
        of = open(args.filename, "ab")

    comment = "Disk dump started %s with drive %s" % (time.ctime(), CURRENT_DRIVE)
    comment = comment.encode("utf8")
    of.write(b"\x00" + struct.pack("<I", len(comment)) + comment)

    highest_sector = args.nsectors - 1
    highest_with_data = 0

    target_retry = args.retries

    tracktypecounts = {}

    allknown = {}
    tested_tracks = []

    if args.tracks:
        if "-" in args.tracks:
            start, end = args.tracks.split("-")
            target_tracks = list(range(int(start), int(end)+1))
            
        else:
            target_tracks = [int(x) for x in args.tracks.split(",")]
            
    else:
        if args.even:
            target_tracks = list(range(0, 168, 2))
        elif args.odd:
            target_tracks = list(range(1, 168, 2))
        else:
            target_tracks = list(range(0, 168, 1))
            
    if args.rev:
        target_tracks = target_tracks[::-1]

    firstread = True
    for trackno in target_tracks:
        known_sectors = {}
        
        retry = 0
        retrycount = target_retry
        current_highest = 0
        
        while retry < retrycount:
            if retry == 0:
                ticks = int(14400000 * 1.25)
            else:
                ticks = int(14400000 * 2.50)
                
            usb.seek(trackno // 2, trackno % 2)
            
            if firstread:
                time.sleep(0.25)
                firstread = False
                
            flux = usb.read_track(revs=0, ticks=ticks)

            indexes = bytearray()
            for index in flux.index_list:
                indexes += struct.pack("<Q", index)
            
            fluxes = bytearray()
            for f in flux.list:
                if f >= 0xffff:
                    fluxes += b"\xff\xff" + struct.pack("<Q", f)
                else:
                    fluxes += struct.pack("<H", f)
            
            of.write(b"\xca" + struct.pack("<BII", trackno, len(indexes), len(fluxes)) + indexes + fluxes)
                    
            # clamp to make handling easier
            trackdata = [min(x, 1023) for x in flux.list]
            
            splits2txt = ""
            curr_status = {}
            
            if args.hd:
                tracktype, new_sectors, synccount = gwrawparser.quick_scan_hd_track(trackdata)
            else:
                tracktype, new_sectors, synccount = gwrawparser.quick_scan_track(trackdata)
            
            if tracktype == "amiga" and len(new_sectors) > 0:
                highest_sector = max(10, highest_sector)
                
            if tracktype not in tracktypecounts:
                tracktypecounts[tracktype] = 0
            tracktypecounts[tracktype] += 1
                
            for ts in new_sectors:
                htrackno, sectorno = ts
                if htrackno != trackno:
                    print("sector on wrong track, claims %d but should be %d" % (htrackno, trackno))
                else:
                    if sectorno not in known_sectors:
                        known_sectors[sectorno] = new_sectors[ts]
                    else:
                        if known_sectors[sectorno] != new_sectors[ts]:
                            print("SECTOR MISMATCH", sectorno)

                    if sectorno not in curr_status:
                        curr_status[sectorno] = 0
                        
                    if trackno < 160:
                        highest_sector = max(highest_sector, sectorno)
                        
                    current_highest = max(current_highest, sectorno)
                    
            sectortarget = max(highest_sector, current_highest) + 1
            sectormap = ""
            for i in range(sectortarget):
                if i in known_sectors:
                    sectormap += "@ "
                else:
                    sectormap += ". "
                        
            passmap = ""
            for i in range(sectortarget):
                if i in curr_status:
                    passmap += str(curr_status[i] + 1) + " "
                else:
                    passmap += ". "
                    
            print("Track %3d try %2d: %6d fluxes, %2d/%2d sectors  %s  track type %s %s  %d syncs" % (trackno, retry, len(trackdata), len(known_sectors), highest_sector + 1, sectormap, tracktype, passmap, synccount))
            
            if len(known_sectors) >= sectortarget:
                break
                    
            if len(known_sectors) == 0:
                if trackno >= 160:
                    retrycount = min(2, target_retry)
            else:
                retrycount = target_retry
                
            retry += 1
            
        allknown[trackno] = known_sectors
        if len(known_sectors) > 0:
            highest_with_data = max(trackno, highest_with_data)

        tested_tracks.append(trackno)
            
    of.close()
    
    badsectors = []
    badtracks = set()
    goodcount = 0
    numtracks = highest_with_data + 1

    of2 = open(args.filename + ".img", "wb")
    for trackno in tested_tracks:
        if trackno <= highest_with_data:
            for sectorno in range(highest_sector + 1):
                if sectorno in allknown[trackno]:
                    of2.write(allknown[trackno][sectorno])
                    goodcount += 1
                else:
                    of2.write(b"CWTOOLBADSECTOR!" * 32)
                    badsectors.append((trackno, sectorno))
                    badtracks.add(trackno)
    of2.close()

    print(args.filename)

    if "dos" in tracktypecounts and 0 in allknown and 0 in allknown[0]:
        bootsector = allknown[0][0]
        
        bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads = struct.unpack("<HBxxxxxHxxxHH", bootsector[0x0b:0x1c])
            
        print("    BPB: %d bytes/sector, %d sectors per cluster, %d total sectors, %d sectors per track, %d heads" % (bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads))
        if bpb_spt != 0 and (bpb_tot % bpb_spt) == 0:
            print("    Total tracks according to BPB: %d" % (bpb_tot // bpb_spt,))
            

    print("    track type stats", tracktypecounts)
    print("    %3d (%3d) tracks read (sectors: good %4d  bad %4d)" % (numtracks, numtracks // 2, goodcount, len(badsectors)))
    for trackno in range(numtracks):
        s = ""
        for trackno2, sectorno in badsectors:
            if trackno == trackno2:
                s += " %02d" % sectorno
                
        if s != "":
            print("    track %3d: %s" % (trackno, s))
            
    print("bad tracks", ",".join([str(x) for x in sorted(badtracks)]))
                

def main(argv):
    parser = util.ArgumentParser()
    parser.add_argument("--drive", type=util.drive_letter, default='A', help="drive to read")
    parser.add_argument("filename")

    parser.add_argument("-t", "--tracks")
    parser.add_argument("--rev", action="store_true")
    parser.add_argument("--odd", action="store_true")
    parser.add_argument("--even", action="store_true")

    parser.add_argument("-r", "--retries", type=int, default=10)
    parser.add_argument("--nsectors", type=int, default=1)
    parser.add_argument("--hd", action="store_true")
    
    args = parser.parse_args()

    if ".graw" not in args.filename:
        raise Exception("wrong filename extension?")
        
        
    usb = util.usb_open(None)

    util.with_drive_selected(readtest, usb, args)

if __name__ == "__main__":
    main(sys.argv)
