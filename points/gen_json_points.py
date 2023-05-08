import json
import os

def find_nemu_simpoint_cpts(d:str):
    TaskSummary = {}
    for simpoint in os.listdir(d):
        segments = simpoint.split('_')
        if len(segments) < 3:
            continue
        try:
            inst_count = int(segments[-2])
            weight = float(segments[-1])
        except ValueError:
            continue
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

        TaskSummary[workload][inst_count] = cpt_file
    return TaskSummary

def find_nemu_simpoint_cpts_weights(d:str):
    weightSummary = {}
    for simpoint in os.listdir(d):
        segments = simpoint.split('_')
        if len(segments) < 3:
            continue
        try:
            inst_count = int(segments[-2])
            weight = float(segments[-1])
        except ValueError:
            continue
        workload = segments[:-2]
        workload = '_'.join(workload)
        point_dir = os.path.join(d, simpoint)
        if not os.path.isdir(point_dir):
            continue
        if workload not in weightSummary:
            weightSummary[workload] = {}
        weightSummary[workload][int(inst_count)] = float(weight)
    return weightSummary

def filter_only_weights(weights_dict:dict):
    newSum = {}
    for workload, weights in weights_dict.items():
        i = 0
        newSum[workload] = {}
        for k in sorted(weights, key=weights.get, reverse=True):
            if float(weights[k]) >= 0.01:
                newSum[workload][k] = weights[k]
    return newSum

def filter_weights(path_dict:dict,weights_dict:dict):
    newSum = {}
    for workload, weights in weights_dict.items():
        i = 0
        for k in sorted(weights, key=weights.get, reverse=True):
            if float(weights[k]) < 0.1:
                break
            newSum[f'{workload}_{i}'] = path_dict[workload][k]
            i+=1
    return newSum

new_js = {}

# mspec_task_sum = find_nemu_simpoint_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/mspec06')
# mspec_task_weight = find_nemu_simpoint_cpts_weights('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/mspec06')
# filterd_mspec_task = filter_weights(mspec_task_sum,mspec_task_weight)

# new_js.update(filterd_mspec_task)

# mspec_task_sum = find_nemu_simpoint_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/mspec')
# mspec_task_weight = find_nemu_simpoint_cpts_weights('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/mspec')
# filterd_mspec_task = filter_weights(mspec_task_sum,mspec_task_weight)

# new_js.update(filterd_mspec_task)


# npb_task_sum = find_nemu_simpoint_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/npb')
# npb_task_weight = find_nemu_simpoint_cpts_weights('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/npb')
# filterd_npb_task = filter_weights(npb_task_sum,npb_task_weight)

# new_js.update(filterd_npb_task)

gapbs_task_sum = find_nemu_simpoint_cpts('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/outcptgz/branchopt')
gapbs_task_weight = find_nemu_simpoint_cpts_weights('/nfs/home/zhangchuanqi/lvna/for_xs/xs-env/nemu-mkcpt/cpts/outcptgz/branchopt')
filtered_gapbs_task_weight = filter_only_weights(gapbs_task_weight)
new_js.update(filtered_gapbs_task_weight)
for w in filtered_gapbs_task_weight:
    print(w,sum(filtered_gapbs_task_weight[w].values()))

with open('./resources/simpoint_cpt_desc/branchopt.json', 'w') as outf:
    json.dump(new_js, outf, indent=4)
