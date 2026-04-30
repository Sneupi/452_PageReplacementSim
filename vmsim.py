# File: vmsim.py
# Author: Gabe Venegas
# Description:
#   CSC 452 (Operating Systems) virtual memory simulation. 
#   Utilizing Valgrind Lackey memory trace outputs
#   as simulation input (.trace.gz)

import argparse
import gzip
from collections import deque
import random

    
class Page:
    def __init__(self):
        self.frame = None
        self.dirty = False
        self.referenced = False
        self.valid = False
        
        # for optimal algorithm, all future positions in 
        # instruction sequence this page is accessed
        self.occurrences = deque()   

    def __str__(self):
        return '\n    '.join([super.__str__(self)] + [f'{k} = {v}' for k,v in vars(self).items()])


def parse_args(args=None):
    
    parser = argparse.ArgumentParser(prog="vmsim")
    parser.add_argument("-n", dest="numframes", type=int, required=True)
    parser.add_argument("-a", dest="algorithm", choices=["opt", "clock", "rand", "nru"], required=True)
    parser.add_argument("-r", dest="refresh", type=int)
    parser.add_argument("tracefile")
    parsed_args = parser.parse_args(args=args)

    if parsed_args.algorithm == "nru" and parsed_args.refresh is None:
        parser.error("The NRU algorithm requires a refresh rate specified by -r.")
    
    return parsed_args


def main(args: argparse.Namespace):
    
    # INITIALIZE ------------------------------------------------------------------
    
    # 32-bit addr space divided into 2^14=16kb (page_size) chunks
    # 2^(32-14) unique page addresses

    num_frames = int(args.numframes)
    frame_table: list[Page] = [None] * num_frames # physical pages in memory
    page_table: list[Page] = [Page() for _ in range(int(pow(2, 32-14)))] # virtual pages of process
    accesses: list[tuple[int, bool]]= []                   # tuples (pg_addr, is_write)
    count_accesses = 0
    count_page_fault = 0
    count_disk_writes = 0

    if args.algorithm == 'nru':
        nru_refresh = int(args.refresh)
        nru_counter = 0
    if args.algorithm == 'clock':
        clock_hand = 0

    # PRE-LOAD TRACES -------------------------------------------------------------

    def load_traces(f):
        seq_id = 0
        for line in f:
            
            # skip non-instructions
            if not (line[0] == ' ' or line[0] == 'I'): continue
            
            # cast hex str to int
            v_addr = int(line[3:11], 16) 
            
            # rshift by 14 equal to div by 2^14 (=16kb page size)
            pg_addr = v_addr >> 14 
            
            # append instruction to sim
            if line[0] == 'I' or line[1] == 'L': 
                accesses.append((pg_addr,False)) # read
            elif line[1] == 'S': 
                accesses.append((pg_addr,True)) # write
            elif line[1] == 'M': 
                accesses.append((pg_addr,False)) # read
                page_table[pg_addr].occurrences.append(seq_id)
                seq_id += 1
                accesses.append((pg_addr,True)) # ...then write
            
            page_table[pg_addr].occurrences.append(seq_id)
            seq_id += 1
            
    if args.tracefile.endswith('.trace.gz'):
        with gzip.open(args.tracefile, 'rt') as f:
            load_traces(f)    
    elif args.tracefile.endswith('.trace'):
        with open(args.tracefile, 'r') as f:
            load_traces(f)    
    else:
        print('Bad trace file. Neither ".trace.gz", ".trace"')  
        exit(1)
        
    # SIMULATE --------------------------------------------------------------------

    for pg_addr, is_write in accesses:
        
        # (For NRU algorithm) Handle page refresh timeouts
        if args.algorithm == 'nru':
            nru_counter = (nru_counter + 1) % nru_refresh
            
            # If time for refresh, all refs stale 
            if  nru_counter == 0:
                for p in frame_table:
                    if p: p.referenced = False
        
        # Attempt instruction
        page = page_table[pg_addr]
        page.occurrences.popleft()
        page.referenced = True
        if is_write: page.dirty = True
        
        # If page fault, handle
        if not page.valid:
            count_page_fault += 1
            
            # If memory space, add
            if None in frame_table:
                frame_table[frame_table.index(None)] = page
                
            # No memory, evict a page
            else:
                idx = -1
                evicted: Page = None
                
                # Pick a page to evict
                match args.algorithm:
                    case 'opt':
                        # find page that will remain unused for longest time duration
                        evicted = max(frame_table, key=lambda p: p.occurrences[0] if p.occurrences else float('inf'))
                    case 'clock':
                        # find first unreferenced page not holding a 2nd chance
                        evicted = frame_table[clock_hand]
                        while evicted.referenced:
                            evicted.referenced = False
                            clock_hand = (clock_hand + 1) % num_frames
                            evicted = frame_table[clock_hand]
                    case 'rand':
                        # find any random page
                        idx = random.randint(0, len(frame_table)-1)
                        evicted = frame_table[idx]
                    case 'nru':
                        # find least recently used, prio unref'd over ref'd, prio clean over dirty
                        evicted = min(frame_table, key=lambda p: (p.referenced<<1)|(p.dirty))
                
                # Find frame where we page swap
                if args.algorithm != 'rand':
                    idx = frame_table.index(evicted)
                
                # Disk write before eviction
                if evicted.dirty: 
                    count_disk_writes += 1
                
                # Eviction time
                evicted.dirty = False
                evicted.referenced = False
                evicted.valid = False
                frame_table[idx] = page
            
            # Mark as valid after load
            page.valid = True
        
        # Count access success
        count_accesses += 1
    
    return count_accesses, count_page_fault, count_disk_writes
       
       
# MAIN ------------------------------------------------------------------------       
     
if __name__ == "__main__":
    
    args = parse_args()

    count_accesses, count_page_fault, count_disk_writes = main(args)

    print(f'Algorithm: {args.algorithm}')
    print(f'Number of frames: {args.numframes}')
    print(f'Total memory accesses: {count_accesses}')
    print(f'Total page faults: {count_page_fault}')
    print(f'Total writes to disk: {count_disk_writes}')