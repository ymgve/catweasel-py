import array, fcntl, struct, ctypes, os, socket, time

_IOC_WRITE = 1
_IOC_READ = 2

iodir = _IOC_WRITE
iotype = 0xca
ionr = 2
iosize = 40

CW_IOC_READ = (iodir << 30) | (iotype << 8) | ionr | (iosize << 16)

CW_STRUCT_VERSION = 2

BUFFERSIZE = 0x20000

buff = ctypes.create_string_buffer(BUFFERSIZE)

def recv_all(sc, size):
    res = b""
    while len(res) < size:
        rec = sc.recv(size - len(res))
        if len(rec) == 0:
            raise Exception("DASDSADS")
            
        res += rec
        
    return res
        
iof = os.open("/dev/cw0raw0", os.O_RDWR)

sc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sc.bind(("", 12322))
sc.listen(1)

while True:
    cs, addr = sc.accept()
    print('Connected by', addr)
    while True:
        try:
            cmd = recv_all(cs, 1)
        except Exception as e:
            print("Connection error:", e)
            cs.close()
            break
            
        
        if cmd == b"\x00":
            iof.close()
            cs.close()
            sc.close()
            exit()
            
        elif cmd == b"\x01":
            try:
                data = recv_all(cs, 13)
            except Exception as e:
                print("Connection error:", e)
                cs.close()
                break
                
            track_seek, track, side, clock, mode, flags, timeout = struct.unpack("<BBBBBII", data)
                    
            arr = struct.pack("<IBBBBBxxxIIxxxxQIxxxx", CW_STRUCT_VERSION, track_seek, track, side, clock, mode, flags, timeout, ctypes.addressof(buff), BUFFERSIZE)

            # gotta pass a bytearray to get the proper return value
            while True:
                try:
                    res = fcntl.ioctl(iof, CW_IOC_READ, bytearray(arr))
                    break
                except Exception as e:
                    print("IO call failed, trying again", e)
                    msg = b"IO call failed, trying again"
                    cs.sendall(b"\x00" + struct.pack("<I", len(msg)) + msg)
                    iof.close()
                    
                    time.sleep(1)
                    iof = os.open("/dev/cw0raw0", os.O_RDWR)
                
            if res < 0 or res > BUFFERSIZE:
                raise Exception("BAD RETURN CODE %d" % res)
                
            try:
                cs.sendall(b"\x01" + struct.pack("<I", res) + buff[0:res])
            except Exception as e:
                print("Connection error:", e)
                cs.close()
                break
            
                
                
                
                        
# iodir = _IOC_READ
# iotype = 0xca
# ionr = 0
# iosize = 32

# CW_IOC_GFLPARM = (iodir << 30) | (iotype << 8) | ionr | (iosize << 16)

# arr = bytearray(32)
# struct.pack_into("<I", arr, 0, 2)


# iof = os.open("/dev/cw0raw0", os.O_RDWR)
# fcntl.ioctl(iof, CW_IOC_GFLPARM, arr, 1)

# params = struct.unpack_from("<IIIIBBBBIII", arr)
# print(params)
# print(hex(params[3]))
# print(hex(params[8]))

# iodir = _IOC_WRITE
# iotype = 0xca
# ionr = 1
# iosize = 32

# CW_IOC_SFLPARM = (iodir << 30) | (iotype << 8) | ionr | (iosize << 16)
# fcntl.ioctl(iof, CW_IOC_SFLPARM, arr, True)


# CW_TRACKINFO_CLOCK_14MHZ = 0
# CW_TRACKINFO_CLOCK_28MHZ = 1
# CW_TRACKINFO_CLOCK_56MHZ = 2

# CW_TRACKINFO_MODE_NORMAL = 0
# CW_TRACKINFO_MODE_INDEX_WAIT = 1
# CW_TRACKINFO_MODE_INDEX_STORE = 2

# CW_DEFAULT_TIMEOUT = 500

# track_seek = 0
# track = 0
# side = 1


#define _IOC(dir,type,nr,size)			\
	# ((unsigned int)				\
	 # (((dir)  << _IOC_DIRSHIFT) |		\
	  # ((type) << _IOC_TYPESHIFT) |		\
	  # ((nr)   << _IOC_NRSHIFT) |		\
	  # ((size) << _IOC_SIZESHIFT)))
      
      
    # {
	# cw_count_t			version;        cw_s32_t        2
	# cw_msecs_t			settle_time;    cw_s32_t        CW_DEFAULT_SETTLE_TIME		25
	# cw_msecs_t			step_time;      cw_s32_t        CW_DEFAULT_STEP_TIME		6
	# cw_psecs_t			wpulse_length;  cw_s32_t        10*CW_WPULSE_LENGTH_MULTIPLIER	35310		/* 35.31 ns = 35310 ps */
	# cw_snum_t			nr_tracks;          cw_u8_t
	# cw_snum_t			nr_sides;           cw_u8_t
	# cw_snum_t			nr_clocks;          cw_u8_t
	# cw_snum_t			nr_modes;           cw_u8_t
	# cw_size_t			max_size;           cw_s32_t
	# cw_count_t			rpm;            cw_s32_t
	# cw_flag_t			flags;              cw_u32_t
	# };
    
    
# struct cw_trackinfo
	# {
	# cw_count_t			version;        cw_s32_t
	# cw_snum_t			track_seek;         cw_u8_t
	# cw_snum_t			track;              cw_u8_t
	# cw_snum_t			side;               cw_u8_t
	# cw_snum_t			clock;              cw_u8_t
	# cw_snum_t			mode;               cw_u8_t
	# cw_snum_t			reserved[3];        cw_u8_t * 3    
	# cw_flag_t			flags;              cw_u32_t
	# cw_msecs_t			timeout;        cw_s32_t
	# cw_raw_t			*data;              64bit pointer
	# cw_size_t			size;               cw_s32_t
	# };
    
    
    