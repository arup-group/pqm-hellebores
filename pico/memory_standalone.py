import uctypes
import sys
import gc


BUFFER_MEMORY_SIZE = 2048

def get_unstriped_regions(bs: bytearray):
    '''From a given bytearray or memoryview, finds the starting address and
    places some test data in the memory. Then searches for the unstriped
    form of the data across the unstriped memory space. Then computes
    starting addresses for each unstriped region and returns them as
    memoryview objects.
    '''
    length = len(bs)
    # write some test data into the bytearray
    test_data = b'abcdefghijklmnopqrstuvwxyz'
    clear_data = b'\x00' * len(test_data)
    if len(test_data) > length:
        print('ERROR: stream.py, get_unstriped_regions() was called with a '
              'bytearray that was too short.')
        sys.exit(1)
    bs[:len(test_data)] = test_data
    # with the test_data written into memory, adjacent words of the unstriped
    # memory region will have the following contents.
    search_data = test_data[0:4] + test_data[16:20]
    # Figure out base address offset into unstriped memory, searching the
    # first 64kB of unstriped address space. We want to find the last match of
    # search data: this avoids a false match on data in the run-time environment.
    offset = None
    # Memory allocations are word-aligned (32 bits) so we can step through in
    # 4 byte increments
    for i in range(0, 65536-length, 4):
        if uctypes.bytearray_at(0x21000000 + i, 8) == search_data:
            offset = i
            print(f'Found data in unstriped memory at offset {i}')
    # Quit if we can't find the test data
    if offset == None:
        print('ERROR: stream.py, get_unstriped_regions() could not locate '
              'unstriped memory regions.')
        sys.exit(1)
    # clear the test data
    bs[:len(clear_data)] = clear_data
    # make bytearray objects that correspond to each page of unstriped memory
    p0 = memoryview(uctypes.bytearray_at(0x21000000 + offset, length // 4))
    p1 = memoryview(uctypes.bytearray_at(0x21010000 + offset, length // 4))
    p2 = memoryview(uctypes.bytearray_at(0x21020000 + offset, length // 4))
    p3 = memoryview(uctypes.bytearray_at(0x21030000 + offset, length // 4))
    return (p0, p1, p2, p3)


def configure_buffer_memory():
    '''Buffer memory is allocated for retaining a cache of samples received from
    the ADC. The memory is referenced by various memoryview objects that point
    to different portions of it. By default, buffer memory allocated from global
    heap is striped across 4 x 64kB memory regions, with striping at 32 bit
    word boundaries. When we are accessing memory from 2 CPU cores, we want to
    avoid accessing the same memory region from both cores simultaneously (one
    access will be delayed by the DMA scheduler).
    Consequently, we re-map the allocated bytearray into bytearray objects that
    are in contigous memory regions, using the unstriped memory mapping.
    This memory layout means that at a hardware level, reading and writing from
    different pages can occur in the same clock cycle.
    '''
    global acq
    global p0_mv, p1_mv, p2_mv, p3_mv
    global cells_mv

    # 2 bytes per channel, 4 channels
    # acq is a global variable to prevent it being garbage collected
    acq = bytearray(BUFFER_MEMORY_SIZE)
    # Create memoryviews for each unstriped region of the buffer (ie four pages).
    p0_mv, p1_mv, p2_mv, p3_mv = get_unstriped_regions(acq)
    # Create an array of memoryviews for each storage cell of the buffer.
    cells_list =      [ memoryview(p0_mv[i:i+8]) for i in range(0, len(p0_mv), 8) ]
    cells_list.extend([ memoryview(p1_mv[i:i+8]) for i in range(0, len(p1_mv), 8) ])
    cells_list.extend([ memoryview(p2_mv[i:i+8]) for i in range(0, len(p2_mv), 8) ])
    cells_list.extend([ memoryview(p3_mv[i:i+8]) for i in range(0, len(p3_mv), 8) ])
    # Convert to a tuple for slight performance gain
    cells_mv = tuple(cells_list)


def main():
    #gc.collect()
    configure_buffer_memory()
    print(f'Length of storage bytearray acq is: {len(acq)}')
    print(f'Length of unstriped bytearrays are: {len(p0_mv)}+{len(p1_mv)}+{len(p2_mv)}+{len(p3_mv)}')
    print(f'Length of cells lookup tuple is:    {len(cells_mv)}')
    bs0 = b'abcdefgh'
    bs1 = b'ijklmnop'
    bs2 = b'qrstuvwx'
    bs3 = b'yzABCDEF'
    print(f'Cells are 8 bytes long and the data should span across 2 pages in 4 byte chunks')
    print(f'Inserting data into cells: 5 ({bs0}), 69 ({bs1}), 133 ({bs2}), 197 ({bs3})')
    cells_mv[5][:] = bs0
    cells_mv[69][:] = bs1
    cells_mv[133][:] = bs2
    cells_mv[197][:] = bs3
    print(f'Reading back contents of cells:')
    for i in range(256):
        print(f'Cell {i}: {bytes(cells_mv[i])}')
    print(f'Reading back contents of unstriped buffer pages p0_mv, p1_mv, p2_mv, p3_mv:')
    print(f'{bytes(p0_mv[:])}')
    print(f'{bytes(p1_mv[:])}')
    print(f'{bytes(p2_mv[:])}')
    print(f'{bytes(p3_mv[:])}')
    print(f'Reading back contents of striped buffer acq:')
    print(f'{acq[:]}')

# Run from here
if __name__ == '__main__':
    main()
