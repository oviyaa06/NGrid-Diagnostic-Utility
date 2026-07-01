# NGrid-Diagnostic-Utility
Problem statement

•	No unified view of service health across HMI and Core machines - teams relied on manual checks on each individual machine.
•	No way to detect if a process is running, stopped, or degraded without logging in locally to each machine.
•	No visibility into duplicate service instances or version mismatches across the two machines.
•	Resource issues (high CPU, memory exhaustion, disk pressure) were discovered only after system failures, with no proactive alerting.
•	Existing OS tools (Task Manager, Resource Monitor) are local-only, produce no structured data, and cannot span two machines simultaneously.

Proposed Solution
•	A centralized desktop monitoring utility is used to monitor both the HMI Machine and Core Machine from a single interface.
•	Each machine runs a lightweight background agent that collects CPU, RAM, Disk I/O, and process-related information.
•	Communication between the utility and machine agents is performed using gRPC for fast and efficient real-time data transfer.
•	The dashboard continuously updates system metrics, process status, graphs, and performance values every second.
•	Recording and profiling features allow monitoring data to be exported in CSV/Parquet format, while configuration files enable easy addition of new processes without code changes.
•	An integrated Analyze Module enables users to load recorded files, visualize historical performance trends, and filter data using custom time ranges.

Files in Code
What Each File Does
•	Utility.py acts as the main desktop GUI client, providing real-time monitoring of HMI and Core machines through interactive dashboards, live performance graphs, process status tracking, recording and profiling controls, and an integrated analysis module for visualizing historical monitoring data, filtering records by time range, and exporting results in CSV format.
•	agent.py, client.py, and monitor.proto handle communication and monitoring. The agent collects system/process statistics, the client manages gRPC connections, and the proto file defines the RPC services and message formats.
•	monitor_pb2.py and monitor_pb2_grpc.py are auto generated gRPC files created from monitor.proto; they define the message structures and communication methods used between the monitoring utility and machine agents.
•	PPC4.5.0.json and machine_details.json store configuration information such as machine IP addresses and the list of processes to be monitored, enabling the application to connect to machines and track the required services without code changes.

Which File Runs on Which Machine
•	agent.py runs on both the HMI and Core machines, collecting local system statistics and serving them through gRPC. 
•	Utility.py runs on the operator workstation and serves as the main monitoring interface, while client.py is used internally by the GUI to communicate with remote agents. 
•	PPC4.5.0.json and machine_details.json are stored on the operator workstation and provide machine connection settings and process-monitoring configurations.
•	agent.py, monitor_pb2_grpc.py and monitor_pb2.py should be present on the machine whose details we are going to monitor

Functionalities
•	Service Health Monitoring: Continuously monitors services on both HMI and Core machines through 1-second gRPC polling, providing real-time UP/DOWN status indicators and automatic offline detection.
•	System Resource Graphs: Displays live CPU, RAM, Disk I/O, Read, and Write metrics using interactive graphs with rolling historical data for real-time performance visualization.
•	Per-Process Statistics: Tracks individual process status, CPU usage, memory consumption, and disk activity, along with trend graphs to visualize process behaviour over time.
•	Recording (CSV Export): Records process metrics at one-second intervals within a specified time window and exports the collected data as a CSV file for later analysis.
•	Profiling (Parquet and Chart Export): Captures detailed system and process performance data, stores it in Parquet and CSV formats, and automatically generates performance charts for post-session evaluation.
•	gRPC Agent: Runs on monitored machines as a background service, collects system and process statistics using psutil, and serves the data through gRPC APIs.
•	Configuration and Centralized Monitoring: Uses JSON-based configuration files for machine and process settings, enabling centralized monitoring and easy deployment without modifying the source code.
•	Analyze Module: Loads previously recorded Parquet files and provides historical performance analysis through an interactive graphical interface.
•	Time-Based Data Filtering: Allows users to select custom start and end timestamps to filter monitoring records and focus on specific periods of interest.
•	Interactive Graph Visualization: Supports hover-based tooltips displaying exact metric values and clickable graph cards that open enlarged graph views for detailed inspection.
•	System and Process Analysis: Provides separate visualization of system-level metrics (CPU, RAM, Disk I/O) and process-level metrics for comprehensive performance investigation.
•	CSV Export from Analysis: Enables filtered historical data to be exported as CSV files for reporting, documentation, and external analysis.
•	Automatic Graph Generation: Generates graphical reports for recorded and profiled data, allowing users to review performance trends without requiring additional tools.
•	Historical Performance Investigation: Facilitates post-monitoring analysis of system behaviour and process activity using stored Parquet datasets and visual trend analysis.
