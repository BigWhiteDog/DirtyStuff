from ast import arg
import itertools
import os
import random
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
parser.add_argument("--num_tti", type=int,required=True,default=None)
parser.add_argument('-W','--warmup',type=int,default=20_000_000)
args = parser.parse_args()

def mix_mspec(workloads, run_once_script, out_dir_path, threads=1, ncores=128):
	base_arguments = ["python3", run_once_script, "--cpt-json", json_path, '-W', str(args.warmup), '--np=4']
	base_arguments.extend(["--num_tti",str(args.num_tti)])
	# base_arguments.extend(["--l3_size_MB",str(4)])
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
	a = []
	for w in workloads:
		d = {}
		d['-b'] = w
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
					result_path = os.path.join(out_dir_path, f"{workload_name}")
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
	# log_dir = f"/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/new_hw_test/period{args.num_tti}/native/"
	log_dir = f"/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/new_hw_test/period{args.num_tti}/4MLLC_native/"
	with open('/nfs/home/zhangchuanqi/lvna/5g/gem5_data_proc/hw_stats_out_dir/period_hmmer_least.json') as f:
		work_dict = json.load(f)
	combined_workloads = work_dict.keys()
	# task_loads = [f'period_hmmer_o3_{i}' for i in range(4)] + [f'period_hmmer_o2_{i}' for i in range(3)]
	# combined_workloads = [ '-'.join(e) for e in itertools.permutations(task_loads,4)]
	# random.seed(1234)
	# random.shuffle(combined_workloads)
	mix_mspec(combined_workloads,
	"/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/gem5tasks/mix_mspec.py",
	out_dir_path = log_dir,
	ncores = args.ncores)
