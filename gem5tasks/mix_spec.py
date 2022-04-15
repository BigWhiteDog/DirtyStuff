#!/usr/bin/env python3

import os
import argparse
import time
import json

path_file = "/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/resources/simpoint_cpt_desc/06_max_path.json"

with open(path_file) as f:
    benchmark_cpt_file = json.load(f)

# benchmark_cpt_file = {
#     #cache sensitive
#     'mcf':'mcf_234550000000_0.127543/0/_2550001000_.gz',
#     'omnetpp':'omnetpp_172700000000_0.512105/0/_4700001000_.gz',
#     'sphinx3':'sphinx3_1843050000000_0.119702/0/_3050001000_.gz',
#     'xalancbmk':'xalancbmk_174600000000_0.205097/0/_6600001000_.gz',
#     #streaming
#     'milc':'milc_847950000000_0.146956/0/_7950001000_.gz',
#     'lbm': 'lbm_751550000000_0.51771/0/_7550001000_.gz',
#     'GemsFDTD':'GemsFDTD_665500000000_0.234708/0/_1500001000_.gz',
#     'hmmer':'hmmer_nph3_163100000000_0.138082/0/_3100001000_.gz',
# }

# like 'gcc':'gcc_ref32_O5_22850000000_0.197858/'
benchmarks = {k:v.split('/')[0] for k,v in benchmark_cpt_file.items() }

ff_base = '/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/'
# benchmark_dir = '/nfs/home/share/checkpoints_profiles/nemu_take_simpoint_cpt_06/'
gcpt_bin_path = '/nfs-nvme/home/share/checkpoints_profiles/gcpt.bin'

parser = argparse.ArgumentParser()
parser.add_argument('-b','--benchmark', type=str, required=True,help="like gcc-xal-xal-xal")
parser.add_argument('--l3_waymask_set', type=str, help="like 0xff,0xff00")
parser.add_argument('-I','--insts',type=int,default=10_000_000)
parser.add_argument('--cycle_afterwarm',type=int,default=1_000_000)
parser.add_argument('--set_est_dir',type=str,
        default="/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/40x1M/mcf-sphinx3/0x1-0xfe/set_est")
parser.add_argument('-n','--np',type=int,default=2)
parser.add_argument('-W','--warmup',type=int,default=50_000_000)
parser.add_argument('-D','--output',type=str,default='',help='output dir')
parser.add_argument('--debug-flag',type=str)
parser.add_argument('-C','--compile', action="store_true",help="compile Gem5 first")
parser.add_argument('--l2inc',type=int,default=1)
parser.add_argument('--l3inc',type=int,default=1)
parser.add_argument('--l2_tb_size',type=int,default=1024)
parser.add_argument('--l3_tb_size',type=int,default=2048)
args = parser.parse_args()

if args.compile:
    os.system('python3 `which scons` '+ff_base+'build/RISCV/gem5.opt -j64')

# ==================  Basics  ==================
binary = ff_base+'build/RISCV/gem5.opt'
outdir = ff_base+'log/{}'.format(args.benchmark) if args.output=='' else args.output
outopt = '--outdir='+outdir
debugf = '--debug-flag='+ args.debug_flag if args.debug_flag else ''
fspy   = ff_base+'configs/example/fs.py'

# ==================  Options  ==================
opt = []
opt.append('--nohype --branch-trace-file=useless_branch.protobuf.gz')
opt.append('--num-cpus={}'.format(args.np))
opt.append('--cpu-type=DerivO3CPU --num-ROB=192 --num-PhysReg=192 --num-IQ=192 --num-LQ=72 --num-SQ=48')
# opt.append('--mem-type=DRAMsim3')
opt.append('--mem-type=DDR4_2400_16x4')
opt.append('--mem-size={}GB'.format(args.np * 8))
# opt.append('--mem-channels=2')

opt.append('--cacheline_size=64')
opt.append('--caches --l2cache --l3_cache')
opt.append('--l1i_size=32kB --l1i_assoc=8')
opt.append('--l1d_size=32kB --l1d_assoc=8')

opt.append('--l2_size=1MB --l2_assoc=16')
opt.append('--l2_slices=1024')
opt.append('--l3_size=2MB --l3_assoc=8')
opt.append('--l3_slices=4096')

opt.append('--l1d_hwp_type=StridePrefetcher')
opt.append('--l2_hwp_type=BOPPrefetcher')

opt.append('--l2inc={} --l3inc={}'.format(args.l2inc, args.l3inc))
opt.append('--l2_tb_size={} --l3_tb_size={}'.format(args.l2_tb_size, args.l3_tb_size))

if args.l3_waymask_set:
    opt.append('--l3_waymask_set="{}"'.format(args.l3_waymask_set))

if args.set_est_dir:
    opt.append('--set_est_dir={}'.format(args.set_est_dir))

gcpt_all = [benchmark_cpt_file[bm] for bm in args.benchmark.split("-")]
# opt.append('--job-benchmark')

# use "" around multiple paths connnected by ;
opt.append('--generic-rv-cpt=' + '"' + ";".join(gcpt_all) + '"')
opt.append('--gcpt-restorer=' + gcpt_bin_path)

# opt.append('--maxinsts={} --gcpt-warmup={}'.format(args.insts+args.warmup, args.warmup))
opt.append('--gcpt-warmup={}'.format(args.warmup))
opt.append('--cycle_afterwarm={}'.format(args.cycle_afterwarm))


# ==================  RUN  ==================
cmd = [binary, outopt, debugf, fspy]
cmd.extend(opt)
print(" ".join(cmd))
os.system(" ".join(cmd))
os.system("echo "+time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())+">"+outdir+"/timestamp")
