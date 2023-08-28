#!/usr/bin/env python3

import os
import argparse
import time
import json

ff_base = '/nfs/home/zhangchuanqi/lvna/for_xs/intgem5-lazycat'
need_clint_sd_works = ['imgdnn','moses','xapian','specjbb','sphinx']

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
parser.add_argument('--cache-type',choices=['oldinc','xs','goldencove','skylake',
                                            'goldencove24M','goldencove48M','goldencovelru'],
                    required=True)
parser.add_argument('--l3_assoc',type=int,default=8)
parser.add_argument('--l3_waymask_set', type=str, help="like ff-ff00")
parser.add_argument('--l3_qos_csvfile', type=str, default=None)
parser.add_argument('--l3_qos_grow_target', type=str, default=None)
parser.add_argument('--l3_qos_policy_set', type=str, default=None)
parser.add_argument('--qos-high-ids',type= str, default=None)
parser.add_argument("--insts-stop-event-afterwarm",type=int,default=None)
parser.add_argument("--insts-test-afterstop",type=int,default=None)
parser.add_argument("--start-qos-fromstart", action="store_true",
        help="start qos from start")
# parser.add_argument('--enable-clint-sets',type=str,default=None)
parser.add_argument('--cpt-json',type=str,default="/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/resources/simpoint_cpt_desc/06_max_path.json")
args = parser.parse_args()

print(args)

path_file = args.cpt_json

with open(path_file) as f:
    benchmark_cpt_file = json.load(f)


gcpt_notie_bin_path = '/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-sdcard-cpt/resource/gcpt_restore/build/gcpt-disable-tie.bin'
gcpt_tie_bin_path = '/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-sdcard-cpt/resource/gcpt_restore/build/gcpt-enable-tie.bin'


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
    if args.start_qos_fromstart:
        opt.append('--start-qos-fromstart')
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
# opt.append('--mem-type=DDR4_2400_16x4')
# opt.append('--mem-type=DDR3_1600_8x8')
opt.append('--mem-size={}GB'.format(args.np * 8))
# opt.append('--mem-channels=2')

opt.append('--cacheline_size=64')
opt.append('--caches --l2cache --l3cache')

#set memory and caches
if args.cache_type == 'oldinc':
    opt.append('--l1i_size=32kB --l1i_assoc=4')
    opt.append('--l1i_tag_latency=1')
    opt.append('--l1i_data_latency=2')
    opt.append('--l1i_response_latency=1')
    opt.append('--l1i-rp-type=TreePLRURP')

    opt.append('--l1d_size=32kB --l1d_assoc=4')
    opt.append('--l1d_tag_latency=1')
    opt.append('--l1d_data_latency=2')
    opt.append('--l1d_response_latency=1')
    opt.append('--l1d-rp-type=TreePLRURP')
    
    opt.append('--l2_size=256kB --l2_assoc=8')
    opt.append('--l2_tag_latency=1')
    opt.append('--l2_data_latency=4')
    opt.append('--l2_response_latency=1')
    opt.append('--l2-rp-type=TreePLRURP')
    
    opt.append(f'--l3_size={args.l3_assoc * 512}kB --l3_assoc={args.l3_assoc}')
    opt.append('--l3_tag_latency=8')
    opt.append('--l3_data_latency=27')
    opt.append('--l3_response_latency=8')
    # opt.append('--l3_size=8MB --l3_assoc=16')
    
    opt.append('--l2-clusivity=mostly_incl')
    opt.append('--l3-clusivity=mostly_incl')

    opt.append('--mem-type=DDR3_1600_8x8')

    opt.append('--cpu-clock=2.66GHz')

elif 'goldencove' in args.cache_type:
    #l1i
    opt.append('--l1i_size=32kB --l1i_assoc=8')
    opt.append('--l1i_tag_latency=2')
    opt.append('--l1i_data_latency=3')
    opt.append('--l1i_response_latency=2')
    opt.append('--l1i_mshrs=16')
    if 'lru' in args.cache_type:
        opt.append('--l1i-rp-type=LRURP')
    else:
        opt.append('--l1i-rp-type=HPRRIPRP')
    #l1d
    opt.append('--l1d_size=48kB --l1d_assoc=12')
    opt.append('--l1d_tag_latency=2')
    opt.append('--l1d_data_latency=3')
    opt.append('--l1d_response_latency=2')
    opt.append('--l1d_mshrs=16')
    if 'lru' in args.cache_type:
        opt.append('--l1d-rp-type=LRURP')
    else:
        opt.append('--l1d-rp-type=HPRRIPRP')
    #l2
    opt.append('--l2_size=1280kB --l2_assoc=10')
    opt.append('--l2_tag_latency=4')
    opt.append('--l2_data_latency=9')
    opt.append('--l2_response_latency=4')
    opt.append('--l2_mshrs=48')
    if 'lru' in args.cache_type:
        opt.append('--l2-rp-type=LRURP')
    else:
        opt.append('--l2-rp-type=HPRRIPRP')
    #l3
    if args.cache_type == 'goldencove24M':
        opt.append(f'--l3_size={args.l3_assoc * 2048}kB --l3_assoc={args.l3_assoc}')
    elif args.cache_type == 'goldencove48M':
        opt.append(f'--l3_size={args.l3_assoc * 4096}kB --l3_assoc={args.l3_assoc}')
    else:
        opt.append(f'--l3_size={args.l3_assoc * 1024}kB --l3_assoc={args.l3_assoc}')
    opt.append('--l3_tag_latency=10')
    opt.append('--l3_data_latency=51')
    opt.append('--l3_response_latency=10')

    opt.append('--l2-clusivity=mostly_incl')
    opt.append('--l3-clusivity=mostly_excl')

    opt.append('--mem-type=DDR4_2400_16x4')

    opt.append('--cpu-clock=3.2GHz')

elif args.cache_type == 'skylake':
    #l1i
    opt.append('--l1i_size=32kB --l1i_assoc=8')
    opt.append('--l1i_tag_latency=2')
    opt.append('--l1i_data_latency=3')
    opt.append('--l1i_response_latency=2')
    opt.append('--l1i-rp-type=TreePLRURP')
    #l1d
    opt.append('--l1d_size=32kB --l1d_assoc=8')
    opt.append('--l1d_tag_latency=2')
    opt.append('--l1d_data_latency=3')
    opt.append('--l1d_response_latency=2')
    opt.append('--l1d-rp-type=TreePLRURP')
    #l2
    opt.append('--l2_size=1MB --l2_assoc=16')
    opt.append('--l2_tag_latency=4')
    opt.append('--l2_data_latency=9')
    opt.append('--l2_response_latency=4')
    opt.append('--l2-rp-type=TreePLRURP')
    #l3
    opt.append(f'--l3_size={args.l3_assoc * 512}kB --l3_assoc={args.l3_assoc}')
    opt.append('--l3_tag_latency=10')
    opt.append('--l3_data_latency=24')
    opt.append('--l3_response_latency=10')

    opt.append('--l2-clusivity=mostly_incl')
    opt.append('--l3-clusivity=mostly_excl')

    opt.append('--mem-type=DDR4_2400_16x4')

    opt.append('--cpu-clock=3.2GHz')

else:
    opt.append('--l1i_size=64kB --l1i_assoc=8')
    opt.append('--l1d_size=64kB --l1d_assoc=8')

    opt.append('--l2_size=1MB --l2_assoc=8')
    opt.append(f'--l3_size={args.l3_assoc}MB --l3_assoc={args.l3_assoc}')
    opt.append('--mem-type=DDR4_2400_16x4')

# opt.append('--l1d-hwp-type=StridePrefetcher')
opt.append('--l2-hwp-type=BOPPrefetcher')

if 'lru' in args.cache_type:
    opt.append('--l3-rp-type=LRURP')
else:
    opt.append('--l3-rp-type=HPRRIPRP')

if args.l3_waymask_set:
    opt.append('--l3_waymask_set="{}"'.format(args.l3_waymask_set))
if args.l3_qos_csvfile:
    opt.append('--qos-policy-csvfile="{}"'.format(args.l3_qos_csvfile))
if args.l3_qos_grow_target:
    opt.append('--qos-policy-grow-target={}'.format(args.l3_qos_grow_target))
    
if args.qos_high_ids:
    opt.append('--qos-high-ids="{}"'.format(args.qos_high_ids))

if args.l3_qos_policy_set:
    opt.append('--l3-qos-policy={}'.format(args.l3_qos_policy_set))
elif args.l3_qos_csvfile:
    opt.append('--l3-qos-policy=MaskCsvPolicy')

gcpt_all = [benchmark_cpt_file[bm] for bm in args.benchmark.split("-")]

# use "" around multiple paths connnected by ;
opt.append('--generic-rv-cpt=' + '"' + ";".join(gcpt_all) + '"')

#enable clint for tailbench bms
bm_all = [bm for bm in args.benchmark.split("-")]
lint_enables = []
for i,bm in enumerate(bm_all):
    if bm in need_clint_sd_works:
        lint_enables.append(str(i))
lint_enable_str = "-".join(lint_enables)
if len(lint_enables) > 0:
    opt.append('--enable-clint-sets={}'.format(lint_enable_str))
    opt.append('--gcpt-restorer=' + gcpt_tie_bin_path)
else:
    opt.append('--gcpt-restorer=' + gcpt_notie_bin_path)

opt.append('--warmup-insts-no-switch={}'.format(args.warmup))
if args.insts_afterwarm:
    opt.append('--insts-after-allwarm={}'.format(args.insts_afterwarm))
if args.insts_stop_event_afterwarm:
    opt.append('--insts-stop-event-afterwarm={}'.format(args.insts_stop_event_afterwarm))
if args.insts_test_afterstop:
    opt.append('--insts-test-afterstop={}'.format(args.insts_test_afterstop))
# opt.append('-I={}'.format(args.insts))

opt.append('--mmc-img=/nfs/home/share/zhangchuanqi/sd-imgs/full-tail-sd.img')

# ==================  RUN  ==================
cmd = [binary, outopt, debugf, fspy]
cmd.extend(opt)
print(" ".join(cmd))
os.system(" ".join(cmd))
os.system("echo "+time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())+">"+outdir+"/timestamp")
