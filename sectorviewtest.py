import struct, sys

from PIL import Image

# rows = []
# largest = 0
# longest = 0
# for line in open(sys.argv[1], "r"):
    # x = eval(line)
    # curr = 0
    # values = []
    # for c in x:
        # curr += c
        # values.append(curr)
        
    # rows.append(values)
    # largest = max(largest, curr)
    # print(curr)
    
# print(largest)

# width = 5000

# nblocks = largest // 10 // width + 1

# im = Image.new("RGB", (width, len(rows)*nblocks))
# for yy in range(len(rows)):
    # for c in rows[yy]:
        # c = c // 10
        # x = c % 5000
        # y = (c // 5000) * len(rows) + yy
        
        #im.putpixel((x, y), 0xffffff)
        
            
#im.save("_testtrack.png")


rows = []
longest = 0
for line in open(sys.argv[1], "r"):
    values = eval(line)
    rows.append([min(x, 1024) for x in values])
    longest = max(longest, len(values))
    
width = longest

im = Image.new("RGB", (width, 1024))
for row in rows:
    for x in range(len(row)):
        y = 1023 - row[x]
        im.putpixel((x, y), 0xfffffff)
        
im.save("_testtrack.png")