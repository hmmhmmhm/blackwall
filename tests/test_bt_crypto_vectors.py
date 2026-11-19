import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from bt_crypto_vectors import aes128_be, hci_encrypt, cmac128_be


class CryptoVectors(unittest.TestCase):
    def test_fips197_block(self):
        self.assertEqual(aes128_be(bytes(range(16)),bytes.fromhex('00112233445566778899aabbccddeeff')),
                         bytes.fromhex('69c4e0d86a7b0430d8cdb78070b4c55a'))

    def test_hci_little_endian_fields(self):
        self.assertEqual(hci_encrypt(bytes(range(16))[::-1],bytes.fromhex('00112233445566778899aabbccddeeff')[::-1]),
                         bytes.fromhex('69c4e0d86a7b0430d8cdb78070b4c55a')[::-1])

    def test_no_padding_or_variable_key_size(self):
        for size in [0,15,17,24,32]:
            for function in [aes128_be,hci_encrypt]:
                with self.subTest(size=size,function=function.__name__):
                    with self.assertRaises(ValueError):function(bytes(size),bytes(16))
                    with self.assertRaises(ValueError):function(bytes(16),bytes(size))

    def test_rfc4493_cmac_examples(self):
        key=bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')
        message=bytes.fromhex('6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e5130c81c46a35ce411')
        for data,tag in [(b'','bb1d6929e95937287fa37d129b756746'),
                         (message[:16],'070a16b46b4d4144f79bdd9dd04a287c'),
                         (message,'dfa66747de9ae63030ca32611497c827')]:
            with self.subTest(length=len(data)):
                self.assertEqual(cmac128_be(key,data),bytes.fromhex(tag))


if __name__=='__main__':unittest.main()
