import os
import subprocess
import time
import signal
import argparse

parser = argparse.ArgumentParser(description='Process some cores.')
parser.add_argument('-n','--nt', type=int, default=16)
parser.add_argument("--after-warmM", type=int, default=40)
args = parser.parse_args()

def mix_spec_run(workloads_dict, run_once_script, out_dir_path, warmup=50_000_000,
	after_warmM=1, threads=1, ncores=128):
	base_arguments = ["python3", run_once_script, '-W', str(warmup)]
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
	a = []
	for w in workloads_dict:
		d = {}
		d['-b'] = w
		d["--l3_waymask_set"] = work_load_dict[w]
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
					waymask_set = workload["--l3_waymask_set"]
					addition_cmd.append(f"--l3_waymask_set={waymask_set}")

					#modify est and out here
					result_path = os.path.join(out_dir_path, f"{workload_name}/hotcold")
					if not os.path.exists(result_path):
						os.makedirs(result_path, exist_ok=True)
					addition_cmd.append(f"-D={result_path}")		
					set_est_path = os.path.join(out_dir_path,f"{workload_name}/{waymask_set}/set_est")
					addition_cmd.append(f"--set_est_dir={set_est_path}")

					stdout_file = os.path.join(result_path, "stdout.log")
					stderr_file = os.path.join(result_path, "stderr.log")
					with open(stdout_file, "w") as stdout, open(stderr_file, "w") as stderr:
						run_cmd = base_arguments + addition_cmd
						cmd_str = " ".join(run_cmd)
						print(f"cmd {proc_count}: {cmd_str}")
						proc = subprocess.Popen(
							run_cmd, stdout=stdout, stderr=stderr, preexec_fn=os.setsid)
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
	log_dir = f"/nfs/home/zhangchuanqi/lvna/5g/ff-reshape/log/{args.after_warmM}x1M/"
	work_load_dict = {
		'mcf-omnetpp':'0x7f-0x80',
		'mcf-xalancbmk':'0x1f-0xe0',
		'mcf-sphinx3':'0x1-0xfe',
		'omnetpp-xalancbmk':'0x3-0xfc',
		'omnetpp-sphinx3':'0x1-0xfe',
	}
	mix_spec_run(work_load_dict,
	"/nfs/home/zhangchuanqi/lvna/5g/DirtyStuff/gem5tasks/mix_spec.py",
	out_dir_path = log_dir,
	ncores = args.nt,
	after_warmM=args.after_warmM)
