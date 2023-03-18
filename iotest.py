import array, fcntl, struct, ctypes, os


#define _IOR(type,nr,size)	_IOC(_IOC_READ,(type),(nr),sizeof(size))


_IOC_WRITE = 1
_IOC_READ = 2

iodir = _IOC_READ
iotype = 0xca
ionr = 0
iosize = 32

CW_IOC_GFLPARM = (iodir << 30) | (iotype << 8) | ionr | (iosize << 16)

arr = bytearray(32)
struct.pack_into("<I", arr, 0, 2)


iof = os.open("/dev/cw0raw0", os.O_RDWR)
fcntl.ioctl(iof, CW_IOC_GFLPARM, arr, 1)

params = struct.unpack_from("<IIIIBBBBIII", arr)
print(params)
print(hex(params[3]))
print(hex(params[8]))

iodir = _IOC_WRITE
iotype = 0xca
ionr = 1
iosize = 32

CW_IOC_SFLPARM = (iodir << 30) | (iotype << 8) | ionr | (iosize << 16)
fcntl.ioctl(iof, CW_IOC_SFLPARM, arr, True)

iodir = _IOC_WRITE
iotype = 0xca
ionr = 2
iosize = 40

CW_IOC_READ = (iodir << 30) | (iotype << 8) | ionr | (iosize << 16)

CW_STRUCT_VERSION = 2

CW_TRACKINFO_CLOCK_14MHZ = 0
CW_TRACKINFO_CLOCK_28MHZ = 1
CW_TRACKINFO_CLOCK_56MHZ = 2

CW_TRACKINFO_MODE_NORMAL = 0
CW_TRACKINFO_MODE_INDEX_WAIT = 1
CW_TRACKINFO_MODE_INDEX_STORE = 2

CW_DEFAULT_TIMEOUT = 500

track_seek = 0
track = 0
side = 1

for i in range(10):
    buff = ctypes.create_string_buffer(0x20000)
    print(type(buff))
    flags = 0
    arr = struct.pack("<IBBBBBxxxIIxxxxQIxxxx", CW_STRUCT_VERSION, track_seek, track, side, CW_TRACKINFO_CLOCK_14MHZ, CW_TRACKINFO_MODE_INDEX_WAIT, flags, 500, ctypes.addressof(buff), 0x20000)

    # gotta pass a bytearray to get the proper return value
    res = fcntl.ioctl(iof, CW_IOC_READ, bytearray(arr))
    print(hex(res), repr(buff[0:100]))


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
    
    
    