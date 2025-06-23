import uctypes
import sys
import gc

def get_unstriped_regions(bs):
    length = len(bs)
    # figure out base addresses of unstriped memory and convert to bytearray
    # objects
    for i in range(0, 65528):
        if uctypes.bytearray_at(0x21000000 + i, 8) == b'abcdqrst':
            found = i
            break
    base_unstriped = 0x21000000 + found
    b0 = uctypes.bytearray_at(base_unstriped, length // 4)
    b1 = uctypes.bytearray_at(base_unstriped + 0x10000, length // 4)
    b2 = uctypes.bytearray_at(base_unstriped + 0x20000, length // 4)
    b3 = uctypes.bytearray_at(base_unstriped + 0x30000, length // 4)
    return (b0, b1, b2, b3)

def main():
    #gc.collect()
    bs = bytearray(b'abcdefghijklmnopqrstuvwxyzABCDEF')
    b0, b1, b2, b3 = get_unstriped_regions(bs)
    print(f'Address of bs    : {hex(uctypes.addressof(bs))}')
    print(f'Address of b0    : {hex(uctypes.addressof(b0))}')
    print()
    print('Original contents.')
    print('bytearray bs:             ', bs)
    print('unstriped b0, b1, b2, b3: ', b0, b1, b2, b3)
    print()
    print('Now changing bytes only within b0.')
    b0[0:8] = b'12345678'
    print('bytearray bs:             ', bs)
    print('unstriped b0, b1, b2, b3: ', b0, b1, b2, b3)
    print()
    print('Now changing sub-string of bs.')
    bs[4:8] = b'ZZZZ'
    print('bytearray bs:             ', bs)
    print('unstriped b0, b1, b2, b3: ', b0, b1, b2, b3)


# Run from here
if __name__ == '__main__':
    main()
