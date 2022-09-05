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

import os, sys
from pathlib import Path
# sys.path += [str(Path(__file__).parent.parent)]

from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import ModelCheckpoint, EarlyStopping

from gdl.models.temporal.AVFace import TemporalFace, instantiate
from pytorch_lightning.loggers import WandbLogger
import datetime
import time as t
# import hydra
from omegaconf import DictConfig, OmegaConf
import copy

project_name = 'TalkingHead'


def get_checkpoint_with_kwargs(cfg, prefix, checkpoint_mode=None):
    checkpoint = get_checkpoint(cfg, checkpoint_mode)
    cfg.model.resume_training = False  # make sure the training is not magically resumed by the old code
    checkpoint_kwargs = {
        "model_params": cfg.model,
        "learning_params": cfg.learning,
        "inout_params": cfg.inout,
        "stage_name": prefix
    }
    return checkpoint, checkpoint_kwargs


def get_checkpoint(cfg, checkpoint_mode=None):
    if checkpoint_mode is None:
        if hasattr(cfg.learning, 'checkpoint_after_training'):
            checkpoint_mode = cfg.learning.checkpoint_after_training
        else:
            checkpoint_mode = 'latest'
    checkpoint = locate_checkpoint(cfg, checkpoint_mode)
    return checkpoint


def locate_checkpoint(cfg, mode='latest'):
    print(f"Looking for checkpoint in '{cfg.inout.checkpoint_dir}'")
    checkpoints = sorted(list(Path(cfg.inout.checkpoint_dir).rglob("*.ckpt")))
    if len(checkpoints) == 0:
        print(f"Did not found checkpoints. Looking in subfolders")
        checkpoints = sorted(list(Path(cfg.inout.checkpoint_dir).rglob("*.ckpt")))
        if len(checkpoints) == 0:
            print(f"Did not find checkpoints to resume from. Terminating")
            sys.exit()
        print(f"Found {len(checkpoints)} checkpoints")
    else:
        print(f"Found {len(checkpoints)} checkpoints")
    for ckpt in checkpoints:
        print(f" - {str(ckpt)}")

    if isinstance(mode, int):
        checkpoint = str(checkpoints[mode])
    elif mode == 'latest':
        checkpoint = str(checkpoints[-1])
    elif mode == 'best':
        min_value = 999999999999999.
        min_idx = -1
        for idx, ckpt in enumerate(checkpoints):
            if ckpt.stem == 'last':
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
            raise RuntimeError("Finding the best checkpoint failed")
        checkpoint = str(checkpoints[min_idx])
    else:
        raise ValueError(f"Invalid checkopoint loading mode '{mode}'")
    print(f"Selecting checkpoint '{checkpoint}'")
    return checkpoint


def prepare_data(cfg):
    print(f"The data will be loaded from: '{cfg.data.data_root}'")

    dm = None 
    sequence_name = None 
    #TODO: initialize LRS3 or others

    return dm, sequence_name


def create_logger(logger_type, name, project_name, version, save_dir, config=None):
    if logger_type is None:
        # legacy reasons
        logger_type = "WandbLogger"
        print(f"Logger type is not set. Defaulting to {logger_type}")

    if not logger_type:
        print(f"No logger instantiated.")
        return None
    if logger_type == "WandbLogger":
        print(f"Creating logger: {logger_type}")
        short_name = name[:128]
        short_version = version[:128]
        print(f"Short name len: {len(short_name)}")
        print(short_name)
        if config is not None:
            if 'learning' in config.keys():
                tags = config['learning']['tags'] if 'tags' in config['learning'].keys() else None
            elif "coarse" in config.keys():
                tags = config["coarse"]['learning']['tags'] if 'tags' in config["coarse"]['learning'].keys() else None
            elif "detail" in config.keys():
                tags = config["detail"]['learning']['tags'] if 'tags' in config["detail"]['learning'].keys() else None
        else:
            tags = None

        logger = WandbLogger(name=short_name,
                             notes=name,
                             project=project_name,
                             version=short_version,
                             save_dir=save_dir,
                             config=config,
                             tags=tags)
        max_tries = 100
        tries = 0
        if logger is not None:
            while True:
                try:
                    ex = logger.experiment
                    break
                except Exception as e:
                    logger._experiment = None
                    print("Reinitiliznig wandb because it failed in 10s")
                    t.sleep(10)
                    if max_tries <= max_tries:
                        print("WANDB Initialization unsuccessful")
                        break
                    tries += 1
    else:
        raise ValueError(f"Invalid logger_type: '{logger_type}")
    return logger


def single_stage_training_pass(model, cfg, stage, prefix, dm=None, logger=None,
                           data_preparation_function=None,
                           checkpoint=None, checkpoint_kwargs=None, project_name_=None,
                           instantiation_function=None
                           ):
    # instantiation_function = instantiation_function or instantiate
    project_name_ = project_name_ or project_name
    if dm is None:
        dm, sequence_name = data_preparation_function(cfg)
        dm.prepare_data()

    if logger is None:
        N = len(datetime.datetime.now().strftime("%Y_%m_%d_%H-%M-%S"))

        if hasattr(cfg.inout, 'time') and hasattr(cfg.inout, 'random_id'):
            version = cfg.inout.time + "_" + cfg.inout.random_id
        elif hasattr(cfg.inout, 'time'):
            version = cfg.inout.time + "_" + cfg.inout.name
        else:
            version = sequence_name[:N] # unfortunately time doesn't cut it if two jobs happen to start at the same time

        logger = create_logger(
                    cfg.learning.logger_type,
                    name=cfg.inout.name,
                    project_name=project_name_,
                    version=version,
                    save_dir=cfg.inout.full_run_dir,
                    config=OmegaConf.to_container(cfg)
        )

    if logger is not None:
        logger.finalize("")

    if model is None:
        # model = instantiation_function(cfg, stage, prefix, checkpoint, checkpoint_kwargs)
        model = instantiation_function(cfg, stage, prefix, checkpoint, checkpoint_kwargs)
    else:
        if stage == 'train':
            mode = True
        else:
            mode = False
        # if checkpoint is not None:
        #     deca.load_from_checkpoint(checkpoint_path=checkpoint)
        # model.reconfigure(cfg.model, cfg.inout, cfg.learning, prefix, downgrade_ok=True, train=mode)



    # accelerator = None if cfg.learning.num_gpus == 1 else 'ddp2'
    accelerator = None if cfg.learning.batching.num_gpus == 1 else 'ddp'
    # accelerator = None if cfg.learning.num_gpus == 1 else 'ddp_spawn' # ddp only seems to work for single .fit/test calls unfortunately,
    # accelerator = None if cfg.learning.num_gpus == 1 else 'dp'  # ddp only seems to work for single .fit/test calls unfortunately,

    # if accelerator is not None and 'LOCAL_RANK' not in os.environ.keys():
    #     print("SETTING LOCAL_RANK to 0 MANUALLY!!!!")
    #     os.environ['LOCAL_RANK'] = '0'

    # loss_to_monitor = 'val_loss_total'
    loss_to_monitor = 'val/loss_total'
    dm.setup()
    val_data = dm.val_dataloader()
    filename_pattern = 'model-{epoch:02d}-{' + loss_to_monitor + ':.8f}'
    if isinstance(val_data, list):
        loss_to_monitor = loss_to_monitor + "/dataloader_idx_0"
        filename_pattern = 'model-{epoch:02d}-{' + loss_to_monitor + ':.8f}'
        # loss_to_monitor = '0_' + loss_to_monitor + "/dataloader_idx_0"
    # if len(prefix) > 0:
    #     loss_to_monitor = prefix + "_" + loss_to_monitor

    callbacks = []
    checkpoint_callback = ModelCheckpoint(
        monitor=loss_to_monitor,
        filename=filename_pattern,
        save_top_k=3,
        save_last=True,
        mode='min',
        dirpath=cfg.inout.checkpoint_dir
    )
    callbacks += [checkpoint_callback]
    if hasattr(cfg.learning, 'early_stopping') and cfg.learning.early_stopping:
        patience = 3
        if hasattr(cfg.learning.early_stopping, 'patience') and cfg.learning.early_stopping.patience:
            patience = cfg.learning.early_stopping.patience

        early_stopping_callback = EarlyStopping(monitor=loss_to_monitor,
                                                mode='min',
                                                patience=patience,
                                                strict=True)
        callbacks += [early_stopping_callback]


    val_check_interval = 1.0
    if 'val_check_interval' in cfg.model.keys():
        val_check_interval = cfg.model.val_check_interval
    print(f"Setting val_check_interval to {val_check_interval}")

    max_steps = None
    if hasattr(cfg.model, 'max_steps'):
        max_steps = cfg.model.max_steps
        print(f"Setting max steps to {max_steps}")

    print(f"After training checkpoint strategy: {cfg.learning.checkpoint_after_training}")

    trainer = Trainer(gpus=cfg.learning.batching.num_gpus,
                      max_epochs=cfg.model.max_epochs,
                      max_steps=max_steps,
                      default_root_dir=cfg.inout.checkpoint_dir,
                      logger=logger,
                      accelerator=accelerator,
                      callbacks=callbacks,
                      val_check_interval=val_check_interval,
                      log_every_n_steps=cfg.learning.batching.get('log_every_n_steps', 50),
                      # num_sanity_val_steps=0
                      )

    pl_module_class = TemporalFace # TODO: make configurable


    if stage == "train":
        # trainer.fit(deca, train_dataloader=train_data_loader, val_dataloaders=[val_data_loader, ])
        trainer.fit(model, datamodule=dm)
        if hasattr(cfg.learning, 'checkpoint_after_training'):
            if cfg.learning.checkpoint_after_training == 'best':
                print(f"Loading the best checkpoint after training '{checkpoint_callback.best_model_path}'.")
                model = pl_module_class.load_from_checkpoint(checkpoint_callback.best_model_path,
                                                       model_params=cfg.model,
                                                       learning_params=cfg.learning,
                                                       inout_params=cfg.inout,
                                                       stage_name=prefix
                                                       )
            elif cfg.learning.checkpoint_after_training == 'latest':
                print(f"Keeping the lastest weights after training.")
                pass # do nothing, the latest is obviously loaded
            else:
                print(f"[WARNING] Unexpected value of cfg.learning.checkpoint_after_training={cfg.learning.checkpoint_after_training}. "
                      f"Will do nothing")

    elif stage == "test":
        # trainer.test(deca,
        #              test_dataloaders=[test_data_loader],
        #              ckpt_path=None)
        trainer.test(model,
                     datamodule=dm,
                     ckpt_path=None)
    else:
        raise ValueError(f"Invalid stage {stage}")
    if logger is not None:
        logger.finalize("")
    return model


def create_experiment_name(cfg_coarse, cfg_detail, sequence_name, version=1):

    experiment_name = "TalkingHead"
    return experiment_name



def configure_and_train(cfg_default, cfg_overrides):
    cfg_coarse = configure(cfg_default, cfg_overrides)
    train_model(cfg_coarse)


def load_configs(run_path):
    with open(Path(run_path) / "cfg.yaml", "r") as f:
        conf = OmegaConf.load(f)
    cfg_coarse = conf.coarse
    cfg_detail = conf.detail
    return cfg_coarse, cfg_detail


def configure_and_resume(run_path,
                         coarse_cfg_default, coarse_overrides,
                         detail_cfg_default, detail_overrides,
                         start_at_stage):
    cfg_coarse, cfg_detail = configure(
                                       coarse_cfg_default, coarse_overrides,
                                       detail_cfg_default, detail_overrides)

    cfg_coarse_, cfg_detail_ = load_configs(run_path)

    if start_at_stage < 4:
        raise RuntimeError("Resuming before stage 2 makes no sense, that would be training from scratch")
    if start_at_stage == 4:
        cfg_coarse = cfg_coarse_
    elif start_at_stage == 5:
        raise RuntimeError("Resuming for stage 3 makes no sense, that is a testing stage")
    else:
        raise RuntimeError(f"Cannot resume at stage {start_at_stage}")

    train_model(cfg_coarse, cfg_detail,
               start_i=start_at_stage,
               resume_from_previous=True, #important, resume from previous stage's checkpoint
               force_new_location=True)



def resume_training(run_path, start_at_stage, resume_from_previous, force_new_location):
    with open(Path(run_path) / "cfg.yaml", "r") as f:
        conf = OmegaConf.load(f)
    train_model(conf, 
                start_i=start_at_stage,
                resume_from_previous=resume_from_previous,
                force_new_location=force_new_location)


def configure(cfg, overrides):
    from hydra.experimental import compose, initialize
    initialize(config_path="../talkinghead_conf", job_name="TalkingHead")
    config = compose(config_name=cfg, overrides=overrides)
    return config


# # @hydra.main(config_path="../emoca_conf", config_name="deca_finetune")
# # def main(cfg : DictConfig):
# def main():
#     configured = False
#     if len(sys.argv) >= 3:
#         if Path(sys.argv[1]).is_file():
#             configured = True
#             with open(sys.argv[1], 'r') as f:
#                 coarse_conf = OmegaConf.load(f)
#             with open(sys.argv[2], 'r') as f:
#                 detail_conf = OmegaConf.load(f)

#         else:
#             coarse_conf = sys.argv[1]
#             detail_conf = sys.argv[2]
#     else:
#         coarse_conf = "temporal_face"
#         # detail_conf = ""
#         detail_conf = None
        

#     if len(sys.argv) >= 5:
#         coarse_override = sys.argv[3]
#         detail_override = sys.argv[4]
#     else:
#         coarse_override = []
#         detail_override = []
#     if configured:
#         train_model(coarse_conf, detail_conf)
#     else:
#         configure_and_finetune(coarse_conf, coarse_override, detail_conf, detail_override)


# if __name__ == "__main__":
#     main()