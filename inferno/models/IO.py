"""
Author: Radek Danecek
Copyright (c) 2022, Radek Danecek
All rights reserved.

# Max-Planck-Gesellschaft zur Förderung der Wissenschaften e.V. (MPG) is
# holder of all proprietary rights on this computer program.
# Using this computer program means that you agree to the terms 
# in the LICENSE file included with this software distribution. 
# Any use not explicitly granted by the LICENSE is prohibited.
#
# Copyright©2022 Max-Planck-Gesellschaft zur Förderung
# der Wissenschaften e.V. (MPG). acting on behalf of its Max Planck Institute
# for Intelligent Systems. All rights reserved.
#
# For comments or questions, please email us at emoca@tue.mpg.de
# For commercial licensing contact, please contact ps-license@tuebingen.mpg.de
"""


import sys
from pathlib import Path
from inferno.utils.other import get_path_to_assets


def locate_checkpoint(cfg_or_checkpoint_dir, replace_root = None, relative_to = None, mode=None, pattern=None):
    if isinstance(cfg_or_checkpoint_dir, (str, Path)):
        checkpoint_dir = str(cfg_or_checkpoint_dir)
    else:
        checkpoint_dir = cfg_or_checkpoint_dir.inout.checkpoint_dir
    if replace_root is not None and relative_to is not None:
        try:
            checkpoint_dir = str(Path(replace_root) / Path(checkpoint_dir).relative_to(relative_to))
        except ValueError as e:
            print(f"Not replacing the root of checkpoint_dir '{checkpoint_dir}' beacuse the specified root does not fit:"
                  f"'{replace_root}'")
    if not Path(checkpoint_dir).is_absolute():
        checkpoint_dir = str(get_path_to_assets() / checkpoint_dir)
    print(f"Looking for checkpoint in '{checkpoint_dir}'")
    checkpoints = sorted(list(Path(checkpoint_dir).rglob("*.ckpt")))
    if len(checkpoints) == 0:
        print(f"Did not find checkpoints. Looking in subfolders")
        checkpoints = sorted(list(Path(checkpoint_dir).rglob("*.ckpt")))
        if len(checkpoints) == 0:
            print(f"Did not find checkpoints to resume from. Returning None")
            # sys.exit()
            return None
        print(f"Found {len(checkpoints)} checkpoints")
    else:
        print(f"Found {len(checkpoints)} checkpoints")
    if pattern is not None:
        checkpoints = [ckpt for ckpt in checkpoints if pattern in str(ckpt)]
    for ckpt in checkpoints:
        print(f" - {str(ckpt)}")

    if isinstance(mode, int):
        checkpoint = str(checkpoints[mode])
    elif mode == 'latest':
        # checkpoint = str(checkpoints[-1])
        checkpoint = checkpoints[0]
        # assert checkpoint.name == "last.ckpt", f"Checkpoint name is not 'last.ckpt' but '{checkpoint.name}'. Are you sure this is the right checkpoint?"
        if checkpoint.name != "last.ckpt":
            # print(f"Checkpoint name is not 'last.ckpt' but '{checkpoint.name}'. Are you sure this is the right checkpoint?")
            return None
        checkpoint = str(checkpoint)
    elif mode == 'best':
        min_value = 999999999999999.
        min_idx = -1
        # remove all checkpoints that do not containt the pattern 
        for idx, ckpt in enumerate(checkpoints):
            if ckpt.stem == "last": # disregard last
                continue
            end_idx = str(ckpt.stem).rfind('=') + 1
            loss_str = str(ckpt.stem)[end_idx:]
            try:
                loss_value = float(loss_str)
            except ValueError as e:
                print(f"Unable to convert '{loss_str}' to float. Skipping this checkpoint.")
                continue
            if loss_value <= min_value:
                min_value = loss_value
                min_idx = idx
        if min_idx == -1:
            raise FileNotFoundError("Finding the best checkpoint failed")
        checkpoint = str(checkpoints[min_idx])
    else:
        raise ValueError(f"Invalid checkpoint loading mode '{mode}'")
    print(f"Selecting checkpoint '{checkpoint}'")
    return checkpoint


def get_checkpoint_with_kwargs(cfg, prefix, replace_root = None, relative_to = None, checkpoint_mode=None, pattern=None):
    checkpoint = get_checkpoint(cfg, replace_root = replace_root,
                                relative_to = relative_to, checkpoint_mode=checkpoint_mode, pattern=pattern)
    cfg.model.resume_training = False  # make sure the training is not magically resumed by the old code
    # checkpoint_kwargs = {
    #     "model_params": cfg.model,
    #     "learning_params": cfg.learning,
    #     "inout_params": cfg.inout,
    #     "stage_name": prefix
    # }
    checkpoint_kwargs = {'config': cfg}
    return checkpoint, checkpoint_kwargs


def get_checkpoint(cfg, replace_root = None, relative_to = None, checkpoint_mode=None, pattern=None):
    if checkpoint_mode is None:
        checkpoint_mode = 'latest'
        if hasattr(cfg.learning, 'checkpoint_after_training'):
            checkpoint_mode = cfg.learning.checkpoint_after_training
    checkpoint = locate_checkpoint(cfg, replace_root = replace_root,
                                   relative_to = relative_to, mode=checkpoint_mode, pattern=pattern)
    return checkpoint