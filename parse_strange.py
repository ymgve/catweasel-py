import sys, struct

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
    
    if trackno % 2 == 1:
        continue
    
    print("-----")
    bits = ""
    for n in trackdata:
        if (n & 0x7f) < 0x27:
            bits += "1"
        else:
            bits += "0"
          
    for i in range(0, len(bits), 128):
        print(bits[i:i+128])
    
    # for part in bits.split("1001010111101110101111011101110010101001010111111100011100111111101111011101110111001111000000"):
        # print(trackno, len(part), part[0:100])
    #exit()