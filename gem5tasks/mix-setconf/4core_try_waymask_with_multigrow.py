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
parser.add_argument('-W','--warmup',type=int,default=50_000_000)
parser.add_argument('-A','--insts_afterwarm',type=int,default=50_000_000)
parser.add_argument('--run-types',
		    choices=['vanilla','fullgrow','growpart','overlap'],
			required=True)
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
	 '--np=4',
	 '--start-qos-fromstart',
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
	for w in workloads_dict:
		d = {}
		d["-b"] = w
		if (args.run_types == 'vanilla'):
			a.append(d) #nopart

		d_waypart = d.copy()
		# i equal to ways for high priority
		i = workloads_dict[w]['highways']
		high_l_mask = (1 << i) - 1
		low_r_mask = all_mask ^ high_l_mask
		masks = [high_l_mask,low_r_mask,low_r_mask,low_r_mask]
		d_waypart["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
		d_waypart["highways"] = i
		if (args.run_types == 'vanilla'):
			a.append(d_waypart) #vanilla way partition

		# d_csvpart = d_waypart.copy()
		# d_csvpart['csv_path'] = workloads_dict[w]['csv_path']
		# a.append(d_csvpart)

		d_overlap_part = d_waypart.copy()
		overlap_mask = 1 << (i - 1)
		overlap_low_r_mask = overlap_mask | low_r_mask
		masks = [high_l_mask, overlap_low_r_mask, overlap_low_r_mask, overlap_low_r_mask]
		d_overlap_part["l3_waymask_set"] = '-'.join([hex(s) for s in masks])
		d_overlap_part['l3_qos_policy_set'] = 'OverlapOnePolicy'
		if (args.run_types == 'overlap'):
			a.append(d_overlap_part)

		full_t = list(range(1, full_grow_parts+1))
		if (args.run_types == 'growpart'):
			p = args.part
			assert(p*16 >= 0 and p*16 < full_grow_parts)
			runt = full_t[p*16: (p+1)*16]
		elif (args.run_types == 'fullgrow'):
			runt = full_t
		
		if (args.run_types == 'growpart') or (args.run_types == 'fullgrow'):
			for i in runt:
				d_growpart = d_waypart.copy()
				d_growpart['l3_qos_policy_set'] = 'RealOneLessPolicy'
				# d_growpart['l3_qos_policy_set'] = 'OneLessGrowTargetPolicy'
				d_growpart['grow_target'] = math.ceil(all_set / full_grow_parts * i)
				d_growpart['full_grow_portion'] = f'{i}in{full_grow_parts}'
				a.append(d_growpart)

		# d_growtarget = d_waypart.copy()
		# d_growtarget['l3_qos_policy_set'] = 'RealOneLessPolicy'
		# d_growtarget['grow_target'] = workloads_dict[w]['grow_target']
		# a.append(d_growtarget)
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
						if 'csv_path' in workload:
							#csv part
							addition_cmd.append(f"--l3_qos_csvfile={workload['csv_path']}")
							if 'l3_qos_policy_set' in workload:
								addition_cmd.append(f"--l3_qos_policy_set={workload['l3_qos_policy_set']}")
								highways = f"{highways}-{workload['l3_qos_policy_set']}"	
							else:
								highways = f'{highways}-csv'
						elif workload.get('l3_qos_policy_set',None) == 'OverlapOnePolicy':
							#overlap part
							highways = f"{highways}-{workload['l3_qos_policy_set']}"
						else:
							#not csv part
							if 'l3_qos_policy_set' in workload:
								addition_cmd.append(f"--l3_qos_policy_set={workload['l3_qos_policy_set']}")
								highways = f"{highways}-{workload['l3_qos_policy_set']}"
							if ('grow_target' in workload ):
								addition_cmd.append(f"--l3_qos_grow_target={workload['grow_target']}")
							if ('grow_portion' in workload):
								highways += f"grow{workload['grow_portion']}"
							elif ('full_grow_portion' in workload):
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
	conf_json_format = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-data_proc/set_analyze/conf-json/conf_{}_tailbm50M.json"
	select_json = conf_json_format.format(args.cache_type)
	with open(select_json,'r') as f:
		global use_conf
		use_conf = json.load(f)
	if use_conf is None:
		exit(255)

	bm_json_format = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-data_proc/set_analyze/conf-json/benchs_4_{}_tailbm50M.json"
	bm_json = bm_json_format.format(args.cache_type)
	with open(bm_json,'r') as f:
		use_bm = json.load(f)
	if use_bm is None:
		exit(255)

	work_pairs = use_bm['4bench']

	test_prefix = use_conf['test_prefix']
	perf_prefix = '95perf'

	waydict_format = 'cache_work_{}ways'

	# #log for 95% perf core0
	# csv_path_top = os.path.join(analyze_base_dir, f'{test_prefix}other/csv/min0way_{perf_prefix}')
	waydict_name = waydict_format.format(perf_prefix)
	waydict = use_conf[waydict_name]
	log_dir = f"/nfs/home/zhangchuanqi/lvna/for_xs/catlog/mix4-qosfromstart-core0-{test_prefix}{perf_prefix}/"
	
	target_workload = {}

	for wp in work_pairs:
		wlist = wp.split('-')
		w = wlist[0]
		opts_dict = {}
		# opts_dict['csv_path'] = os.path.join(csv_path_top, f'{w}.csv')
		# opts_dict['grow_target'] = use_conf['grow_last_target'][w]
		# opts_dict['grow_target_full'] = use_conf['grow_last_target_full'][w]
		opts_dict['highways'] = waydict[w]
		target_workload[wp] = opts_dict

	find_waymask_mspec(target_workload,
	script_path,
	out_dir_path = log_dir,
	insts_afterwarm=args.insts_afterwarm,
	ncores = args.ncores)
