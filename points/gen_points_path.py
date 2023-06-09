import json
import os

from common.cpt_searcher import find_nemu_simpoint_cpts, find_nemu_simpoint_cpts_weights

def filter_max_weight(base_dir:str, input_dict=None):
    if input_dict is None:
        newSum = {}
    else:
        newSum = input_dict
    pathSum = find_nemu_simpoint_cpts(base_dir)
    weightSum = find_nemu_simpoint_cpts_weights(base_dir)
    for workload, point_weight in weightSum.items():
        max_weight = 0.0
        for point, weight in point_weight.items():
            if float(weight) > max_weight:
                max_weight = float(weight)
                newSum[workload] = pathSum[workload][int(point)]
    return newSum

# weight_file = "./resources/simpoint_cpt_desc/simpoints06.json"

# with open(weight_file) as f:
#     js = json.load(f)

# task_sum = find_nemu_simpoint_cpts('/nfs-nvme/home/share/checkpoints_profiles/nemu_take_simpoint_cpt_06/')

new_js = {}

filter_max_weight('/nfs-nvme/home/share/checkpoints_profiles/nemu_take_simpoint_cpt_17/', new_js)
filter_max_weight('/nfs/home/share/zhangchuanqi/nemu-mkcpt/cpts/outcptgz/gapbs/', new_js)
filter_max_weight('/nfs/home/share/zhangchuanqi/gcpt_cpts/tailbench-withsd-50M/', new_js)

with open('./resources/simpoint_cpt_desc/lazycat_17_gap_tailbench_path.json', 'w') as outf:
    json.dump(new_js, outf, indent=4)
