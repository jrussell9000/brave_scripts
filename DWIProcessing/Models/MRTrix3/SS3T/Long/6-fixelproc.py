#!/usr/bin/env python3
# coding: utf-8

import subprocess
from pathlib import Path
import shutil
from joblib import parallel_backend, delayed, Parallel

template_dir = Path('/fast_scratch/jdr/dti_longproc')
bidsproc_dir = Path('/Volumes/Vol6/YouthPTSD/BIDS_Processed/')
wmfod_template = template_dir / 'YouthPTSD_wmfodtempl_long.mif'
template_mask = template_dir / 'YouthPTSD_masktempl_long.mif'
fixel_mask = template_dir / 'fixel_mask'

# 1. Run segmendFodTempl command separately in command line (has issues).
# 2. Run the script as usual (segmentFODTempl command won't run).

#!!! This command spits out an error about the mask image if not run from
# the command line. :(
def segmentFODTempl(template_dir, wmfod_template, template_mask):
    if fixel_mask.exists():
        shutil.rmtree(fixel_mask)
    subprocess.run(['fod2fixel', '-mask', template_mask, '-fmls_peak_value', '0.06',
                    wmfod_template, fixel_mask])
    return fixel_mask


def loadsubj(ses_dir):
    subj_dir = ses_dir.parent
    subjroot = "_".join([subj_dir.name, ses_dir.name])
    proc_dir = ses_dir / 'dwi' / 'processed'
    ss3t_dir = proc_dir / 'mrtrix' / 'ss3t'
    wmfod_norm = ss3t_dir / (subjroot + '_wmfod_norm.mif')
    subj2templwarp = ss3t_dir / (subjroot + '_subj2templwarp.mif')
    return ss3t_dir, subjroot, wmfod_norm, subj2templwarp


def warpFODs2Templ(ss3t_dir, subjroot, wmfod_norm, subj2templwarp):
    wmfod_norm_reg2templ_notreoriented = ss3t_dir / (subjroot + '_wmfod_norm_reg2templ_notreoriented.mif')
    subprocess.run(['mrtransform', '-force', '-warp', subj2templwarp, '-reorient_fod', 'no', wmfod_norm,
                    wmfod_norm_reg2templ_notreoriented])
    return wmfod_norm_reg2templ_notreoriented


def segmentSubjFODs(ss3t_dir, subjroot, template_mask, wmfod_norm_reg2templ_notreoriented):
    fixel_reg2templ_notreoriented = ss3t_dir / 'fixel_reg2templ_notreoriented'
    if fixel_reg2templ_notreoriented.exists():
        shutil.rmtree(fixel_reg2templ_notreoriented)
    fiber_density_notreoriented = str(subjroot + '_fd.mif')
    subprocess.run(['fod2fixel', '-force', '-mask', template_mask, wmfod_norm_reg2templ_notreoriented,
                    fixel_reg2templ_notreoriented, '-afd', fiber_density_notreoriented])
    return fixel_reg2templ_notreoriented


def reorientfixels(ss3t_dir, subjroot, fixel_reg2templ_notreoriented, subj2templwarp):
    fixel_reg2templ = ss3t_dir / 'fixel_reg2templ'
    if fixel_reg2templ.exists():
        shutil.rmtree(fixel_reg2templ)
    subprocess.run(['fixelreorient', '-force', fixel_reg2templ_notreoriented, subj2templwarp, fixel_reg2templ])
    return fixel_reg2templ


def subjfxls2templfxls(ss3t_dir, subjroot, fixel_reg2templ, fixel_mask):
    subj_FD_reoriented = fixel_reg2templ / (subjroot + '_fd.mif')
    FD_dir = template_dir / 'FD'
    subj_FD_matched = str(subjroot + '_fd.mif')
    subprocess.run(['fixelcorrespondence', '-force', subj_FD_reoriented, fixel_mask, FD_dir,
                    subj_FD_matched])


def subjfixelproc(ses_dir):
    ss3t_dir, subjroot, wmfod_norm, subj2templwarp = loadsubj(ses_dir)
    wmfod_norm_reg2templ_notreoriented = warpFODs2Templ(ss3t_dir, subjroot, wmfod_norm, subj2templwarp)
    fixel_reg2templ_notreoriented = segmentSubjFODs(ss3t_dir, subjroot, template_mask,
                                                    wmfod_norm_reg2templ_notreoriented)
    fixel_reg2templ = reorientfixels(ss3t_dir, subjroot, fixel_reg2templ_notreoriented, subj2templwarp)
    subjfxls2templfxls(ss3t_dir, subjroot, fixel_reg2templ, fixel_mask)

# See note above about running this command.
# fixel_mask = segmentFODTempl(template_dir, template_mask, wmfod_template)

ses_dirs = (ses_dir for ses_dir in bidsproc_dir.glob('*/ses-*') if Path(ses_dir.parent / 'ses-01' / 'dwi').exists() and
            Path(ses_dir.parent / 'ses-02' / 'dwi').exists())

with parallel_backend("loky", inner_max_num_threads=8):
    results = Parallel(n_jobs=8, verbose=1)(
        delayed(subjfixelproc)(ses_dir) for ses_dir in sorted(ses_dirs))
