#!/usr/bin/env python3

import os
import argparse
import time
import json

ff_base = '/nfs/home/zhangchuanqi/lvna/for_xs/GEM5-internal'

parser = argparse.ArgumentParser()
parser.add_argument('-b','--benchmark', type=str, required=True,help="like gcc-xal-xal-xal")
parser.add_argument('-I','--insts',type=int,default=100_000_000)
parser.add_argument('-n','--np',type=int,default=1)
parser.add_argument('-W','--warmup',type=int,default=50_000_000)
parser.add_argument('-D','--output',type=str,default='',help='output dir')
parser.add_argument('-A','--insts_afterwarm',type=int,default=20_000_000)
parser.add_argument('--debug-flag',type=str)
parser.add_argument('--enable_archdb', action='store_true')
parser.add_argument('--nohype',action='store_true')
# parser.add_argument('--l3_size_MB',type=int,default=8)
parser.add_argument('--l3_assoc',type=int,default=8)
parser.add_argument('--l3_waymask_set', type=str, help="like ff-ff00")
parser.add_argument('--enable-clint-sets',type=str,default=None)
parser.add_argument('--cpt-json',type=str,default="/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/resources/simpoint_cpt_desc/06_max_path.json")
args = parser.parse_args()

print(args)

path_file = args.cpt_json

with open(path_file) as f:
    benchmark_cpt_file = json.load(f)


gcpt_bin_path = '/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/NEMU/resource/gcpt_restore/build/gcpt-ori.bin'


# ==================  Basics  ==================
binary = os.path.join(ff_base,'build/RISCV/gem5.opt')
outdir = os.path.join(ff_base,'log/{}').format(args.benchmark) if args.output=='' else args.output
outopt = '--outdir='+outdir
debugf = '--debug-flag='+ args.debug_flag if args.debug_flag else ''
fspy   = os.path.join(ff_base,'configs/example/fs.py')

# ==================  Options  ==================
opt = []
opt.append('--xiangshan-system')

if args.nohype:
    opt.append('--nohype')
else:
    assert(args.np == 1)

# opt.append('--enable-difftest')
# opt.append('--difftest-ref-so=~/lvna/5g/nemu_diff/riscv64-nemu-interpreter-so')

if args.enable_archdb:
    opt.append('--enable-arch-db')
    opt.append('--arch-db-fromstart=False')
    db_file = os.path.join(outdir,"hm.db")
    opt.append(f'--arch-db-file={db_file}')

opt.append('--num-cpus={}'.format(args.np))
opt.append('--cpu-type=DerivO3CPU')
opt.append('--bp-type=LTAGE')
# opt.append('--mem-type=DRAMsim3')
opt.append('--mem-type=DDR4_2400_16x4')
opt.append('--mem-size={}GB'.format(args.np * 8))
# opt.append('--mem-channels=2')

opt.append('--cacheline_size=64')
opt.append('--caches --l2cache --l3cache')
opt.append('--l1i_size=128kB --l1i_assoc=8')
opt.append('--l1d_size=128kB --l1d_assoc=8')

opt.append('--l2_size=1MB --l2_assoc=8')
opt.append(f'--l3_size={args.l3_assoc}MB --l3_assoc={args.l3_assoc}')
# opt.append('--l1d-hwp-type=StridePrefetcher')
opt.append('--l2-hwp-type=BOPPrefetcher')


if args.l3_waymask_set:
    opt.append('--l3_waymask_set="{}"'.format(args.l3_waymask_set))

gcpt_all = [benchmark_cpt_file[bm] for bm in args.benchmark.split("-")]

# use "" around multiple paths connnected by ;
opt.append('--generic-rv-cpt=' + '"' + ";".join(gcpt_all) + '"')
opt.append('--gcpt-restorer=' + gcpt_bin_path)

opt.append('--warmup-insts-no-switch={}'.format(args.warmup))
if args.insts_afterwarm:
    opt.append('--insts-after-allwarm={}'.format(args.insts_afterwarm))
# opt.append('-I={}'.format(args.insts))

# opt.append('--mmc-img=/nfs/home/zhangchuanqi/lvna/new_micro/tail-sd.img')

# ==================  RUN  ==================
cmd = [binary, outopt, debugf, fspy]
cmd.extend(opt)
print(" ".join(cmd))
os.system(" ".join(cmd))
os.system("echo "+time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())+">"+outdir+"/timestamp")
