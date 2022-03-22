#!/usr/bin/env python3
'''
sqanti3_stats.py
Generate counts for sim

@author Jorge Mestre Tomas (jormart2@alumni.uv.es)
@date 20/02/2022
'''

import argparse
from email.policy import default
import subprocess
import os
import sys
from collections import defaultdict
import pandas


try:
    from bx.intervals import IntervalTree
except ImportError:
    print('Unable to import bx-python! Please make sure bx-python is installed.', file=sys.stderr)
    sys.exit(-1)

class CAGEPeak:
    '''Adapted from SQANTI3 by Jorge Martinez'''
    def __init__(self, cage_bed_filename):
        self.cage_bed_filename = cage_bed_filename
        self.cage_peaks = defaultdict(lambda: IntervalTree()) # (chrom,strand) --> intervals of peaks

        self.read_bed()

    def read_bed(self):
        for line in open(self.cage_bed_filename):
            raw = line.strip().split()
            chrom = raw[0]
            start0 = int(raw[1])
            end1 = int(raw[2])
            strand = raw[5]
            tss0 = int(raw[6])
            self.cage_peaks[(chrom,strand)].insert(start0, end1, (tss0, start0, end1))

    def find(self, chrom, strand, query, search_window=10000):
        """
        :param start0: 0-based start of the 5' end to query
        :return: <True/False falls within a cage peak>, <nearest dist to TSS>
        dist to TSS is 0 if right on spot
        dist to TSS is + if downstream, - if upstream (watch for strand!!!)
        """
        within_peak, dist_peak = False, 'NA'
        for (tss0,start0,end1) in self.cage_peaks[(chrom,strand)].find(query-search_window, query+search_window):
            # Skip those cage peaks that are downstream the detected TSS because degradation just make the transcript shorter
            if strand=='+' and start0>int(query) and end1>int(query):
                continue
            if strand=='-' and start0<int(query) and end1<int(query):
                continue
            if not within_peak:
                within_peak, dist_peak = (start0<=query<end1), (query - tss0) * (-1 if strand=='-' else +1)
            else:
                d = (query - tss0) * (-1 if strand=='-' else +1)
                if abs(d) < abs(dist_peak):
                    within_peak, dist_peak = (start0<=query<end1), d
        return within_peak, dist_peak


def sqanti3_stats(args):
    def write_whithin_cage(row):
        return within_cage_dict[row['transcript_id']]

    def write_dist_cage(row):
        return dist_cage_dict[row['transcript_id']]

    print('***Running SQANTI3')
    src_dir = os.path.dirname(os.path.realpath(__file__))
    sqanti3 = os.path.join(src_dir, 'SQANTI3/sqanti3_qc.py')

    min_ref_len = 0
    cmd =[sqanti3, args.isoforms, args.gtf, args.genome,
                          '-o', args.output, '-d', args.dir, '--cpus', str(args.cores),
                          '--min_ref_len', str(min_ref_len),
                          '--force_id_ignore']
    
    if args.cage_peak:
        cmd.append('--cage_peak')
        cmd.append(args.cage_peak)
    
    cmd = ' '.join(cmd)
    if subprocess.check_call(cmd, shell=True)!=0:
        print('ERROR running SQANTI3: {0}'.format(cmd), file=sys.stderr)
        #sys.exit(1)

    if args.cage_peak:
        print('***Parsing CAGE Peak data')
        cage_peak_data = CAGEPeak(args.cage_peak)

        within_cage_dict = defaultdict(lambda: False)
        dist_cage_dict = defaultdict(lambda: False)
        with open(args.trans_index, 'r') as index_file:
            header_names = index_file.readline()
            header_names = header_names.split()
            id_pos = header_names.index('transcript_id')
            chrom_pos = header_names.index('chrom')
            strand_pos = header_names.index('strand')
            start_pos = header_names.index('TSS_genomic_coord') # No need to get end because coordinates already swapper for negative strand
            for line in index_file:
                line = line.split()
                within_cage, dist_cage = cage_peak_data.find(line[chrom_pos], line[strand_pos], line[start_pos])
                within_cage_dict[line[id_pos]] = within_cage
                dist_cage_dict[line[id_pos]] = dist_cage
        index_file.close()

        trans_index = pandas.read_csv(args.trans_index, sep='\t', header=0)
        trans_index['dist_to_cage_peak'] = trans_index.apply(write_dist_cage, axis=1)
        trans_index['within_cage_peak'] = trans_index.apply(write_whithin_cage, axis=1)
        trans_index.to_csv(args.trans_index, sep='\t', na_rep='NA', header=True, index=False)

    print('***Generating SQANTI-SIM report')
    src_dir = os.path.dirname(os.path.realpath(__file__))
    classification_file = os.path.join(args.dir, (args.output + '_classification.txt'))
    junctions_file = os.path.join(args.dir, (args.output + '_junctions.txt'))

    cmd=['Rscript', os.path.join(src_dir,'SQANTI_SIM_report.R'),
         classification_file, junctions_file, args.trans_index, src_dir]

    cmd = ' '.join(cmd)
    if subprocess.check_call(cmd, shell=True)!=0:
        print('ERROR running SQANTI-SIM report generation: {0}'.format(cmd), file=sys.stderr)
        sys.exit(1)