# Workstation memory and Serena process trees

Status: Resolved by authorized process cleanup; no TradingAgents code change
Owner: Codex coordinator
Observed: 30 October 2026

## Reproduction and attribution

The user reported approximately 32 GB of workstation memory use while running
the desk. Real Windows process and memory samples showed about 34 GiB used
across the machine. The installed TradingAgents process tree accounted for
approximately 2.38 GiB of working-set memory: the desktop host, desk service,
Nautilus worker, local Laya worker and their consoles. Its private committed
memory was approximately 4.15 GiB, a different measure from resident memory.

Five busy Node language-server processes consumed approximately five logical
CPU cores in the observed samples. Their commands and parent chains identified
Serena. This evidence did not establish a TradingAgents memory leak.

## Action and observed result

The user explicitly authorized stopping Serena. The coordinator terminated
only verified Serena roots and their descendant servers, including a separate
older Serena Python tree. A subsequent scan found no Serena executable or
Python root, and all five previously busy Node processes were absent.
Available physical memory increased by approximately 10 GiB between samples.
The trading app and unrelated tools were left running during that cleanup.
No installation or configuration change was made.

Remaining Node processes were identified as Codex, browser controls and other
tool servers. The app's largest Python worker was its local language service,
approximately 1.88 GiB resident and idle at the later sample. The desk service
and native engine each used approximately 0.24 GiB resident. These observations
answer the process-ownership question; they do not prove every remaining tool
is optimally configured or establish long-term memory behavior.

## Limits and evidence

Working sets can contain shared pages. The before/after whole-machine memory
change is an observation, not a controlled attribution of every released byte.
No benchmarks, synthetic checks, automated tests or app source changes were
used for this investigation.

Sanitized measurements and action record:
`C:/src/printer/.local/strategy-memory-investigation-20261030.json`.
