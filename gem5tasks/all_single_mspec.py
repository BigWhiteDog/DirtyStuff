from ast import arg
import os
import subprocess
import time
import signal
import argparse
import json


my_env = os.environ.copy()
my_env["LD_PRELOAD"] = '/nfs-nvme/home/share/debug/zhouyaoyang/libz.so.1.2.11.zlib-ng' + os.pathsep + my_env.get("LD_PRELOAD","")

json_path = "/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/resources/simpoint_cpt_desc/hwfinal.json"

parser = argparse.ArgumentParser(description='Process some cores.')
parser.add_argument('-n','--ncores', type=int, default=16)
parser.add_argument("--after-warmM", type=int, default=None)
parser.add_argument('-W','--warmup',type=int,default=20_000_000)
parser.add_argument('--notie',action='store_true',default=False)
args = parser.parse_args()

def single_mspec(workloads, run_once_script, out_dir_path, warmup=20_000_000,
	after_warmM=None, threads=1, ncores=128):
	base_arguments = ["python3", run_once_script, "--cpt-json", json_path, '-W', str(warmup), "--single_mode"]
	if after_warmM:
		base_arguments.extend(["--cycle_afterwarm",str(1_000_000*after_warmM)])
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
	# a = []
	# for w in workloads:
	# 	d = {}
	# 	d["-b"] = w
	# 	a.append(d)
	# 	for i in range(1, 16):
	# 		d = {}
	# 		d['-b'] = w
	# 		l_mask = (1 << i) - 1
	# 		r_mask = 0xffff ^ l_mask
	# 		masks = [l_mask,r_mask]
	# 		d["--l2_waymask_set"] = '-'.join([hex(s) for s in masks])
	# 		a.append(d)

	test_tti_len = [500_000*(2**i)for i in range(0,5)] + [100_000]
	# test_tti_len = [100_000]
	# generate new full workloads
	a = []
	for w in workloads:
		for tti_l in test_tti_len:
			d = {}
			d['-b'] = w
			d['--cycle_per_tti'] = str(tti_l)
			a.append(d)

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
					# waymask_set = workload.get("--l2_waymask_set","")
					# if len(waymask_set)>0:
					# 	addition_cmd.append(f"--l2_waymask_set={waymask_set}")
					# else:
					# 	waymask_set = 'nopart'
					# result_path = os.path.join(out_dir_path, f"{workload_name}/{waymask_set}")
					tti_len = workload['--cycle_per_tti']
					addition_cmd.append(f"--cycle_per_tti={tti_len}")
					result_path = os.path.join(out_dir_path, f"{workload_name}/{tti_len}")
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
	if args.after_warmM:
		log_dir = f"/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/{args.after_warmM}M/"
	else:
		log_dir = f"/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/full{args.warmup}/"

	with open(json_path) as f:
		work_dict = json.load(f)
	# task_loads = work_dict.keys()
	# task_loads = [f'bta{i}' for i in range()]
	task_loads = [f'hmmer_o3{i}' for i in range(2)] + [f'hmmer{i}' for i in range(3)]
	# task_loads = [f'hmmer_o2_retro{i}' for i in range(2)]
	single_mspec(task_loads,
	"/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/gem5tasks/mix_mspec.py",
	out_dir_path = log_dir,
	ncores = args.ncores,
	after_warmM=args.after_warmM,
	warmup=args.warmup)
