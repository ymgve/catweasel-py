import struct, sys

from PIL import Image

def check(n):
    if n >= 0x19 and n <= 0x1d:
        return True
    elif n >= 0x28 and n <= 0x2c:
         return True
    elif n >= 0x36 and n <= 0x3a:
         return True
         
    return False
    
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
        if not synced and (prev & 0x80) != 0x80 and (n & 0x80) != 0:
            synced = True
            
            row = []
            
        if synced:
            row.append(n)
                
        prev = n
        
    rows.append(row)
    
    print("rowlen", len(row))

if len(rows) == 0:
    exit()
    
largest = 0
for row in rows:
    largest = max(largest, len(row))
    
width = 3650

nblocks = largest // width + 1

im = Image.new("RGB", (width, len(rows)*nblocks))
for yy in range(len(rows)):
    for xx in range(len(rows[yy])):
        x = xx % width
        y = yy + len(rows) * (xx // width)
        c = 0x020202 * (255 - (rows[yy][xx] & 0x7f) * 2)
        if rows[yy][xx] & 0x80 == 0x80:
            c &= 0xffff00
        if not check(rows[yy][xx] & 0x7f):
            c &= 0xff00ff
            
        im.putpixel((x, y), c)
        
            
im.save("_testtrack.png")

