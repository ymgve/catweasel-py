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
        target_tracks = list(range(0, DRIVE_MAX_TRACKS, 1))

    if args.even:
        target_tracks = [x for x in target_tracks if (x % 2) == 0]
    elif args.odd:
        target_tracks = [x for x in target_tracks if (x % 2) == 1]
        
    if args.rev:
        target_tracks = target_tracks[::-1]

    target_tracks = [x for x in target_tracks if x < DRIVE_MAX_TRACKS]
    
    proc = gwrawparser.Processor(args, target_tracks)
    
    firstread = True
    for trackno in target_tracks:
        retry = 0
        retrycount = target_retry
        
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
            
            rt = gwrawparser.RawTrack(args, None, None, trackno, trackdata)
            
            proc.process_tracks([rt], gwrawparser.quick_scan_track, False)
            
            if args.nsectors != -1:
                sectortarget = args.nsectors
            else:
                sectortarget = proc.highest_sector + 1
                
            highest_local = -1
            for trackno2, sectorno in proc.known_sectors:
                if trackno == trackno2:
                    highest_local = max(highest_local, sectorno)
                    
            localtarget = max(highest_local + 1, sectortarget)
            
            sectormap = ""
            for sectorno in range(localtarget):
                if (trackno, sectorno) in proc.known_sectors:
                    sectormap += "@ "
                else:
                    sectormap += ". "
                        
            passmap = ""
            for sectorno in range(localtarget):
                if (trackno, sectorno) in rt.known_sectors:
                    passmap += "@ "
                else:
                    passmap += ". "

            sectorcount = 0
            tracktype = "none"
            for sectorno in range(localtarget):
                if (trackno, sectorno) in proc.known_sectors:
                    sectorcount += 1
                    
                    secs = list(proc.known_sectors[(trackno, sectorno)].values())
                    sec = secs[0][0]
                    if tracktype == "none":
                        tracktype = sec.sectortype
                    else:
                        if tracktype != sec.sectortype:
                            tracktype = "hybrid"
                
                    
            print("Track %3d try %2d: %6d fluxes, %2d/%2d sectors  %s  track type %-6s  %s  %d syncs" % (trackno, retry, len(trackdata), sectorcount, localtarget, sectormap, tracktype, passmap, len(rt.syncs)))
            
            if sectorcount >= localtarget:
                break
                    
            if sectorcount == 0:
                if trackno >= 160:
                    retrycount = min(2, target_retry)
            else:
                retrycount = target_retry
                
            retry += 1
            
    of.close()
    
    print(args.filename)
    
    proc.generate_output()
    # badsectors = []
    # badtracks = set()
    # goodcount = 0
    # numtracks = highest_with_data + 1

    # of2 = open(args.filename + ".img", "wb")
    # for trackno in tested_tracks:
        # if trackno <= highest_with_data:
            # for sectorno in range(highest_sector + 1):
                # if sectorno in allknown[trackno]:
                    # of2.write(allknown[trackno][sectorno])
                    # goodcount += 1
                # else:
                    # of2.write(b"CWTOOLBADSECTOR!" * 32)
                    # badsectors.append((trackno, sectorno))
                    # badtracks.add(trackno)
    # of2.close()

    # print(args.filename)

    # if "dos" in tracktypecounts and 0 in allknown and 0 in allknown[0]:
        # bootsector = allknown[0][0]
        
        # bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads = struct.unpack("<HBxxxxxHxxxHH", bootsector[0x0b:0x1c])
            
        # print("    BPB: %d bytes/sector, %d sectors per cluster, %d total sectors, %d sectors per track, %d heads" % (bpb_bps, bpb_spc, bpb_tot, bpb_spt, bpb_heads))
        # if bpb_spt != 0 and (bpb_tot % bpb_spt) == 0:
            # print("    Total tracks according to BPB: %d" % (bpb_tot // bpb_spt,))
            

    # print("    track type stats", tracktypecounts)
    # print("    %3d (%3d) tracks read (sectors: good %4d  bad %4d)" % (numtracks, numtracks // 2, goodcount, len(badsectors)))
    # for trackno in range(numtracks):
        # s = ""
        # for trackno2, sectorno in badsectors:
            # if trackno == trackno2:
                # s += " %02d" % sectorno
                
        # if s != "":
            # print("    track %3d: %s" % (trackno, s))
            
    # print("bad tracks", ",".join([str(x) for x in sorted(badtracks)]))
                

def main(argv):
    parser = util.ArgumentParser()
    parser.add_argument("--drive", type=util.drive_letter, default='A', help="drive to read")
    parser.add_argument("filename")

    parser.add_argument("-t", "--tracks")
    parser.add_argument("--rev", action="store_true")
    parser.add_argument("--odd", action="store_true")
    parser.add_argument("--even", action="store_true")

    parser.add_argument("-r", "--retries", type=int, default=10)
    parser.add_argument("--nsectors", type=int, default=-1)
    parser.add_argument("--hd", action="store_true")
    parser.add_argument("--rpm360", action="store_true")
    parser.add_argument("--useht", action="store_true")
    parser.add_argument("--selected")
    
    args = parser.parse_args()

    if not args.filename.endswith(".graw"):
        raise Exception("wrong filename extension?")
        
        
    usb = util.usb_open(None)

    util.with_drive_selected(readtest, usb, args)

if __name__ == "__main__":
    main(sys.argv)
