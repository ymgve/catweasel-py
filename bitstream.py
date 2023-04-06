class Bitstream(object):
    def __init__(self, trackdata, splitlut, use_skew=False):
        self.trackdata = trackdata
        self.index = 0
        self.pending = 0
        self.splitlut = splitlut
        self.last = None
        self.skew = 0
        self.use_skew = use_skew
        
        
    def get_bit(self):
        if self.pending == 0:
            try:
                t = self.trackdata[self.index]
            except:
                return None

            n = (t & 0x7f) + self.skew
            if n < 0:
                n = 0
            if n > 0x7f:
                n = 0x7f
                
            self.pending, self.skew = self.splitlut[n]
            
            if not self.use_skew:
                self.skew = 0
                
            self.index += 1
                
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last
