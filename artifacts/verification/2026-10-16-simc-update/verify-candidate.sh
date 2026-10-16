#!/usr/bin/env bash
set -euo pipefail
umask 077
root=/var/lib/chickenbro-simc-update-20261016
candidate=/opt/chickenbro-candidates/simc-update-20261016
engine=/opt/wow-simc/releases/76f8118cf3f7f41dad20708e8328e1f4ab2deebc
printf '%s\n' waiting_for_engine > "$root/phase.txt"
for ((i=0; i<360; i++)); do
  if [[ -f "$engine/binary.sha256" ]]; then break; fi
  state=$(systemctl show chickenbro-simc-prepare-20261016 -p ActiveState --value)
  [[ "$state" == active || "$state" == activating ]] || { echo 'engine preparation stopped without sealed release'; exit 1; }
  sleep 5
done
[[ -f "$engine/binary.sha256" ]] || exit 1
if [[ ! -e /opt/wow-simc/candidate-20261016 ]]; then ln -s "$engine" /opt/wow-simc/candidate-20261016; fi
[[ "$(readlink -f /opt/wow-simc/candidate-20261016)" == "$engine" ]]
printf '%s\n' engine_smoke > "$root/phase.txt"
cd "$candidate"
/opt/chickenbro-runtime/bin/python "$root/engine-smoke.py" > "$root/engine-smoke.log" 2>&1
cp "$root/giannis_wcl_engine_export_70391.json" "$candidate/tests/fixtures/simc/giannis_wcl_engine_export_70391.json"
printf '%s\n' targeted_tests > "$root/phase.txt"
/opt/chickenbro-runtime/bin/python -m unittest tests.app_wcl_talents_test tests.app_simulation_talent_editor_test tests.app_simulation_localization_test tests.app_simulation_runtime_info_test tests.app_simulation_sources_test tests.app_simulation_compiler_test tests.app_simulation_effective_config_test tests.app_simulation_report_test tests.app_simulation_worker_test tests.app_simc_workbench_test tests.app_simc_workbench_api_test tests.app_simulation_phase_test > "$root/targeted-tests.log" 2>&1
printf '%s\n' candidate_http_smoke > "$root/phase.txt"
/opt/chickenbro-runtime/bin/python "$root/smoke.py" candidate "$candidate" --label candidate > "$root/candidate-smoke.log" 2>&1
printf '%s\n' candidate_verified > "$root/phase.txt"
