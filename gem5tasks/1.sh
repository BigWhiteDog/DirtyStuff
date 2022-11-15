#!/usr/bin/bash
works=$1
old_way=$2
out_dir=/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/40x1M/$works/cold
mkdir -p $out_dir
est_dir=/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/40x1M/$works/$old_way/set_est
python3 /nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/gem5tasks/mix_spec.py \
 -W 50000000 --cycle_afterwarm 40000000 \
 -b=$works --l3_waymask_set=$old_way \
 --set_est_dir=$est_dir \
 -D=$out_dir