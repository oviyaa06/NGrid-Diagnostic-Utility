# imports
import grpc
import monitor_pb2 # auto generated message class
import monitor_pb2_grpc # auto generated service class

PORT = 50051
TIMEOUT = 3.0 # maximum time to wait for a server response

channels: dict[str, grpc.Channel] = {} # stores active gRPC channels for each IP address
stubs: dict[str, monitor_pb2_grpc.SystemMonitorStub] = {} # stores reusable stub objects for each connected server

# returns a stub object used to call RPC methods on the remote server
def get_stub(ip: str) -> monitor_pb2_grpc.SystemMonitorStub:
    if ip not in stubs:
        channel = grpc.insecure_channel(f"{ip}:{PORT}") # to creates a communication path to the server
        channels[ip] = channel
        stubs[ip] = monitor_pb2_grpc.SystemMonitorStub(channel)
    return stubs[ip]

# used when connection fails
def reset_stub(ip: str) -> None:
    if ip in channels:
        try:
            channels[ip].close()
        except Exception:
            pass
        channels.pop(ip, None)
        stubs.pop(ip, None)

# to get cpu, memory, disk statistics from remote machine
def get_system_stats(ip: str) -> monitor_pb2.SystemStats | None:
    stub = get_stub(ip)
    try:
        return stub.GetSystemStats(monitor_pb2.SystemRequest(machine_name=ip),timeout=TIMEOUT,)
    except grpc.RpcError:
        reset_stub(ip)
        return None

# gets statistics for specific processes.
def get_process_stats(ip: str,process_names: list[str],) -> list[monitor_pb2.ProcessStat]:
    stub = get_stub(ip)
    try:
        response = stub.GetProcessStats(monitor_pb2.ProcessRequest(process_names=process_names),timeout=TIMEOUT,)
        return list(response.processes)
    except grpc.RpcError:
        reset_stub(ip)
        return []