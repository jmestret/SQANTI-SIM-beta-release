#!/usr/bin/env python3
'''
Stats from sqantisim

Author: Jorge Mestre Tomas
Date: 15/02/2021
Last update: 15/02/2022
'''

import argparse
from collections import defaultdict
from operator import ge


class myQueryIsoforms:
    '''Features of the query isoform and its associated reference'''
    def __init__(self, id=None, gene_id=None, str_class=None, genes=None, transcripts=None, junctions=[], names=[], counts=0):
        self.id = id
        self.gene_id = gene_id
        self.str_class = str_class
        self.genes = genes
        self.transcripts = transcripts
        self.junctions = junctions
        self.names = names
        self.counts = counts
        


def main():
    parser = argparse.ArgumentParser(prog='sqanti3_sim.py', description="SQANTI-SIM: a simulator of controlled novelty and degradation of transcripts sequence by long-reads")
    parser.add_argument('--classi', default = False,  help = '\t\tFile with transcripts structural categories generated with SQANTI-SIM')
    parser.add_argument('--junc', default = False,  help = '\t\tFile with transcripts structural categories generated with SQANTI-SIM')
    parser.add_argument('--deleted', default = False,  help = '\t\tFile with deleted trans', required=True)
    parser.add_argument('--fsim', default = False,  help = '\t\tFile with deleted trans', required=True)
    parser.add_argument('-o', '--output', default='sqanti_sim', help = '\t\tPath for output files')
    parser.add_argument('--nanosim', action='store_true', help = '\t\tIf used the program will only categorize the GTF file but skipping writing a new modified GTF')
    parser.add_argument('--isoseqsim', action='store_true', help = '\t\tIf used the program will only categorize the GTF file but skipping writing a new modified GTF')
    
    args = parser.parse_args()

    # Get junctions from deleted reads
    #ref_by_chr = defaultdict(lambda: myQueryIsoforms())
    ref = []
    ref_by_SC = defaultdict(lambda: [])
    
    with open(args.deleted, 'r') as f_del:
        skip = f_del.readline()
        for line in f_del:
            juncs = []
            line = line.split()
            SC = line[2]
            donors = line[5].split(',')
            acceptors = line[6].split(',')
            for d, a in zip(donors, acceptors):
                juncs.append(d)
                juncs.append(a)
            
            ref[SC].append(myQueryIsoforms(id=line[0], gene_id=line[1],
                                       str_class=line[2],
                                       genes=line[3].split('_'),
                                       transcripts=line[4].split('_'),
                                       junctions=juncs))
    f_del.close()

    # Count ocurrencies
    if args.nanosim:
        with open(args.fsim, 'r') as f_sim:
            for line in f_sim:
                if line.startswith('@'):
                    line = line.lstrip('@')
                    id = line.split('_')

                    for i in range(len(ref)):
                        if id == ref[i].id.split('.')[0]:
                            ref[i].names.append(line)
                            ref[i].counts += 1
        f_sim.close()



    elif args.isoseqsim:
        with open(args.fsim, 'r') as f_sim:
            for line in f_sim:
                    line = line.split()
                    simid = line[0]
                    refid = line[1]

                    for i in range(len(ref)):
                        if refid == ref.id:
                            ref[i].names.append(simid)
                            ref[i].counts += 1
        f_sim.close()  

    # Delete those simulated with low coverage (smaller than the threshhold used in the pipeline)
    threshold = 3
    for SC in ref:
        print(SC, len(ref[SC]))
        for rec in ref[SC]:
            if rec.counts < threshold:
                ref[SC].remove(rec)
        print(SC, len(ref[SC]))


    # READ read to isoform id by the pipeline file!
    # for talon is read_annot.tsv       

    # Get SC and ref from query isoforms
    isos = defaultdict(lambda: [])
    with open(args.classi, 'r') as f_class:
        skip = f_class.readline()
        for line in f_class:
            line = line.split()
            iso = line[0]
            SC = line[5]
            ref_g = line[6].split('_')
            ref_t = line[7].split('_')
            isos[iso].append(myQueryIsoforms(id=iso, gene_id=None,
                                                 str_class=SC,
                                                 genes=ref_g,
                                                 transcripts=ref_t))

    f_class.close()
    
    # Get junctions from query isoforms
    with open(args.junc, 'r') as f_junc:
        skip = f_junc.readline()
        for line in f_junc:
            line = line.split()
            iso = line[0]
            d = line[4]
            a = line[5]
            isos[iso].junctions.append(d)
            isos[iso].junctions.append(a)
    f_junc.close()

    iso_by_SC = defaultdict(lambda: [])
    for iso in isos.values():
        iso_by_SC[iso.str_class].append(iso)

    # Get Stats
    for SC in ref_by_SC:
        print('SC stats')
        TP = 0
        FP = 0
        for iso in iso_by_SC[SC]:
            for rec in ref_by_SC[SC]:
                if rec.junctions == iso.junctions:
                    TP += 1
                    break
            else:
                FP += 1
        FN = len(ref_by_SC[SC]) - TP
        print('TP', TP)
        print('FP', FP)
        print('FN', FN)
        print('Precision', TP/(TP+FP))
        print('FDR', FP/(TP+FP))
        print('Sensitivity', TP/(TP+FN))



if __name__ == '__main__':
    main()