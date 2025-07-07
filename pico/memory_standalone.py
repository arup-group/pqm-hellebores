import uctypes
import sys
import gc


BUFFER_MEMORY_SIZE = 2048

def get_unstriped_regions(bs: bytearray):
    '''From a given bytearray or memoryview, finds the starting address and
    places some test data in the bytearray. Then searches for the unstriped
    form of the data across the unstriped memory space. Then computes
    starting addresses for each unstriped region and returns them as
    bytearray objects.
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
    # first 64kB of unstriped address space and using the last location
    # found.
    offset = None
    for i in range(0, 65528):
        if (uctypes.bytearray_at(0x21000000 + i, 8) == search_data):
            print(f'Found data in unstriped memory at offset {i}')
            offset = i
    # quit if we can't find the test data
    if offset == None:
        print('ERROR: stream.py, get_unstriped_regions() could not locate '
              'unstriped memory regions.')
        sys.exit(1)
    # clear the test data
    bs[:len(clear_data)] = clear_data
    # make bytearray objects that correspond to each page, using unstriped memory mapping
    p0 = uctypes.bytearray_at(0x21000000 + offset, length // 4)
    p1 = uctypes.bytearray_at(0x21010000 + offset, length // 4)
    p2 = uctypes.bytearray_at(0x21020000 + offset, length // 4)
    p3 = uctypes.bytearray_at(0x21030000 + offset, length // 4)
    # also make bytearray objects that correspond to each cell, in page order
    cells_list =      [ uctypes.bytearray_at(0x21000000 + offset + i, 8) for i in range(0, length // 4, 8) ]
    cells_list.extend([ uctypes.bytearray_at(0x21010000 + offset + i, 8) for i in range(0, length // 4, 8) ])
    cells_list.extend([ uctypes.bytearray_at(0x21020000 + offset + i, 8) for i in range(0, length // 4, 8) ])
    cells_list.extend([ uctypes.bytearray_at(0x21030000 + offset + i, 8) for i in range(0, length // 4, 8) ])
    # convert list to tuple, for marginal performance benefit
    cells = tuple(cells_list)
    return (p0, p1, p2, p3, cells)


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
    global p0, p1, p2, p3
    global cells

    # 2 bytes per channel, 4 channels
    # acq is a global variable to prevent it being garbage collected
    acq = bytearray(BUFFER_MEMORY_SIZE)
    # Create bytearrays for each unstriped region of the buffer (ie four pages).
    # Also create a tuple of bytearrays that represent each individual cell
    p0, p1, p2, p3, cells = get_unstriped_regions(acq)



def main():
    #gc.collect()
    configure_buffer_memory()
    print(f'Length of storage bytearray acq is: {len(acq)}')
    print(f'Length of unstriped bytearrays are: {len(p0)}+{len(p1)}+{len(p2)}+{len(p3)}')
    print(f'Length of cells lookup tuple is:    {len(cells)}')
    bs0 = b'abcdefgh'
    bs1 = b'ijklmnop'
    bs2 = b'qrstuvwx'
    bs3 = b'yzABCDEF'
    print(f'Cells are 8 bytes long and the data should span across 2 pages in 4 byte chunks')
    print(f'Inserting data into cells: 5 ({bs0}), 69 ({bs1}), 133 ({bs2}), 197 ({bs3})')
    cells[5][:] = bs0
    cells[69][:] = bs1
    cells[133][:] = bs2
    cells[197][:] = bs3
    print(f'Reading back contents of cells:')
    for i in range(256):
        print(f'Cell {i}: {bytes(cells[i])}')
    print(f'Reading back contents of unstriped buffer pages p0, p1, p2, p3:')
    print(f'{p0[:]}')
    print(f'{p1[:]}')
    print(f'{p2[:]}')
    print(f'{p3[:]}')
    print(f'Reading back contents of striped buffer acq:')
    print(f'{acq[:]}')

# Run from here
if __name__ == '__main__':
    main()
