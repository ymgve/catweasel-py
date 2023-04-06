import copy, struct, sys, random, time, hashlib

sys.setrecursionlimit(15000)

class BitstreamRandom(object):
    def __init__(self, trackdata):
        self.trackdata = trackdata
        self.index = 0
        self.pending = 0
        self.last = None
        
        
    def get_bit(self):
        if self.pending == 0:
            try:
                n = self.trackdata[self.index] & 0x7f
            except:
                return None
                
            if n <= 0x1f:
                self.pending = 2

            #  1b 1c 1d 1e 1f 20 21 22 23 24 25 26 27 28 29 2a
            #  0  1  2  3  4  5  6  7  7  6  5  4  3  2  1  0

            elif n == 0x20:
                c = random.randrange(100)
                if c < 99:
                    self.pending = 2
                else:
                    self.pending = 4
            elif n == 0x21:
                c = random.randrange(100)
                if c < 90:
                    self.pending = 2
                else:
                    self.pending = 4
            elif n == 0x22:
                c = random.randrange(100)
                if c < 50:
                    self.pending = 2
                else:
                    self.pending = 4
            elif n == 0x23:
                c = random.randrange(100)
                if c < 50:
                    self.pending = 2
                else:
                    self.pending = 4
            elif n == 0x24:
                c = random.randrange(100)
                if c < 10:
                    self.pending = 2
                else:
                    self.pending = 4
            elif n == 0x25:
                c = random.randrange(100)
                if c < 1:
                    self.pending = 2
                else:
                    self.pending = 4
                    
            # 2b 2c 2d 2e 2f 30 31 32 33 34 35 36 37 38
            # 0  1  2  3  4  5  6  6  5  4  3  2  1  0
            elif n >= 0x26 and n <= 0x2e:
                self.pending = 4
            elif n == 0x2f:
                c = random.randrange(100)
                if c < 99:
                    self.pending = 4
                else:
                    self.pending = 8
            elif n == 0x30:
                c = random.randrange(100)
                if c < 90:
                    self.pending = 4
                else:
                    self.pending = 8
            elif n == 0x31:
                c = random.randrange(100)
                if c < 50:
                    self.pending = 4
                else:
                    self.pending = 8
            elif n == 0x32:
                c = random.randrange(100)
                if c < 50:
                    self.pending = 4
                else:
                    self.pending = 8
            elif n == 0x33:
                c = random.randrange(100)
                if c < 10:
                    self.pending = 4
                else:
                    self.pending = 8
            elif n == 0x34:
                c = random.randrange(100)
                if c < 1:
                    self.pending = 4
                else:
                    self.pending = 8
            else:
                self.pending = 8
                
            self.index += 1
                
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last


class BitstreamTree(object):
    def __init__(self, trackdata):
        self.trackdata = trackdata
        self.index = 0
        self.pending = 0
        self.last = None
        self.lut = [0] * 128
        dist = 5
        
        split1lo = 0x1b - dist
        split1hi = 0x1b + dist + 1
        
        split2lo = 0x2a - dist
        split2hi = 0x2a + dist + 1
        
        split3lo = 0x38 - dist
        split3hi = 0x38 + dist + 1

        splits = [0, split1lo, split1hi, split2lo, split2hi, split3lo, split3hi, 0x80]
        #           1         2         3         4         5         6         7
        
        for i in range(len(splits)-1):
            for j in range(splits[i], splits[i+1]):
                self.lut[j] = i + 1
                
        assert 0 not in self.lut
        
        self.lut = tuple(self.lut)

    def prepare_bit(self):
        if self.pending == 0:
            try:
                n = self.trackdata[self.index] & 0x7f
            except:
                return None

            self.index += 1
               
            t = self.lut[n]
            if t == 1 or t == 2:
                self.pending = 2
                return (self, )
            elif t == 3:
                #print("lo split at", self.index)
                self.pending = 2
                other = copy.copy(self)
                other.pending = 4
                return (self, other)
            elif t == 4:
                self.pending = 4
                return (self, )
            elif t == 5:
                #print("hi split at", self.index)
                self.pending = 4
                other = copy.copy(self)
                other.pending = 8
                return (self, other)
            elif t == 6:
                self.pending = 8
                return (self, )
            else:
                if n == 0x7f:
                    return None
                    
                self.pending = 8
                return (self, )
                
        return (self,)

    def get_bit(self):
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last

def getbits(bs, results, rawres, sofar, remaining):
    if remaining == 0:
        results.append(rawres)
    else:
        last = bs.last
        a = bs.get_bit()
        rawres = (rawres << 1) | a
        
        if sofar >= 3 and remaining % 2 == 1:
            if rawres & 7 == 0:
                #print("dsdsds", remaining, hex(rawres))
                return
        
        bss = bs.prepare_bit()
        if bss == None:
            return
            
        for bs2 in bss:
            getbits(bs2, results, rawres, sofar + 1, remaining - 1)


f = open("_segments_to_test.bin", "rb")

segments = []
maxsize = 0
while True:
    data = f.read(16)
    if len(data) == 0:
        break
        
    trackno, vtrackno, sectorno, datasize = struct.unpack("<IIII", data)
    data = f.read(datasize)
    
    if trackno != int(sys.argv[1]):
        continue
    
    if sectorno != int(sys.argv[2]):
        continue
        
    if 0x7f in data or 0xff in data:
        continue
        
    segments.append(data)
    maxsize = max(maxsize, datasize)
    #print(trackno, sectorno)
    #print(len(data), data[0:100].hex())
    
    # stats = [0] * 128
    # for n in data:
        # stats[n & 0x7f] += 1
        
    # s = ""
    # for i in range(0x80):
        # s += "%02x %5d " % (i, stats[i])
        
        # if i & 0xf == 0xf:
            # print(s)
            # s = ""
            
    # print("dsds", s)
    
    # for i in range(len(data)):
        # n = data[i] & 0x7f
        # dist1 = abs(n - 0x1b)
        # dist2 = abs(n - 0x2a)
        # dist3 = abs(n - 0x38)
        
        # if dist1 <= dist2 and dist1 <= dist3:
            # if dist1 >= 4:
                # print("%10d %3d %3x %3x" % (i, 1, n, n - 0x1b))
        # elif dist2 <= dist1 and dist2 <= dist3:
            # if dist2 >= 4:
                # print("%10d %3d %3x %3x" % (i, 2, n, n - 0x2a))
        # else:
            # if dist3 >= 4:
                # print("%10d %3d %3x %3x" % (i, 3, n, n - 0x38))    
    
for i in range(maxsize):
    s = ""
    lo = 99999
    hi = 0
    for segment in segments[-10:]:
        if i < len(segment):
            s += "%02x " % (segment[i] & 0x7f)
            lo = min(lo, (segment[i] & 0x7f))
            hi = max(hi, (segment[i] & 0x7f))
            n = (hi + lo) // 2
            
            dist1 = abs(n - 0x1b)
            dist2 = abs(n - 0x2a)
            dist3 = abs(n - 0x38)
            
            if dist1 <= dist2 and dist1 <= dist3:
                diff = n - 0x1b
            elif dist2 <= dist1 and dist2 <= dist3:
                diff = n - 0x2a
            else:
                diff = n - 0x38
                
        else:
            s += "   "
        
    print("%5d %02x %02x %3d %3d: %s" % (i, lo, hi, hi-lo, diff, s))
    
exit()
    
    
    
lastprint = time.time()

for segment in segments[::-1]:
    print("testing segment")
    bs = BitstreamTree(segment)
    bss = bs.prepare_bit()
    if len(bss) != 1:
        raise Exception("DSADSD")
    
    active_cands = []
    active_cands.append((bss[0], 0))
    
    for i in range(32 * 12 + 32 * 258):
        active_cands2 = []
        for bs, res in active_cands:
            a = bs.get_bit()
            res = (res << 1) | a
            
            if i >= 3 and i % 2 == 1:
                if res & 7 == 0:
                    continue
                    
            bss = bs.prepare_bit()
            if bss != None:
                for bs2 in bss:
                    active_cands2.append((bs2, res))
                    
        active_cands = active_cands2
        
        if time.time() - lastprint >= 1:
            print("size of active cands", len(active_cands), "nbits", i)
            lastprint = time.time()
            
        if len(active_cands) >= 1000000:
            active_cands = []
            break
                 
    print("remaining active cands", len(active_cands))
    for idx in range(len(active_cands)):
        _, ress = active_cands[idx]
        words = []
        for i in range(12 + 258):
            words.append(ress & 0xffffffff)
            ress >>= 32
            
        words = words[::-1]
        
        csum = 0
        for i in range(12):
            csum ^= words[i]
            
        csum &= 0x55555555
        if csum != 0:
            #print("BAD headercsum", idx, hex(csum))
            continue
        
        csum = 0
        for i in range(258):
            csum ^= words[12+i]
            
        csum &= 0x55555555
        if csum != 0:
            #print("BAD datacsum", idx, hex(csum))
            continue
            
        print("GOOD")

        data = bytearray()
        for i in range(128):
            dataword = ((words[i+12+2] & 0x55555555) << 1) | (words[i+12+130] & 0x55555555)
            data += struct.pack(">I", dataword)
            
        data = bytes(data)
        print(data.hex())
        print("hash", hashlib.sha256(data).hexdigest())


exit()
def getamigaword(bs):
    rawres = 0
    missing_syncs = 0
    for i in range(16):
        last = bs.last
        a = bs.get_bit()
        b = bs.get_bit()
        if a == None or b == None:
            return None, missing_syncs
            
        if b == 0 and last == a:
            missing_syncs += 1
            
        rawres = (rawres << 2) | (a << 1) | b
        
    return rawres, missing_syncs
    
print("num segments", len(segments))
if len(segments) >= 1:
    while True:
        for segment in segments[-2:]:
            bs = BitstreamRandom(segment)
            
            words = []
            ok = True
            for i in range(12 + 258):
                word, missing_syncs = getamigaword(bs)
                if missing_syncs != 0:
                    ok = False
                    break
                    
                words.append(word)
                
            if not ok:
                continue
                
            print("no missing syncs")
            print(words)
            
            csum = 0
            for i in range(12):
                csum ^= words[i]
                
            csum &= 0x55555555
            if csum != 0:
                print("BAD headercsum", hex(csum))
                continue
            
            csum = 0
            for i in range(258):
                csum ^= words[12+i]
                
            csum &= 0x55555555
            if csum != 0:
                print("BAD datacsum", hex(csum))
                continue
                
            print("GOOD", idx)
            
        
exit()
for segment in segments[::-1]:
    bs = BitstreamTree(segment)

    bss = bs.prepare_bit()
    if len(bss) != 1:
        raise Exception("DSADSD")
        
    res = []

    getbits(bss[0], res, 0, 0, 32 * 12 + 32 * 258)

    print("results", len(res))

    for idx in range(len(res)):
        ress = res[idx]
        words = []
        for i in range(12 + 258):
            words.append(ress & 0xffffffff)
            ress >>= 32
            
        words = words[::-1]
        
        csum = 0
        for i in range(12):
            csum ^= words[i]
            
        csum &= 0x55555555
        if csum != 0:
            #print("BAD headercsum", idx, hex(csum))
            continue
        
        csum = 0
        for i in range(258):
            csum ^= words[12+i]
            
        csum &= 0x55555555
        if csum != 0:
            #print("BAD datacsum", idx, hex(csum))
            continue
            
        
        #exit()
            
        
    
exit()

    
    
    