#!/usr/bin/env bash

# Need to get:
# -PREPROC_DIR

# Need to do:
# -Check for cuda support

PREPROC_DIR=$1
USEGPUopt=$2

main() {
	FSL_DIR="$FSLDIR"
	verbose="--verbose"
	ReplOutliers="--repol"
	if [[ "${USEGPUopt}" == "True" ]] ; then
		eddyExec="${FSL_DIR}/bin/eddy_cuda"
		printf "\\nGPU acceleration enabled.  Using eddy_cuda for eddy correction..."
	else
		eddyExec="${FSL_DIR}/bin/eddy_openmp"
		printf "\\nGPU acceleration not enabled.  Using eddy_openmp for eddy correction..."
	fi
	eddy_command="${eddyExec}"
	eddy_command="${eddy_command} ${verbose}"
	eddy_command="${eddy_command} ${ReplOutliers}"
	eddy_command="${eddy_command} --imain=${PREPROC_DIR}/PA_AP"
	eddy_command="${eddy_command} --mask=${PREPROC_DIR}/nodif_brain_mask"
	eddy_command="${eddy_command} --index=${PREPROC_DIR}/index.txt"
	eddy_command="${eddy_command} --acqp=${PREPROC_DIR}/acqparams.txt"
	eddy_command="${eddy_command} --bvecs=${PREPROC_DIR}/PA_AP.bvec"
	eddy_command="${eddy_command} --bvals=${PREPROC_DIR}/PA_AP.bval"
	eddy_command="${eddy_command} --topup=${PREPROC_DIR}/topup_PA_AP_b0"
	eddy_command="${eddy_command} --out=${PREPROC_DIR}/eddy_unwarped_images"
	${eddy_command}
}

main $@