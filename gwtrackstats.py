import io, struct, sys, hashlib

drivestats_mfmdd = [-2] * 1024
width = 30
for i in range(288 - width, 288 + width):
    drivestats_mfmdd[i] = 1

for i in range(426 - width, 426 + width):
    drivestats_mfmdd[i] = 1

for i in range(564 - width, 564 + width):
    drivestats_mfmdd[i] = 1
    
f = open(sys.argv[1], "rb")
target = int(sys.argv[2])

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
        print("comment:", comment)
        
    elif datatype != b"\xca":
        raise Exception()
        
    else:
        trackno, indexsize, fluxsize = struct.unpack("<BII", f.read(9))
        f.read(indexsize)
        
        fluxdata = f.read(fluxsize)
        
        bio = io.BytesIO(fluxdata)
        fluxes = []
        while True:
            b = bio.read(2)
            if len(b) == 0:
                break
                
            flux = struct.unpack("<H", b)[0]
            if flux == 0xffff:
                flux = struct.unpack("<Q", bio.read(8))[0]
            fluxes.append(flux)

        fluxes2 = [min(x, 1023) for x in fluxes]
        
        #print("trackno", trackno, sum([drivestats_mfmdd[x] for x in fluxes2]))
        
        
        if target == trackno:
            bio = io.BytesIO(fluxdata)
            print("----------- track", trackno)
            stats = [0] * 0x80
            fluxes2 = [min(x // 6, 0x7f) for x in fluxes]
            for flux in fluxes2:
                stats[flux] += 1

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

