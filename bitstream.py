class Bitstream(object):
    def __init__(self, trackdata, splitlut):
        self.trackdata = [splitlut[x] for x in trackdata]
        self.index = 0
        self.pending = 0
        self.splitlut = splitlut
        self.last = None
        
        
    def get_bit(self):
        if self.pending == 0:
            try:
                self.pending = self.trackdata[self.index]
            except:
                return None
                
            self.index += 1
                
        self.last = self.pending & 1
        self.pending >>= 1
        
        return self.last
