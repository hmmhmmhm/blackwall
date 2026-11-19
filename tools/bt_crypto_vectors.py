"""One AES-128 block using macOS CommonCrypto; explicit HCI byte order."""
import ctypes
import sys


def aes128_be(key, plaintext):
    if len(key)!=16 or len(plaintext)!=16:
        raise ValueError('AES-128 requires exactly 16-byte key and plaintext')
    if sys.platform!='darwin':
        raise RuntimeError('This research adapter requires macOS CommonCrypto')
    library=ctypes.CDLL('/usr/lib/system/libcommonCrypto.dylib')
    function=library.CCCrypt
    function.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,
        ctypes.c_size_t,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,
        ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    function.restype=ctypes.c_int32
    key_buffer=ctypes.create_string_buffer(key,16)
    data_buffer=ctypes.create_string_buffer(plaintext,16)
    output=ctypes.create_string_buffer(16);written=ctypes.c_size_t()
    # kCCEncrypt=0, kCCAlgorithmAES=0, kCCOptionECBMode=2; no padding.
    status=function(0,0,2,key_buffer,16,None,data_buffer,16,output,16,ctypes.byref(written))
    if status!=0 or written.value!=16:
        raise RuntimeError('CommonCrypto AES failed: status '+str(status))
    return output.raw


def hci_encrypt(key_le, plaintext_le):
    return aes128_be(key_le[::-1],plaintext_le[::-1])[::-1]


def cmac_blocks_be(key, message):
    """Research trace of CMAC AES inputs/results; underlying AES is CommonCrypto."""
    zero=bytes(16);subkey=aes128_be(key,zero);trace=[(zero,subkey)]
    def doubled(value):
        number=int.from_bytes(value,'big')
        return (((number<<1)&((1<<128)-1)) ^ (0x87 if number>>127 else 0)).to_bytes(16,'big')
    first=doubled(subkey);second=doubled(first)
    complete=bool(message) and len(message)%16==0
    count=max(1,(len(message)+15)//16)
    last=message[(count-1)*16:]
    if not complete:last=last+b'\x80'+bytes(15-len(last))
    last=bytes(a^b for a,b in zip(last,first if complete else second))
    previous=zero
    for index in range(count):
        block=last if index==count-1 else message[index*16:(index+1)*16]
        prepared=bytes(a^b for a,b in zip(previous,block))
        previous=aes128_be(key,prepared);trace.append((prepared,previous))
    return trace


def cmac128_be(key, message):
    return cmac_blocks_be(key,message)[-1][1]
