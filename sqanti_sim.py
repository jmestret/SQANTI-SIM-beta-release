#!/usr/bin/env python3
"""
sqanti3_sim.py

Wrapper for long-read RNA-seq simulators (NanoSim and IsoSeqSim) to simulate
controlled novelty and degradation of transcripts based on SQANTI3 structural
categories

Author: Jorge Mestre Tomas (jormart2@alumni.uv.es)
"""

__version__ = "1.0b1"

import argparse
import numpy
import os
import random
import sys
from collections import defaultdict
from src import classify_gtf
from src import simulate_reads
from src import design_simulation
from src import evaluation_metrics
from time import strftime


def classif(input: list):
    """Classify transcripts in SQANTI3 structural categories

    Given a GTF annotation generates an index file with the potential SQANTI3
    structural category of each transcript

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py classif", description="sqanti_sim.py classif parse options", )
    parser.add_argument("--gtf", type=str, required=True, help="\t\tReference annotation in GTF format", )
    parser.add_argument("-o", "--output", type=str, default="sqanti_sim", help="\t\tPrefix for output file", )
    parser.add_argument("-d", "--dir", type=str, default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument("-k", "--cores", type=int, default=1, help="\t\tNumber of cores to run in parallel", )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] classif mode unrecognized arguments: {}\n".format(
                " ".join(unknown)
            ),
            file=sys.stderr,
        )
    
    if not os.path.isdir(args.dir):
        os.makedirs(args.dir)

    print("\n[SQANTI-SIM] Running with the following parameters:")
    print("[SQANTI-SIM] - Ref GTF:", str(args.gtf))
    print("[SQANTI-SIM] - Out prefix:", str(args.output))
    print("[SQANTI-SIM] - Out dir:", str(args.dir))
    print("[SQANTI-SIM] - N threads:", str(args.cores))

    print("\n[SQANTI-SIM][%s] Classifying transcripts in structural categories" %(strftime("%d-%m-%Y %H:%M:%S")))
    trans_info = classify_gtf.classify_gtf(args)
    
    print("[SQANTI-SIM] Summary table from categorization")
    classify_gtf.summary_table_cat(trans_info)

    print("[SQANTI-SIM][%s] classif step finished" %(strftime("%d-%m-%Y %H:%M:%S")))


def design(input: list):
    """Modifies reference annotation GTF and builds expression matrix

    Given the novel and known transcripts to simulate and its counts, generates
    the expression matrix to give as input to the long-read RNA-seq simulators
    and generetes the modified GTF to use as reference annotation in your tool

    Args:
        input (list): arguments to parse
    """
    parser = argparse.ArgumentParser(prog="sqanti_sim.py design", description="sqanti_sim.py design parse options", )
    subparsers = parser.add_subparsers(dest="mode", description="\t\tDifferent modes to generate the expression matrix: equal (simulate with equal coverage for all reads), custom (simulate with diferent negative binomial distributions for novel and known transcripts) or sample (simulate using a real sample)")

    parser_e = subparsers.add_parser("equal", help="\t\tRun in equal mode")
    parser_e.add_argument("-i", "--trans_index", type=str, required=True, help="\t\tFile with transcript information generated with SQANTI-SIM", )
    parser_e.add_argument("--gtf", type=str, required=True, help="\t\tReference annotation in GTF format", )
    parser_e.add_argument("-o", "--output", type=str, default=str(), help="\t\tPrefix for output files" )
    parser_e.add_argument("-d", "--dir", type=str, default=".", help="\t\tDirectory for output files (default: .)", )
    parser_e.add_argument("-nt", "--trans_number", type=int, default=10000, help="\t\tNumber of different transcripts to simulate", )
    parser_e.add_argument("--read_count", default=50000, type=int, help="\t\tNumber of reads to simulate", )
    parser_e.add_argument("--ISM", type=int, default=0, help="\t\tNumber of incomplete-splice-matches to delete", )
    parser_e.add_argument("--NIC", type=int, default=0, help="\t\tNumber of novel-in-catalog to delete", )
    parser_e.add_argument("--NNC", type=int, default=0, help="\t\tNumber of novel-not-in-catalog to delete", )
    parser_e.add_argument("--Fusion", type=int, default=0, help="\t\tNumber of Fusion to delete" )
    parser_e.add_argument("--Antisense", type=int, default=0, help="\t\tNumber of Antisense to delete", )
    parser_e.add_argument("--GG", type=int, default=0, help="\t\tNumber of Genic-genomic to delete", )
    parser_e.add_argument("--GI", type=int, default=0, help="\t\tNumber of Genic-intron to delete", )
    parser_e.add_argument("--Intergenic", type=int, default=0, help="\t\tNumber of Intergenic to delete", )
    parser_e.add_argument("-k", "--cores", type=int, default=1, help="\t\tNumber of cores to run in parallel", )
    parser_e.add_argument("-s", "--seed", type=int, default=None, help="\t\tRandomizer seed", )

    parser_c = subparsers.add_parser("custom", help="\t\tRun in custom mode")
    parser_c.add_argument("-i", "--trans_index", type=str, required=True, help="\t\tFile with transcript information generated with SQANTI-SIM", )
    parser_c.add_argument("--gtf", type=str, required=True, help="\t\tReference annotation in GTF format", )
    parser_c.add_argument("-o", "--output", type=str, default=str(), help="\t\tPrefix for output files" )
    parser_c.add_argument("-d", "--dir", type=str, default=".", help="\t\tDirectory for output files (default: .)", )
    parser_c.add_argument("-nt", "--trans_number", type=int, default=10000, help="\t\tNumber of different transcripts to simulate", )
    parser_c.add_argument("--nbn_known", type=float, default=15, help="\t\tAverage read count per known transcript to simulate (i.e., the parameter 'n' of the Negative Binomial distribution)", )
    parser_c.add_argument("--nbp_known", type=float, default=0.5, help="\t\tThe parameter 'p' of the Negative Binomial distribution for known transcripts", )
    parser_c.add_argument("--nbn_novel", type=float, default=5, help="\t\tAverage read count per novel transcript to simulate (i.e., the parameter 'n' of the Negative Binomial distribution)", )
    parser_c.add_argument("--nbp_novel", type=float, default=0.5, help="\t\tThe parameter 'p' of the Negative Binomial distribution for novel transcripts", )
    parser_c.add_argument("--ISM", type=int, default=0, help="\t\tNumber of incomplete-splice-matches to delete", )
    parser_c.add_argument("--NIC", type=int, default=0, help="\t\tNumber of novel-in-catalog to delete", )
    parser_c.add_argument("--NNC", type=int, default=0, help="\t\tNumber of novel-not-in-catalog to delete", )
    parser_c.add_argument("--Fusion", type=int, default=0, help="\t\tNumber of Fusion to delete" )
    parser_c.add_argument("--Antisense", type=int, default=0, help="\t\tNumber of Antisense to delete", )
    parser_c.add_argument("--GG", type=int, default=0, help="\t\tNumber of Genic-genomic to delete", )
    parser_c.add_argument("--GI", type=int, default=0, help="\t\tNumber of Genic-intron to delete", )
    parser_c.add_argument("--Intergenic", type=int, default=0, help="\t\tNumber of Intergenic to delete", )
    parser_c.add_argument("-k", "--cores", type=int, default=1, help="\t\tNumber of cores to run in parallel", )
    parser_c.add_argument("-s", "--seed", type=int, default=None, help="\t\tRandomizer seed", )

    parser_s = subparsers.add_parser("sample", help="\t\tRun in sample mode")
    parser_s.add_argument("-i", "--trans_index", type=str, required=True, help="\t\tFile with transcript information generated with SQANTI-SIM", )
    parser_s.add_argument("--gtf", type=str, required=True, help="\t\tReference annotation in GTF format", )
    parser_s.add_argument("-o", "--output", type=str, default=str(), help="\t\tPrefix for output files" )
    parser_s.add_argument("-d", "--dir", type=str, default=".", help="\t\tDirectory for output files (default: .)", )
    parser_s.add_argument("-nt", "--trans_number", type=int, default=None, help="\t\tNumber of different transcripts to simulate", )
    parser_s.add_argument("--genome", type=str, required=True, help="\t\tReference genome FASTA", )
    group = parser_s.add_mutually_exclusive_group()
    group.add_argument("--pb_reads", type=str, default=str(), help="\t\tInput PacBio reads for quantification", )
    group.add_argument("--ont_reads", type=str, default=str(), help="\t\tInput ONT reads for quantification", )
    group.add_argument("--mapped_reads", type=str, default=str(), help="\t\tAligned reads in SAM format", )
    parser_s.add_argument("--iso_complex", action="store_true", help="\t\tIf used the program will simulate the expressed isoform complexity (number of isoforms per gene)", )
    parser_s.add_argument("--diff_exp", action="store_true", help="\t\tIf used the program will simulate different expression values for novel and known transcripts", )
    parser_s.add_argument("--low_prob", type=float, default=0.1, help="\t\tLow value of prob vector (if --diff_exp)", )
    parser_s.add_argument("--high_prob", type=float, default=0.9, help="\t\tHigh value of prob vector (if --diff_exp)", )
    parser_s.add_argument("--ISM", type=int, default=0, help="\t\tNumber of incomplete-splice-matches to delete", )
    parser_s.add_argument("--NIC", type=int, default=0, help="\t\tNumber of novel-in-catalog to delete", )
    parser_s.add_argument("--NNC", type=int, default=0, help="\t\tNumber of novel-not-in-catalog to delete", )
    parser_s.add_argument("--Fusion", type=int, default=0, help="\t\tNumber of Fusion to delete" )
    parser_s.add_argument("--Antisense", type=int, default=0, help="\t\tNumber of Antisense to delete", )
    parser_s.add_argument("--GG", type=int, default=0, help="\t\tNumber of Genic-genomic to delete", )
    parser_s.add_argument("--GI", type=int, default=0, help="\t\tNumber of Genic-intron to delete", )
    parser_s.add_argument("--Intergenic", type=int, default=0, help="\t\tNumber of Intergenic to delete", )
    parser_s.add_argument("-k", "--cores", type=int, default=1, help="\t\tNumber of cores to run in parallel", )
    parser_s.add_argument("-s", "--seed", type=int, default=None, help="\t\tRandomizer seed", )
    
    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] design mode unrecognized arguments: {}\n".format(
                " ".join(unknown)
            ),
            file=sys.stderr,
        )

    total_novel = sum([args.ISM, args.NIC, args.NNC, args.Fusion, args.Antisense, args.GG, args.GI, args.Intergenic])
    if args.trans_number is not None and total_novel > args.trans_number:
        print("[SQANTI-SIM] ERROR: -nt/--trans number must be higher than the novel transcripts to simulate")
        sys.exit(1)

    if not os.path.isdir(args.dir):
        os.makedirs(args.dir)

    print("\n[SQANTI-SIM] Running with the following parameters:")
    if args.mode == "equal":
        print("[SQANTI-SIM] - Mode: equal")
        print("[SQANTI-SIM] - Ref GTF:", str(args.gtf))
        print("[SQANTI-SIM] - Out prefix:", str(args.output))
        print("[SQANTI-SIM] - Out dir:", str(args.dir))
        print("[SQANTI-SIM] - N transcripts:", str(args.trans_number))
        print("[SQANTI-SIM] - N reads:", str(args.read_count))

    elif args.mode == "custom":
        if args.nbn_known < 0 or args.nbn_novel < 0:
            print("[SQANTI-SIM] ERROR: --nbn_known and --nbn_novel must be greater than 0")
            sys.exit(1)
        if args.nbp_known < 0 or args.nbp_known > 1 or args.nbp_novel < 0 or args.nbp_novel > 1:
            print("[SQANTI-SIM] ERROR: --nbp_known and --nbp_novel must be in the interval [0,1]")
            sys.exit(1)

        print("[SQANTI-SIM] - Mode: custom")
        print("[SQANTI-SIM] - Ref GTF:", str(args.gtf))
        print("[SQANTI-SIM] - Out prefix:", str(args.output))
        print("[SQANTI-SIM] - Out dir:", str(args.dir))
        print("[SQANTI-SIM] - N transcripts:", str(args.trans_number))
        print("[SQANTI-SIM] - Known NB mean count:", str(args.nbn_known))
        print("[SQANTI-SIM] - Known NB probability:", str(args.nbp_known))
        print("[SQANTI-SIM] - Novel NB mean count:", str(args.nbn_novel))
        print("[SQANTI-SIM] - Novel NB probability:", str(args.nbp_novel))

    elif args.mode == "sample":
        if args.low_prob < 0 or args.low_prob > 1 or args.high_prob < 0 or args.high_prob > 1:
            print("[SQANTI-SIM] ERROR: --low_prob and --high_prob must be in the interval [0,1]")
            sys.exit(1)

        print("[SQANTI-SIM] - Mode: sample")
        print("[SQANTI-SIM] - Ref GTF:", str(args.gtf))
        print("[SQANTI-SIM] - Ref genome:", str(args.genome))
        print("[SQANTI-SIM] - Out prefix:", str(args.output))
        print("[SQANTI-SIM] - Out dir:", str(args.dir))
        print("[SQANTI-SIM] - N transcripts:", str(args.trans_number))
        if args.pb_reads:
            print("[SQANTI-SIM] - PacBio reads:", str(args.pb_reads))
        else:
            print("[SQANTI-SIM] - ONT reads:", str(args.ont_reads))
        print("[SQANTI-SIM] - N threads:", str(args.cores))

    if not args.seed:
        args.seed = int.from_bytes(os.urandom(1), 'big')
    random.seed(args.seed)
    numpy.random.seed(args.seed)
    print("[SQANTI-SIM] - Seed:", str(args.seed))

    print("[SQANTI-SIM]\tISM\tNIC\tNNC\tFusion\tAS\tGG\tGI\tIntergenic")
    print("[SQANTI-SIM]\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s" %(
        str(args.ISM), str(args.NIC), str(args.NNC), str(args.Fusion),
        str(args.Antisense), str(args.GG), str(args.GI), str(args.Intergenic)
    ))

    if not args.output:
        output = os.path.basename(args.trans_index).split("_")
        args.output = "_".join(output[:-1])

    # Modify GTF
    print("\n[SQANTI-SIM][%s] Generating modified GTF" %(strftime("%d-%m-%Y %H:%M:%S")))
    counts_end = design_simulation.simulate_gtf(args)

    counts_ini = defaultdict(
        lambda: 0,
        {
            "full-splice_match": 0,
            "incomplete-splice_match": args.ISM,
            "novel_in_catalog": args.NIC,
            "novel_not_in_catalog": args.NNC,
            "fusion": args.Fusion,
            "antisense": args.Antisense,
            "genic_intron": args.GI,
            "genic": args.GG,
            "intergenic": args.Intergenic,
        },
    )
    design_simulation.summary_table_del(counts_ini, counts_end)

    # Generate expression matrix
    print("[SQANTI-SIM][%s] Generating expression matrix" %(strftime("%d-%m-%Y %H:%M:%S")))
    index_file = os.path.join(args.dir, (args.output + "_index.tsv"))

    if args.mode == "equal":
        design_simulation.create_expr_file_fixed_count(index_file, args)

    elif args.mode == "custom":
        design_simulation.create_expr_file_nbinom(index_file, args)

    elif args.mode == "sample":
        if args.pb_reads:
            design_simulation.create_expr_file_sample(index_file, args, "pb")
        else:
            design_simulation.create_expr_file_sample(index_file, args, "ont")

    print("[SQANTI-SIM][%s] design step finished" %(strftime("%d-%m-%Y %H:%M:%S")))
    

def sim(input: list):
    """Simulate reads

    Simulate PacBio and/or ONT reads using the IsoSeqSim or NanoSim pipelines.
    It can also simulate Illumina reads using the polyester pipeline

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py sim", description="sqanti_sim.py sim parse options" )
    parser.add_argument("--gtf", type=str, required=True, help="\t\tReference annotation in GTF format", )
    parser.add_argument("--genome", type=str, required=True, help="\t\tReference genome FASTA", )
    parser.add_argument("-i", "--trans_index", type=str, required=True, help="\t\tFile with transcript information generated with SQANTI-SIM", )
    parser.add_argument("--read_type", type=str, default="dRNA", help="\t\tRead type for NanoSim simulation", )
    parser.add_argument("-d", "--dir", type=str, default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument("-k", "--cores", type=int, default=1, help="\t\tNumber of cores to run in parallel", )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pb", action="store_true", help="\t\tIf used the program will simulate PacBio reads with IsoSeqSim", )
    group.add_argument("--ont", action="store_true", help="\t\tIf used the program will simulate ONT reads with NanoSim", )
    parser.add_argument("--illumina", action="store_true", help="\t\tIf used the program will simulate Illumina reads with RSEM", )
    parser.add_argument("--long_count", type=int, default=None, help="\t\tNumber of long reads to simulate (if not given it will use the counts of the given expression file)", )
    parser.add_argument("--short_count", type=int, default=None, help="\t\tNumber of short reads to simulate (if not given it will use the counts of the given expression file)", )
    parser.add_argument("-s", "--seed", type=int, default=None, help="\t\tRandomizer seed", )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] sim mode unrecognized arguments: {}\n".format(" ".join(unknown)),
            file=sys.stderr,
        )
    
    print("\n[SQANTI-SIM] Running with the following parameters:")
    print("[SQANTI-SIM] - Ref GTF:", str(args.gtf))
    print("[SQANTI-SIM] - Ref genome:", str(args.genome))
    print("[SQANTI-SIM] - Index file:", str(args.trans_index))
    print("[SQANTI-SIM] - Out dir:", str(args.dir))

    if args.ont:
        print("[SQANTI-SIM] - Platform: ONT")
        print("[SQANTI-SIM] - Read type:", str(args.read_type))
    else:
        print("[SQANTI-SIM] - Platform: PacBio")
    
    if args.long_count:
        print("[SQANTI-SIM] - Long reads:", str(args.long_count))
    else:
        print("[SQANTI-SIM] - Long reads: requested_counts from index file")
    
    if args.illumina:
        print("[SQANTI-SIM] - Platform: Illumina")
        if args.short_count:
            print("[SQANTI-SIM] - Short reads:", str(args.short_count))
        else:
            print("[SQANTI-SIM] - Short reads: requested_counts from index file")

    print("[SQANTI-SIM] - N threads:", str(args.cores))

    if not args.seed:
        args.seed = int.from_bytes(os.urandom(1), 'big')
    random.seed(args.seed)
    numpy.random.seed(args.seed)
    print("[SQANTI-SIM] - Seed:", str(args.seed))

    # Simulation with IsoSeqSim, NanoSim and/or Polyester
    if args.pb:
        print("\n[SQANTI-SIM][%s] Simulating PacBio reads" %(strftime("%d-%m-%Y %H:%M:%S")))
        simulate_reads.pb_simulation(args)
    if args.ont:
        print("\n[SQANTI-SIM][%s] Simulating ONT reads" %(strftime("%d-%m-%Y %H:%M:%S")))
        simulate_reads.ont_simulation(args)
    if args.illumina:
        print("\n[SQANTI-SIM][%s] Simulating Illumina reads" %(strftime("%d-%m-%Y %H:%M:%S")))
        simulate_reads.illumina_simulation(args)

    print("[SQANTI-SIM][%s] sim step finished" %(strftime("%d-%m-%Y %H:%M:%S")))


def eval(input: list):
    """Generates SQANTI-SIM report

    Run SQANTI3 with the reconstructed transcripts retrieved by your pipeline
    and generates the SQANTI-SIM report with the evaluation metrics

    Args:
        input (list): arguments to parse
    """

    parser = argparse.ArgumentParser( prog="sqanti_sim.py eval", description="sqanti_sim.py eval parse options", )
    parser.add_argument("--isoforms", type=str, required=True, help="\t\tGTF with trancriptome reconstructed with your pipeline", )
    parser.add_argument("--gtf", type=str, required=True, help="\t\tReference annotation in GTF format", )
    parser.add_argument("--genome", type=str, required=True, help="\t\tReference genome FASTA", )
    parser.add_argument("-i", "--trans_index", type=str, required=True, help="\t\tFile with transcript information generated with SQANTI-SIM", )
    parser.add_argument("-o", "--output", type=str, default="sqanti_sim", help="\t\tPrefix for output files", )
    parser.add_argument("-d", "--dir", type=str, default=".", help="\t\tDirectory for output files (default: .)", )
    parser.add_argument("--short_reads", type=str, default=None, help="\t\tFile Of File Names (fofn, space separated) with paths to FASTA or FASTQ from Short-Read RNA-Seq. If expression or coverage files are not provided, Kallisto (just for pair-end data) and STAR, respectively, will be run to calculate them.", required=False, )
    parser.add_argument("--cage_peak", type=str, default=None,help="\t\tFANTOM5 Cage Peak (BED format, optional)" )
    parser.add_argument("--fasta", action="store_true", help="\t\tUse when running SQANTI by using as input a FASTA/FASTQ with the sequences of isoforms", )
    parser.add_argument("--aligner_choice", type=str, default="minimap2",help="\t\tIf --fasta used, choose the aligner to map your isoforms", choices=["minimap2","deSALT","gmap","uLTRA"])
    parser.add_argument("--min_support", type=int, default=3, help="\t\tMinimum number of supporting reads for an isoform", )
    parser.add_argument("-k", "--cores", type=int, default=1, help="\t\tNumber of cores to run in parallel", )

    args, unknown = parser.parse_known_args(input)

    if unknown:
        print(
            "[SQANTI-SIM] sim mode unrecognized arguments: {}\n".format(" ".join(unknown)),
            file=sys.stderr,
        )

    print("\n[SQANTI-SIM] Running with the following parameters:")
    print("[SQANTI-SIM] - Reconstructed transcripts:", str(args.isoforms))
    print("[SQANTI-SIM] - Modified ref GTF:", str(args.gtf))
    print("[SQANTI-SIM] - Ref genome:", str(args.genome))
    print("[SQANTI-SIM] - Index file:", str(args.trans_index))
    print("[SQANTI-SIM] - Out prefix:", str(args.output))
    print("[SQANTI-SIM] - Out dir:", str(args.dir))

    if args.short_reads:
        print("[SQANTI-SIM] - Short reads:", str(args.short_reads))
    if args.CAGE_peak:
        print("[SQANTI-SIM] - CAGE Peak:", str(args.CAGE_peak))
    
    print("[SQANTI-SIM] - Min support:", str(args.min_support))
    print("[SQANTI-SIM] - N threads:", str(args.cores))
    print()

    evaluation_metrics.sqanti3_stats(args)

    print("[SQANTI-SIM][%s] eval step finished" %(strftime("%d-%m-%Y %H:%M:%S")))


#####################################
#                                   #
#               MAIN                #
#                                   #
#####################################

print(
    """                                                                      
      _____  ____            _   _ _______ _____      _____ _____ __  __  
     / ____|/ __ \     /\   | \ | |__   __|_   _|    / ____|_   _|  \/  | 
    | (___ | |  | |   /  \  |  \| |  | |    | |_____| (___   | | | \  / | 
     \___ \| |  | |  / /\ \ | . ` |  | |    | |______\___ \  | | | |\/| | 
     ____) | |__| | / ____ \| |\  |  | |   _| |_     ____) |_| |_| |  | | 
    |_____/ \___\_\/_/    \_\_| \_|  |_|  |_____|   |_____/|_____|_|  |_| 
                                                                          
              A SIMULATOR OF CONTROLLED NOVELTY AND DEGRADATION           
                    OF TRANSCRIPTS SEQUENCED BY LONG-READS                
    """
)

if len(sys.argv) < 2:
    print("[SQANTI-SIM] usage: python sqanti_sim.py <mode> --help\n", file=sys.stderr)
    print("[SQANTI-SIM] modes: classif, design, sim, eval\n", file=sys.stderr)
    sys.exit(1)

else:
    mode = sys.argv[1].lower()
    input = sys.argv[2:]

if mode == "classif":
    print("[SQANTI-SIM] CLASSIF MODE")
    res = classif(input)

elif mode == "design":
    print("[SQANTI-SIM] DESIGN MODE")
    res = design(input)

elif mode == "sim":
    print("[SQANTI-SIM] SIM MODE")
    res = sim(input)

elif mode == "eval":
    print("[SQANTI-SIM] EVAL MODE")
    res = eval(input)

elif mode in ["--version", "-v"]:
    print("[SQANTI-SIM] SQANTI-SIM %s\n" %(__version__))

else:
    print("[SQANTI-SIM] usage: python sqanti_sim.py <mode> --help\n", file=sys.stderr)
    print("[SQANTI-SIM] modes: classif, design, sim, eval\n", file=sys.stderr)
    sys.exit(1)
