# Recovering Owned Containers from Interrupted Native Work

bw-0437. Shared `execute()` saves an ownership journal before starting Docker work. From the original output path on the same Mac, it can verify and recover only the stopped worker's container. Existing normal/timeout cleanup uses the same ownership checks. Firmware, board, observation, and GPU policies were not changed.

## Defect confirmed and change

The previous helper generated a random name and called `docker rm` in `finally`. When SIGTERM was sent to the worker after actual Renode was ready, the worker exited with −15 but the container continued running. `finally` did not execute, and there was no external record of the owned name for precise recovery. The reproduction preserved the name with an observer that returned the UUID unchanged; after confirmation, only that ID was cleaned up.

After the change, `<tag>.process.json` atomically stores token, container name, output path, owner PID/host, and cleanup status. Records with the same name are not overwritten; a separate token suffix is used. Docker receives token and original-path labels too. The entire container list is not deleted and objects owned by other tasks are not cleaned up.

## Usage

After the worker has stopped, run from the original output path where the journal was created. The recovery tool uses Python's standard library and the Docker CLI.

```sh
python3 tools/native_process_recovery.py \
  "$CAPTURE/renode.process.json"
```

It rejects recovery while the owning worker is alive. If a PID was reused or status is ambiguous and appears alive, do not arbitrarily terminate another process. Journals from another host or moved elsewhere are also rejected. The tool has no force option to bypass protections.

Docker inspect checks name, token, and output path, and deletion uses only the verified immutable container ID. Even if the same name is reused after inspection, the new object is not deleted. An already absent object is idempotent success. A completed journal is not rewritten on recheck, preserving pinned capture hashes.

If the Docker daemon cannot be checked or deletion/ownership checks fail, success is not reported. Available errors and `cleanup-failed` status are retained, and the same journal can be checked again once the daemon is available. Docker service and other work are not automatically restarted.

## Actual verification

- Actual Renode readiness marker followed by SIGTERM/SIGKILL: reject recovery while owner is alive → confirm worker termination/container remains → recover that ID → second recovery with identical journal bytes.
- Actual Renode timeout: retained readiness log and TimeoutExpired and removed the task container.
- **Stopped test object** with another token label: recovery rejected it and preserved the object. This was not a test manipulating another user's actual container. It was subsequently cleaned up using the test-owned ID.
- Normal Renode version output and synthetic shell exit 7: preserved original output/failure and cleaned up the container.
- Additional SIGTERM control: recorded the owning worker's actual child PID and confirmed the host Docker client was also no longer running after recovery.

Nine unit tests passed covering ownership, different labels/hosts, moved journals, invalid PID/schema, duplicate tag preservation, daemon errors, immutable-ID deletion, and idempotence. The unavailable-daemon control was a unit mock; the actual Docker service was not stopped. Existing execution-lifetime 8, runtime CLI 9, and display 9 checks also passed.

An actual stock24 RGB-zero ARM candidate was run once through the shared display CLI; it passed 20 candidate checks and comparison with existing predeclared expectations. The new journal was `removed` and remained byte-identical after recovery CLI recheck. Job metadata was not mixed into CPU/display assessment. This single regression does not certify every firmware or interruption point.

Commands, prior-defect reproduction, actual inspect, worker/child termination, rejections, logs, unit/integration reports, and frozen source are retained in private `simulator/native-process-recovery-research-01/`. No physical access, writes, subagent, or external publication occurred.

## Position in the overall objective

The behavior required for E16 interrupted-work recovery was implemented and verified. E16 as a whole remains incomplete, including installation in a new environment and missing-asset guidance. E06 retains the E05 required-initialization dependency identified by the existing audit, so the same idle/reset variations were not repeated. Natural GAF and full main/UI also remain incomplete. Acceptance wording, denominator, and completion status were not changed; overall progress remains 9/16 = 56.25%.
