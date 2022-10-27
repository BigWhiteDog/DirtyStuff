import json
import os

from common.cpt_searcher import find_nemu_simpoint_cpts

def find_nemu_simpoint_cpts(d: str):
    TaskSummary = {}
    for simpoint in os.listdir(d):
        segments = simpoint.split('_')
        inst_count = segments[-2]
        workload = segments[:-2]
        workload = '_'.join(workload)
        point_dir = os.path.join(d, simpoint)
        if not os.path.isdir(point_dir):
            continue
        if workload not in TaskSummary:
            TaskSummary[workload] = {}
        cpt = '0'
        cpt_dir = os.path.join(point_dir, cpt)
        if not os.path.isdir(cpt_dir):
            continue
        cpt_file = os.listdir(cpt_dir)[0]
        cpt_file = os.path.join(cpt_dir, cpt_file)
        assert os.path.isfile(cpt_file)

        TaskSummary[workload][int(inst_count)] = cpt_file
    return TaskSummary

def find_nemu_app_cpts(d: str,app: str='redis',prefix: str=''):
    TaskSummary = {}
    for point in os.listdir(d):
        point_dir = os.path.join(d, point)
        if not os.path.isdir(point_dir):
            continue
        cpt_files = os.listdir(point_dir)
        cpt_files.sort()
        cpt_file = cpt_files[0]
        cpt_file = os.path.join(point_dir, cpt_file)
        assert os.path.isfile(cpt_file)
        workload = prefix+app+point
        TaskSummary[workload] = cpt_file
    return TaskSummary



weight_file = "./resources/simpoint_cpt_desc/simpoints06.json"

with open(weight_file) as f:
    js = json.load(f)

task_sum = find_nemu_simpoint_cpts('/nfs-nvme/home/share/checkpoints_profiles/nemu_take_simpoint_cpt_06/')

new_js = {}
for workload, weights in js.items():
    max_weight = 0.0
    for point, weight in weights.items():
        if float(weight) > max_weight:
            max_weight = float(weight)
            new_js[workload] = task_sum[workload][int(point)]

redis_sum = find_nemu_app_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/NEMU/redis_cpt/10M/get_loop',app='redis',prefix='get_')
new_js.update(redis_sum)

redis_sum = find_nemu_app_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/NEMU/redis_cpt/10M/redis_after_warm',app='redis',prefix='user_')
new_js.update(redis_sum)

xapian_sum = find_nemu_app_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/NEMU/xapian_cpt/50M/test_500',app='xapian',prefix='500_')
new_js.update(xapian_sum)

npb_ft = find_old_nemu_app_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/npb',app='npbftA')
new_js.update(npb_ft)

with open('./resources/simpoint_cpt_desc/06_max_redis_path.json', 'w') as outf:
    json.dump(new_js, outf, indent=4)
