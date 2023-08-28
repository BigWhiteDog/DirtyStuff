import itertools
import os
import subprocess
import time
import signal
import argparse
import json
import math

import itertools

my_env = os.environ.copy()
my_env["LD_PRELOAD"] = '/nfs-nvme/home/share/debug/zhouyaoyang/libz.so.1.2.11.zlib-ng' + os.pathsep + my_env.get("LD_PRELOAD","")

json_path = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-dirtystuff/resources/simpoint_cpt_desc/lazycat_17_gap_tailbench_path.json"
script_path = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-dirtystuff/gem5tasks/mix-setconf/xs_mixspec.py"

parser = argparse.ArgumentParser(description='Process some cores.')
parser.add_argument('-n','--ncores', type=int, default=16)
parser.add_argument('--n-simcores', type=int, default=4)
parser.add_argument('-W','--warmup',type=int,default=50_000_000)
parser.add_argument('-A','--insts_afterwarm',type=int,default=50_000_000)
parser.add_argument('--run-types',
		    choices=['vanilla','fullgrow','growpart','overlap'],
			required=True)
parser.add_argument('--grow-policy', type=str, required=True,
		    choices=['RealOneLessPolicy','NoGrowRealOneLessPolicy'])

parser.add_argument('-p','--part',type=int,required=False)

parser.add_argument('--cache-type',choices=['oldinc','xs','goldencove','skylake'],
                    required=True)
args = parser.parse_args()

def find_waymask_mspec(workloads_dict, run_once_script, out_dir_path,
	insts_afterwarm,
 threads=1, ncores=128):
	base_arguments = ["python3", run_once_script, "--cpt-json", json_path,
	 '-W', str(args.warmup),
	 f'-A={insts_afterwarm}',
	 f'--np={args.n_simcores}',
	 '--start-qos-fromstart',
	 '--qos-high-ids=0-1',
	 '--nohype']
	# base_arguments.append('--enable_archdb')
	base_arguments
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

	#set assoc and type
	all_set = use_conf['all_set']
	ass = use_conf['max_assoc']
	base_arguments.append(f'--cache-type={args.cache_type}')
	base_arguments.append(f'--l3_assoc={ass}')

	# generate new full workloads
	all_mask = (1<<ass) -1
	a = []
	full_grow_parts = 64
	onepart = 16
	grow_step = 2
	for w in workloads_dict:
		d = {}
		d["-b"] = w
		# if (args.run_types == 'vanilla'):
		# 	a.append(d) #nopart

		d_waypart = d.copy()
		w0h = workloads_dict[w]['highways0']
		w1h = workloads_dict[w]['highways1']
		high_0_mask = (1 << w0h) - 1
		high_1_mask = ((1 << w1h) - 1) << w0h
		low_r_mask = all_mask ^ (high_0_mask | high_1_mask)
		masks = [high_0_mask,high_1_mask,low_r_mask,low_r_mask]
		d_waypart["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
		d_waypart['highways0'] = w0h
		d_waypart['highways1'] = w1h
		if (args.run_types == 'vanilla'):
			a.append(d_waypart) #vanilla way partition

		if (args.run_types == 'vanilla'):
			overlap_0_mask = 1 << (w0h - 1)
			overlap_1_mask = 1 << (w0h + w1h -1)
			overlap_0_low_r_mask = overlap_0_mask | low_r_mask
			overlap_1_low_r_mask = overlap_1_mask | low_r_mask
			overlap_01_low_r_mask = overlap_0_mask | overlap_1_mask | low_r_mask
			
			masks = [high_0_mask,high_1_mask, overlap_0_low_r_mask, overlap_0_low_r_mask]
			d_overlap_part0 = d_waypart.copy()
			d_overlap_part0["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
			d_overlap_part0['l3_qos_policy_set'] = 'Overlap0OnePolicy'
			a.append(d_overlap_part0)

			masks = [high_0_mask,high_1_mask, overlap_1_low_r_mask, overlap_1_low_r_mask]
			d_overlap_part1 = d_waypart.copy()
			d_overlap_part1["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
			d_overlap_part1['l3_qos_policy_set'] = 'Overlap1OnePolicy'
			a.append(d_overlap_part1)

			masks = [high_0_mask,high_1_mask, overlap_01_low_r_mask, overlap_01_low_r_mask]
			d_overlap_part01 = d_waypart.copy()
			d_overlap_part01["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
			d_overlap_part01['l3_qos_policy_set'] = 'Overlap01OnePolicy'
			a.append(d_overlap_part01)

		full_t = list(range(grow_step, full_grow_parts+1, grow_step))
		if (args.run_types == 'growpart'):
			p = args.part
			assert(p*onepart >= 0 and p*onepart < full_grow_parts)
			runt = full_t[p*onepart: (p+1)*onepart]
		elif (args.run_types == 'fullgrow'):
			runt = full_t
		
		if (args.run_types == 'growpart') or (args.run_types == 'fullgrow'):
			for i in runt:
				d_growpart = d_waypart.copy()
				d_growpart['l3_qos_policy_set'] = args.grow_policy
				w0target = math.ceil(all_set / full_grow_parts * workloads_dict[w]['grow_target0'])
				w1target = math.ceil(all_set / full_grow_parts * i)
				d_growpart['grow_target'] = '-'.join([str(w0target), str(w1target)])
				d_growpart['full_grow_portion'] = f'{i}in{full_grow_parts}'
				a.append(d_growpart)

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
					highways = workload.get("highways0",0)
					if highways > 0:
						addition_cmd.append(f"--l3_waymask_set={workload['l3_waymask_set']}")
						if 'l3_qos_policy_set' in workload:
							policy_name = workload['l3_qos_policy_set']
							if 'Overlap' in policy_name:
								highways = f"{highways}-{workload['l3_qos_policy_set']}"
							else:
								addition_cmd.append(f"--l3_qos_policy_set={workload['l3_qos_policy_set']}")
								highways = f"{highways}-{workload['l3_qos_policy_set']}"
								if ('grow_target' in workload ):
									addition_cmd.append(f"--l3_qos_grow_target={workload['grow_target']}")
								if ('full_grow_portion' in workload):
									highways += f"fullgrow{workload['full_grow_portion']}"
					if highways == 0:
						highways = 'nopart'
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
	cache_type = args.cache_type

	conf_json_base_dir = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-data_proc/set_analyze/conf-json"
	conf_json_name = f"conf_{cache_type}_tailbm50M.json"
	select_json = os.path.join(conf_json_base_dir, conf_json_name)
	with open(select_json,'r') as f:
		global use_conf
		use_conf = json.load(f)
	if use_conf is None:
		exit(255)

	nsimc = args.n_simcores
	bm_json_name = f"benchs_2hp_{nsimc}_{cache_type}_tailbm50M.json"
	bm_json = os.path.join(conf_json_base_dir , bm_json_name)
	with open(bm_json,'r') as f:
		use_bm = json.load(f)
	if use_bm is None:
		exit(255)

	work_pairs = use_bm[f'{nsimc}bench']

	test_prefix = use_conf['test_prefix']
	perf_prefix = '95perf'

	waydict_format = 'cache_work_{}ways'

	# #log for 95% perf core0
	# csv_path_top = os.path.join(analyze_base_dir, f'{test_prefix}other/csv/min0way_{perf_prefix}')
	waydict_name = waydict_format.format(perf_prefix)
	waydict = use_conf[waydict_name]
	log_base_dir = f"/nfs/home/zhangchuanqi/lvna/for_xs/catlog"
	log_dir = os.path.join(log_base_dir, f"mix{nsimc}-2hp-{test_prefix}{perf_prefix}/")

	profiling_w0_grow_dict = use_conf['32_target_0.97_in64']
	
	target_workload = {}

	for wp in work_pairs:
		wlist = wp.split('-')
		w = wlist[0]
		w1 = wlist[1]
		opts_dict = {}
		opts_dict['highways0'] = waydict[w]
		opts_dict['highways1'] = waydict[w1]
		opts_dict['grow_target0'] = profiling_w0_grow_dict[w]
		target_workload[wp] = opts_dict

	find_waymask_mspec(target_workload,
	script_path,
	out_dir_path = log_dir,
	insts_afterwarm=args.insts_afterwarm,
	ncores = args.ncores)
