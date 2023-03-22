import struct, sys, hashlib

f = open(sys.argv[1], "rb")
target = int(sys.argv[2])

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
    
    if trackno == target:
        for n in trackdata:
            n = n & 0x7f
            dist1 = abs(n - 0x1b)
            dist2 = abs(n - 0x2a)
            dist3 = abs(n - 0x38)
            
            if dist1 <= dist2 and dist1 <= dist3:
                if dist1 >= 3:
                    print("%3d %3d" % (1, n - 0x1b))
            elif dist2 <= dist1 and dist2 <= dist3:
                if dist2 >= 3:
                    print("%3d %3d" % (2, n - 0x2a))
            else:
                if dist3 >= 3:
                    print("%3d %3d" % (3, n - 0x38))

        # largest = max(stats)
        # for y in range(19, -1, -1):
            # s = "| "
            # for x in range(0x80):
                # if stats[x] > (1 << y):
                    # s += "X"
                # else:
                    # s += " "
                    
            # print(s)
            
        # s1 = "  "
        # s2 = "  "
        # for x in range(0x80):
            # s1 += "%1x" % (x >> 4)
            # s2 += "%1x" % (x & 0xf)
            
        # print(s1)
        # print(s2)
        # print("")
        
f.close()

