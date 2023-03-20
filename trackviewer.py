import struct, sys

from PIL import Image

f = open(sys.argv[1], "rb")

target_track = int(sys.argv[2])

magic = f.read(32)
if magic != b"cwtool raw data 3".ljust(32, b"\x00"):
    raise Exception("bad magic")
    
rows = []
while True:
    trackoffset = f.tell()
    trackheader = f.read(8)
    if len(trackheader) == 0:
        break
        
    trackmagic, trackno, clock, flags, tsize = struct.unpack("<BBBBI", trackheader)
    if trackmagic != 0xca:
        raise Exception()
        
    trackdata = f.read(tsize)
    
    if trackno != target_track:
        continue
        
    prev = 0
    row = None
    synced = False
    pos = 0
    for i in range(len(trackdata)):
        n = trackdata[i]
        if (prev & 0x80) == 0x80 and (n & 0x80) == 0:
            synced = True
            
            if row != None:
                rows.append(row)
                
            row = []
            pos = 0
            
        else:
            if synced:
                adjusted = n & 0x7f
                if adjusted >= 0x19 and adjusted <= 0x1d:
                    adjusted = 0x1b
                elif adjusted >= 0x28 and adjusted <= 0x2c:
                    adjusted = 0x2a
                elif adjusted >= 0x36 and adjusted <= 0x3a:
                    adjusted = 0x38
                    
                pos += adjusted
                row.append(pos)
                
        prev = n
        
    rows.append(row)
    
largest = 0
for row in rows:
    largest = max(largest, max(row))
    #print("rowlen", len(row))

print(len(rows))    
print(largest)

if len(rows) == 0:
    exit()
    
#rows.sort()

im = Image.new("RGB", (5000, len(rows)))
for y in range(len(rows)):
    for x in rows[y]:
        if x < 5000:
            im.putpixel((x, y), 0xffffff)
            
im.save("_testtrack.png")

