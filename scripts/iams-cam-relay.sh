#!/bin/bash
# IAMS Camera Relay — persistent Reolink → Mac mediamtx RTSP pusher.
#
# Launched by the com.iams.cam-relay LaunchAgent installed by
# scripts/install-cam-relay.sh. Runs continuously while the Mac is awake.
#
# For each camera:
#   1. Pull RTSP from the Reolink on IAMS-Net
#   2. Push (no re-encode, -c copy) into localhost:8554/<stream_key> on the
#      Mac's mediamtx container (iams-mediamtx-onprem)
# Mediamtx then serves the stream to:
#   - admin portal WHEP (:8889/<key>/whep)
#   - api-gateway's frame_grabber (for attendance recognition)
#   - the VPS mediamtx (via mediamtx.onprem.yml's runOnReady outbound push)
#
# Failure handling: ffmpeg is wrapped in an infinite loop; if it exits for
# any reason (network blip, camera reboot, mediamtx container restart), we
# wait 3 s and reconnect. The wrapper script itself catches SIGTERM/SIGINT
# from launchd and kills all children cleanly so `launchctl unload` doesn't
# leave orphan ffmpegs.
#
# Adding/removing a camera: edit the CAMERAS array below and reinstall
# (scripts/install-cam-relay.sh).

set -u

# Hardcoded absolute path — launchd's PATH is minimal (no /opt/homebrew by
# default). `/opt/homebrew/bin/ffmpeg` is the Apple Silicon Homebrew path;
# Intel Homebrew uses `/usr/local/bin/ffmpeg` (not currently supported).
FFMPEG="/opt/homebrew/bin/ffmpeg"
FFPROBE="/opt/homebrew/bin/ffprobe"

if [ ! -x "${FFMPEG}" ]; then
  echo "FATAL: ffmpeg not found at ${FFMPEG}. Install via 'brew install ffmpeg'." >&2
  exit 1
fi
# ffprobe ships with ffmpeg via Homebrew. If missing, the watchdog loop
# below is skipped (the per-camera restart-on-exit path still works).
if [ ! -x "${FFPROBE}" ]; then
  echo "WARN: ffprobe not found at ${FFPROBE}. Watchdog disabled — stalled ffmpegs" \
       "that hold an ffmpeg PID alive without publishing will NOT be auto-kicked." >&2
fi

# Reolink credentials. Password is @Iams2026THESIS! which needs URL-encoding
# for the '@' and '!' characters: %40 and %21.
CAM_USER="admin"
CAM_PASS_ENC="%40Iams2026THESIS%21"

# Target mediamtx (localhost:8554 is the mapped port from the
# iams-mediamtx-onprem container).
MTX_HOST="localhost"
MTX_PORT="8554"

# Camera list. Format: "ip_address stream_key rtsp_path"
# - stream_key matches the `rooms.stream_key` column seeded by seed_data.py
#   (eb226, eb227 at the time of writing). The `-sub` siblings are admin-only
#   display streams that never leave the Mac (no VPS forwarding — see
#   deploy/mediamtx.onprem.yml).
# - rtsp_path: Reolink P340 serves `h264Preview_01_main` (HD ~2560×1440) and
#   `h264Preview_01_sub` (~640×360 or 896×512).
#   MAIN is mandatory for ML — SCRFD at classroom distance needs ~120 px faces
#   which only the main stream delivers. The sub stream gave ~40 px faces and
#   missed detections (documented 2026-04-22).
#   SUB is used by the admin portal's live-feed page in place of main: the
#   browser doesn't need 2560×1440 to render a 1280-wide viewport, and halving
#   the WebRTC decode load stops the jitter buffer from drifting over long
#   sessions. Overlay boxes use normalized 0–1 coords so they line up with
#   either profile.
# Hardware-to-room is swapped: the camera at 192.168.88.10 is physically
# mounted in EB227, and 192.168.88.11 is physically in EB226. Path keys
# (eb226 / eb227) stay aligned with rooms.stream_key, so the IP↔key mapping
# below looks inverted on purpose. Don't "correct" it without re-checking
# the physical install.
CAMERAS=(
  "192.168.88.11 eb226     h264Preview_01_main"
  "192.168.88.11 eb226-sub h264Preview_01_sub"
  "192.168.88.10 eb227     h264Preview_01_main"
  "192.168.88.10 eb227-sub h264Preview_01_sub"
)

# PIDs of child loops — populated as we launch each camera. Used by the
# signal trap to tear everything down cleanly on launchd shutdown.
CHILD_PIDS=()

cleanup() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] caught signal — terminating $(echo ${#CHILD_PIDS[@]}) children"
  for pid in "${CHILD_PIDS[@]}"; do
    # Kill the whole process group so ffmpeg dies with its loop wrapper.
    kill -TERM -"${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
  done
  # Give ffmpeg a moment to flush its mux.
  sleep 1
  for pid in "${CHILD_PIDS[@]}"; do
    kill -KILL "${pid}" 2>/dev/null || true
  done
  exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

# Per-camera loop. Runs in its own subshell so SIGTERM to the wrapper PID
# propagates via the process group.
run_camera() {
  local cam_ip="$1"
  local stream_key="$2"
  local rtsp_path="$3"
  local input_url="rtsp://${CAM_USER}:${CAM_PASS_ENC}@${cam_ip}:554/${rtsp_path}"
  local output_url="rtsp://${MTX_HOST}:${MTX_PORT}/${stream_key}"
  while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') [${stream_key}] ffmpeg starting — ${cam_ip} -> ${MTX_HOST}:${MTX_PORT}"
    # -c copy = no re-encode (free).
    # TCP transport on both sides — Reolink over WiFi drops UDP packets; mediamtx
    # also prefers TCP publishers.
    "${FFMPEG}" \
      -hide_banner -loglevel warning \
      -rtsp_transport tcp \
      -i "${input_url}" \
      -c copy \
      -f rtsp \
      -rtsp_transport tcp \
      "${output_url}"
    local rc=$?
    echo "$(date '+%Y-%m-%d %H:%M:%S') [${stream_key}] ffmpeg exited rc=${rc} — restart in 3 s"
    sleep 3
  done
}

# Watchdog loop. Periodically probes each stream_key via RTSP DESCRIBE; if
# the stream is missing from mediamtx but the corresponding ffmpeg process
# is still alive, ffmpeg is stuck (the pre-2026-04-22 failure mode: process
# alive, no frames flowing, supervisor happy, attendance pipeline starved).
# kill -9 the stuck ffmpeg — the per-camera run_camera loop restarts it
# with `sleep 3` backoff.
#
# The probe is an ffprobe call against rtsp://localhost:8554/<key>. On a
# healthy publish it prints `video\naudio` and exits 0 in <1 s. On a missing
# publish it prints `method DESCRIBE failed: 404Not Found` and exits 1.
run_watchdog() {
  # Startup grace — give the run_camera loops 30 s to establish their
  # initial publish before the watchdog starts asserting liveness.
  sleep 30

  # Per-stream consecutive-failure counter. We require 2 back-to-back bad
  # probes (60 s of unbroken "missing" state at the 30 s watchdog cadence)
  # before killing ffmpeg. This tolerates the intermittent H.264 cabac
  # decode errors on the EB227 main stream — observed 2026-04-24: ~1/3
  # of probes report "no video" even though the publisher is healthy and
  # the admin portal is rendering the feed fine. One flaky probe shouldn't
  # nuke a working stream; two-in-a-row is strong evidence of a real
  # stuck-ffmpeg state.
  #
  # macOS ships bash 3.2 — no `declare -A` associative arrays. We use
  # dynamically-named simple variables (FAIL_eb226, FAIL_eb227_sub, ...)
  # via bash parameter-substitution + eval.
  local fail_threshold=2

  while true; do
    for cam_spec in "${CAMERAS[@]}"; do
      # shellcheck disable=SC2086
      set -- ${cam_spec}
      local stream_key="$2"
      local stream_url="rtsp://${MTX_HOST}:${MTX_PORT}/${stream_key}"
      local probe_out
      # probesize + analyzeduration need to be generous enough for a
      # 2304x1296 H.264 main stream with ~2 s I-frame interval — on a
      # default probesize=500000 / analyzeduration=500000, ffprobe can
      # exit with no codec_type recognized on a perfectly healthy main
      # publisher, which made the watchdog kick ffmpeg in a ~2 min loop
      # for eb227 (observed 2026-04-24). Sub streams are small enough
      # that the defaults work, but we apply the same values uniformly.
      probe_out=$("${FFPROBE}" -hide_banner -v error -rtsp_transport tcp \
                  -timeout 5000000 \
                  -probesize 5000000 -analyzeduration 5000000 \
                  "${stream_url}" \
                  -show_entries stream=codec_type -of csv=p=0 2>&1 | head -3)
      # Variable name: FAIL_eb227 / FAIL_eb227_sub (hyphens → underscores).
      local fail_var="FAIL_${stream_key//-/_}"
      local streak
      eval "streak=\${${fail_var}:-0}"

      if echo "${probe_out}" | grep -q '^video'; then
        # Probe succeeded — reset any pending failure streak for this stream.
        eval "${fail_var}=0"
        continue
      fi

      # Probe failed. Increment the streak for this stream.
      streak=$(( streak + 1 ))
      eval "${fail_var}=${streak}"

      if [ "${streak}" -lt "${fail_threshold}" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] ${stream_key}" \
             "probe failed (${streak}/${fail_threshold}) — waiting before kick"
        continue
      fi

      # ${fail_threshold} consecutive failures → kick the ffmpeg.
      # pgrep matches on the exact output URL (anchored $), so we don't
      # accidentally kill sub when main is stuck (or vice versa).
      local stuck_pid
      stuck_pid=$(pgrep -f " ${stream_url}\$" | head -1)
      if [ -n "${stuck_pid}" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] ${stream_key}" \
             "missing from mediamtx (${streak} consecutive probe failures)" \
             "— kicking ffmpeg pid=${stuck_pid}"
        kill -9 "${stuck_pid}" 2>/dev/null || true
      else
        # ffmpeg already exited on its own — run_camera's restart loop
        # will bring it back; nothing for the watchdog to do.
        echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] ${stream_key}" \
             "missing from mediamtx (no ffmpeg found — restart loop in progress)"
      fi
      # Reset so the next evaluation gets a fresh ${fail_threshold}-probe window.
      eval "${fail_var}=0"
    done
    sleep 30
  done
}

echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] IAMS camera relay starting (${#CAMERAS[@]} stream(s))"

for cam_spec in "${CAMERAS[@]}"; do
  # shellcheck disable=SC2086
  set -- ${cam_spec}
  run_camera "$1" "$2" "$3" &
  CHILD_PIDS+=("$!")
  echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] launched loop pid=$! for $2"
done

# Launch the watchdog only if ffprobe is available. Otherwise the supervisor
# falls back to ffmpeg-exits-only failure detection (pre-2026-04-22 behaviour).
if [ -x "${FFPROBE}" ]; then
  run_watchdog &
  CHILD_PIDS+=("$!")
  echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] launched watchdog pid=$! (30 s interval, 30 s startup grace)"
fi

# Wait for any child to exit (they shouldn't — they loop forever). If one
# does, wait for them all and let launchd restart us.
wait
echo "$(date '+%Y-%m-%d %H:%M:%S') [supervisor] all children exited — supervisor ending, launchd will restart"
