# imports
import time
import psutil
import grpc
from concurrent import futures # allow multiple client requests simultaneously
import monitor_pb2 # auto generated message class
import monitor_pb2_grpc # auto generated service class
PORT = 50051

# to store previous disk values of processes
prev_proc_disk: dict = {}
prev_sys_disk = None

# to implement the service defined in service SystemMonitor
class SystemMonitorServicer(monitor_pb2_grpc.SystemMonitorServicer):
    # entire system information
    def GetSystemStats(self, request, context):
        global prev_sys_disk 

        cpu_pct   = psutil.cpu_percent() # cpu utilization
        mem       = psutil.virtual_memory() # to return total ram, used ram, free ram
        cores     = psutil.cpu_count(logical=True) # logical cores
        ram_used  = round(mem.used  / (1024 ** 3), 2)
        ram_total = round(mem.total / (1024 ** 3), 2)

        disk_now = psutil.disk_io_counters() # to return read bytes and write bytes since system start up

        # calculate disk activity since the previous request rather than since system boot
        if prev_sys_disk:
            read_mb  = round((disk_now.read_bytes - prev_sys_disk.read_bytes)  / (1024 ** 2), 2)
            write_mb = round((disk_now.write_bytes - prev_sys_disk.write_bytes) / (1024 ** 2), 2)
        else:
            read_mb = write_mb = 0.0
        prev_sys_disk = disk_now
        io_mb = round(read_mb + write_mb, 2)

        return monitor_pb2.SystemStats(
            total_cpu       = cpu_pct,
            total_ram_used  = ram_used,
            total_ram       = ram_total,
            total_disk_io   = io_mb,
            total_read      = read_mb,
            total_write     = write_mb,
            logical_cores   = cores,
        )
    
    # process wise information
    def GetProcessStats(self, request, context):
        results = [] # to store process stats
        running_procs: dict[str, psutil.Process] = {} # to store found processes

        # iterate through all running processes and search for requested process names
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd = " ".join(p.info["cmdline"]) if p.info["cmdline"] else ""
                pname = p.info["name"] or ""
                for wanted in request.process_names:
                    if wanted.lower() in cmd.lower() or wanted.lower() == pname.lower():
                        running_procs[wanted] = p
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                continue

        for name in request.process_names:
            proc = running_procs.get(name)
            # if process is not running
            if proc is None:
                results.append(monitor_pb2.ProcessStat(name=name, running=False))
                continue
            # if process is running
            try:
                cpu = round(proc.cpu_percent(), 2)
                mem = round(proc.memory_info().rss / (1024 ** 2), 2)
                try:
                    disk_now = proc.io_counters()
                    # calculate process disk I/O between consecutive requests
                    if name in prev_proc_disk:
                        prev = prev_proc_disk[name]
                        read_mb  = round((disk_now.read_bytes  - prev.read_bytes)  / (1024 ** 2), 2)
                        write_mb = round((disk_now.write_bytes - prev.write_bytes) / (1024 ** 2), 2)
                    else:
                        read_mb = write_mb = 0.0
                    prev_proc_disk[name] = disk_now
                    io_mb = round(read_mb + write_mb, 2)
                except (psutil.AccessDenied, AttributeError):
                    read_mb = write_mb = io_mb = 0.0
                results.append(monitor_pb2.ProcessStat(
                    name       = name,
                    running    = True,
                    cpu        = cpu,
                    memory_mb  = mem,
                    disk_io    = io_mb,
                    read_mb    = read_mb,
                    write_mb   = write_mb,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                results.append(monitor_pb2.ProcessStat(name=name, running=False))

        return monitor_pb2.ProcessStatsList(processes=results)
    
# to start grpc server
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4)) # to create server with 4 worker threads (handle 4 requests simultaneously)
    monitor_pb2_grpc.add_SystemMonitorServicer_to_server(SystemMonitorServicer(), server) # to connect service class to server
    server.add_insecure_port(f"[::]:{PORT}") # to listen to port
    server.start()
    print(f"[agent] gRPC server listening on port {PORT}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()