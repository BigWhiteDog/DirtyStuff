import itertools
import os
import subprocess
import time
import signal
import argparse
import json

import itertools

my_env = os.environ.copy()
my_env["LD_PRELOAD"] = '/nfs-nvme/home/share/debug/zhouyaoyang/libz.so.1.2.11.zlib-ng' + os.pathsep + my_env.get("LD_PRELOAD","")

json_path = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-dirtystuff/resources/simpoint_cpt_desc/lazycat_17_gap_tailbench_path.json"
script_path = "/nfs/home/zhangchuanqi/lvna/5g/lazycat-dirtystuff/gem5tasks/mix-setconf/xs_mixspec.py"

parser = argparse.ArgumentParser(description='Process some cores.')
parser.add_argument('-n','--ncores', type=int, default=16)
parser.add_argument('-W','--warmup',type=int,default=50_000_000)
parser.add_argument('-A','--insts_afterwarm',type=int,default=50_000_000)
parser.add_argument('--cache-type',choices=['oldinc','xs','goldencove','skylake',
                                            'goldencove24M','goldencove48M','goldencoveLRU'],
                    required=True)
args = parser.parse_args()

def find_waymask_mspec(workloads, run_once_script, out_dir_path, threads=1, ncores=128):
	base_arguments = ["python3", run_once_script, "--cpt-json", json_path,
	 '-W', str(args.warmup),
	 f'-A={args.insts_afterwarm}',
	 '--np=1']
	base_arguments.append('--enable_archdb')
	base_arguments.append(f'--cache-type={args.cache_type}')
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
	if args.cache_type == 'oldinc':
		ass = 16
	elif 'goldencove' in args.cache_type:
		ass = 12
	elif args.cache_type == 'skylake':
		ass = 11
	else:
		ass = 8

	a = []
	for w in workloads:
		for i in range(1, ass+1):
			d = {}
			d['-b'] = w
			# i equal to ways for a workload
			d["highways"] = i
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
					highways = workload.get("highways")
					addition_cmd.append(f"--l3_assoc={highways}")
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
	log_dir = f"/nfs/home/zhangchuanqi/lvna/for_xs/catlog/tail_{args.cache_type}_50M-single-profiling/"
	# cs_works = ['xalancbmk','mcf','omnetpp','sphinx3']
	with open(json_path) as f:
		workloads_path_dict = json.load(f)
	target_workloads = workloads_path_dict.keys()
	# target_workloads = ['imgdnn','moses','xapian','specjbb','sphinx']
	find_waymask_mspec(target_workloads,
	script_path,
	out_dir_path = log_dir,
	ncores = args.ncores)
