# Generates graphs to analyze relationship 
# between frame count and page faults 
# per-algorithm for each of our example trace files

import matplotlib.pyplot as plt
import numpy as np
import vmsim

x = np.array([8, 16, 32, 64])
refresh = 1000 # for NRU

for tracefile in ['gcc.trace.gz', 'ls.trace.gz']:

    for algorithm in ["opt", "clock", "rand", "nru"]:
        
        y = []
        
        for numframes in x:

            args_str = f'-n {numframes} -a {algorithm} -r {refresh} {tracefile}'
            args = vmsim.parse_args(args_str.split())
            _, num_faults, _ = vmsim.main(args)

            y.append(num_faults)
            print(f"{(algorithm+' '+str(numframes)):<25}", end='\r')
        
        plt.plot(x, y, marker='o', linestyle='-', label=f'{algorithm}')

    plt.xlabel("# Frames")
    plt.ylabel("# Faults")    
    plt.title(f"Frame Table Size vs Page Faults ({tracefile})")
    plt.legend()
    plt.savefig(f'{tracefile}.png')
    plt.close()