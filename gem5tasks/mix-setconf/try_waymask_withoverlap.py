import itertools
import os
import subprocess
import time
import signal
import argparse
import json

import itertools

from gem5tasks.cache_sensitive_names import *

my_env = os.environ.copy()
my_env["LD_PRELOAD"] = '/nfs-nvme/home/share/debug/zhouyaoyang/libz.so.1.2.11.zlib-ng' + os.pathsep + my_env.get("LD_PRELOAD","")

json_path = "/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/resources/simpoint_cpt_desc/06_max_path.json"
script_path = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-dirtystuff/gem5tasks/mix-setconf/xs_mixspec.py"

parser = argparse.ArgumentParser(description='Process some cores.')
parser.add_argument('-n','--ncores', type=int, default=16)
parser.add_argument('-W','--warmup',type=int,default=50_000_000)
parser.add_argument('-A','--insts_afterwarm',type=int,default=50_000_000)
args = parser.parse_args()

def find_waymask_mspec(workloads_dict, run_once_script, out_dir_path,
	insts_afterwarm,
 threads=1, ncores=128):
	base_arguments = ["python3", run_once_script, "--cpt-json", json_path,
	 '-W', str(args.warmup),
	 f'-A={insts_afterwarm}',
	 '--np=2',
	 '--start-qos-fromstart',
	 '--nohype']
	# base_arguments.append('--enable_archdb')
	proc_count, finish_count = 0, 0
	max_pending_proc = ncores // threads
	pending_proc, error_proc = [], []
	free_cores = list(range(max_pending_proc))
	# skip CI cores
	ci_cores = []  # list(range(0, 64))# + list(range(32, 48))
	for core in list(map(lambda x: x // threads, ci_cores)):
		if core in free_cores:
			free_cores.remove(core)
			max_pending_proc -= 1
	print("Free cores:", free_cores)

	# generate new full workloads
	ass = 8
	all_mask = (1<<ass) -1
	a = []
	for w in workloads_dict:
		d = {}
		d["-b"] = w
		# a.append(d)

		d_waypart = d.copy()
		# i equal to ways for high priority
		i = workloads_dict[w]['highways']
		high_l_mask = (1 << i) - 1
		low_r_mask = all_mask ^ high_l_mask

		overlap_mask = 1 << (i - 1)
		low_r_mask |= overlap_mask

		masks = [high_l_mask,low_r_mask,low_r_mask,low_r_mask]
		d_waypart["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
		d_waypart["highways"] = i
		d_waypart['l3_qos_policy_set'] = 'OverlapOnePolicy'
		a.append(d_waypart)

	workloads = a

	try:
		while len(workloads) > 0 or len(pending_proc) > 0:
			has_pending_workload = len(workloads) > 0 and len(
				pending_proc) >= max_pending_proc
			has_pending_proc = len(pending_proc) > 0
			if has_pending_workload or has_pending_proc:
				finished_proc = list(
					filter(lambda p: p[1].poll() is not None, pending_proc))
				for workload, proc, core in finished_proc:
					print(f"{workload} has finished")
					pending_proc.remove((workload, proc, core))
					free_cores.append(core)
					if proc.returncode != 0:
						print(
							f"[ERROR] {workload} exits with code {proc.returncode}")
						error_proc.append(workload)
						continue
					finish_count += 1
				if len(finished_proc) == 0:
					time.sleep(1)
			can_launch = max_pending_proc - len(pending_proc)
			for workload in workloads[:can_launch]:
				if len(pending_proc) < max_pending_proc:
					allocate_core = free_cores[0]
					addition_cmd = []
					workload_name = workload['-b']
					addition_cmd.append(f"-b={workload_name}")
					highways = workload.get("highways",0)
					if highways > 0:
						addition_cmd.append(f"--l3_waymask_set={workload['l3_waymask_set']}")
						highways = f"{highways}-{workload['l3_qos_policy_set']}"
					if highways == 0:
						assert(0)
					result_path = os.path.join(out_dir_path,f'{workload_name}', f"l3-{highways}")
					if not os.path.exists(result_path):
						os.makedirs(result_path, exist_ok=True)
					addition_cmd.append(f"-D={result_path}")
					stdout_file = os.path.join(result_path, "stdout.log")
					stderr_file = os.path.join(result_path, "stderr.log")
					with open(stdout_file, "w") as stdout, open(stderr_file, "w") as stderr:
						run_cmd = base_arguments + addition_cmd
						cmd_str = " ".join(run_cmd)
						print(f"cmd {proc_count}: {cmd_str}")
						proc = subprocess.Popen(
							run_cmd, stdout=stdout, stderr=stderr, preexec_fn=os.setsid, env=my_env)
						time.sleep(0.5)
					pending_proc.append((workload, proc, allocate_core))
					free_cores = free_cores[1:]
					proc_count += 1
			workloads = workloads[can_launch:]
	except KeyboardInterrupt:
		print("Interrupted. Exiting all programs ...")
		print("Not finished:")
		for i, (workload, proc, _) in enumerate(pending_proc):
			os.killpg(os.getpgid(proc.pid), signal.SIGINT)
			print(f"  ({i + 1}) {workload}")
		print("Not started:")
		for i, workload in enumerate(workloads):
			print(f"  ({i + 1}) {workload}")
	if len(error_proc) > 0:
		print("Errors:")
		for i, workload in enumerate(error_proc):
			print(f"  ({i + 1}) {workload}")


if __name__ == '__main__':
	analyze_base_dir = '/nfs/home/zhangchuanqi/lvna/5g/gem5_data_proc/set_analyze'
	use_conf = conf_50M
	insts_afterwarm = 50_000_000
	test_prefix = use_conf['test_prefix']
	perf_prefix = '95perf'

	waydict_format = 'cache_work_{}ways'

	#log for 95% perf core0
	csv_path_top = os.path.join(analyze_base_dir, f'{test_prefix}other/csv/min0way_{perf_prefix}')
	waydict_name = waydict_format.format(perf_prefix)
	waydict = use_conf[waydict_name]
	log_dir = f"/nfs/home/zhangchuanqi/lvna/for_xs/catlog/mix2-qosfromstart-core0-{test_prefix}{perf_prefix}/"
	
	target_workload = {}

	for w in waydict:
		# if w not in ['mcf','xalancbmk']:
		# 	continue
		for w1 in waydict:
			combine_work = '-'.join([w,w1])
			opts_dict = {}
			opts_dict['csv_path'] = os.path.join(csv_path_top, f'{w}.csv')
			opts_dict['highways'] = min(waydict[w],7)
			target_workload[combine_work] = opts_dict

	find_waymask_mspec(target_workload,
	"/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/gem5tasks/mix-setconf/xs_mixspec.py",
	out_dir_path = log_dir,
	insts_afterwarm=insts_afterwarm,
	ncores = args.ncores)
