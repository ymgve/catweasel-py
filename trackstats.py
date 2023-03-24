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
    
    #if target == -1 or trackno == target:
    if trackno % 2 == 0:
        print("----------- track", trackno)
        stats = [0] * 0x80
        for c in trackdata:
            stats[c & 0x7f] += 1

        largest = max(stats)
        for y in range(19, -1, -1):
            s = "| "
            for x in range(0x80):
                if stats[x] > (1 << y):
                    if x & 1:
                        s += "X"
                    else:
                        s += "+"
                else:
                    s += " "
                    
            print(s)
            
        s1 = "  "
        s2 = "  "
        for x in range(0x80):
            s1 += "%1x" % (x >> 4)
            s2 += "%1x" % (x & 0xf)
            
        print(s1)
        print(s2)
        print("")
        
f.close()

