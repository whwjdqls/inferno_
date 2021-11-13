from gdl.utils.condor import execute_on_cluster
from pathlib import Path
import train_emodeca
import datetime
from omegaconf import OmegaConf
import time as t
import random
from wandb import Api

def submit(cfg,
           resume_folder,
           stage = None,
           bid=10):
    cluster_repo_path = "/home/rdanecek/workspace/repos/gdl"
    # submission_dir_local_mount = "/home/rdanecek/Workspace/mount/scratch/rdanecek/emoca/submission"
    # submission_dir_local_mount = "/ps/scratch/rdanecek/emoca/submission"
    # submission_dir_cluster_side = "/ps/scratch/rdanecek/emoca/submission"

    submission_dir_local_mount = "/is/cluster/work/rdanecek/emoca/submission"
    submission_dir_cluster_side = "/is/cluster/work/rdanecek/emoca/submission"


    result_dir_local_mount = "/is/cluster/work/rdanecek/emoca/emodeca"
    result_dir_cluster_side = "/is/cluster/work/rdanecek/emoca/emodeca"

    time = datetime.datetime.now().strftime("%Y_%m_%d_%H-%M-%S")
    submission_folder_name = time + "_" + str(hash(random.randint(0,10000000))) + "_" + "submission"
    submission_folder_local = Path(submission_dir_local_mount) / submission_folder_name
    submission_folder_cluster = Path(submission_dir_cluster_side) / submission_folder_name

    local_script_path = Path(train_emodeca.__file__).absolute()
    cluster_script_path = Path(cluster_repo_path) / local_script_path.parents[1].name \
                          / local_script_path.parents[0].name / local_script_path.name


    submission_folder_local.mkdir(parents=True)

    config_file  = submission_folder_local / "cfg.yaml"
    with open(config_file, 'w') as f:
         OmegaConf.save(cfg, f)

    # python_bin = 'python'
    python_bin = '/home/rdanecek/anaconda3/envs/<<ENV>>/bin/python'
    username = 'rdanecek'
    gpu_mem_requirement_mb = cfg.learning.gpu_memory_min_gb * 1024
    gpu_mem_requirement_mb = 15 * 1024
    gpu_mem_requirement_mb_max = 35 * 1024
    # gpu_mem_requirement_mb = None
    cpus = cfg.data.num_workers + 2 # 1 for the training script, 1 for wandb or other loggers (and other stuff), the rest of data loading
    # cpus = 2 # 1 for the training script, 1 for wandb or other loggers (and other stuff), the rest of data loading
    gpus = cfg.learning.num_gpus
    num_jobs = 1
    max_time_h = 36
    max_price = 10000
    job_name = "train_deca"
    cuda_capability_requirement = 7
    mem_gb = 16
    # mem_gb = 30

    start_from_previous = 1
    force_new_location = 1
    stage = 1
    project_name = "AffectNetEmoDECATest"
    args = f" {config_file.name} {stage} {start_from_previous} {force_new_location} {project_name} "

    execute_on_cluster(str(cluster_script_path),
                       args,
                       str(submission_folder_local),
                       str(submission_folder_cluster),
                       str(cluster_repo_path),
                       python_bin=python_bin,
                       username=username,
                       gpu_mem_requirement_mb=gpu_mem_requirement_mb,
                       gpu_mem_requirement_mb_max=gpu_mem_requirement_mb_max,
                       cpus=cpus,
                       mem_gb=mem_gb,
                       gpus=gpus,
                       num_jobs=num_jobs,
                       bid=bid,
                       max_concurrent_jobs=30,
                       max_time_h=max_time_h,
                       max_price=max_price,
                       job_name=job_name,
                       cuda_capability_requirement=cuda_capability_requirement,
                       modules_to_load=['cuda/11.4'],
                       # chmod=False
                       )
    # t.sleep(2)


def train_emodeca_on_cluster():

    # # # EMOEXPDECA
    resume_folders = []
    bid = 10
    stage = 1 # test stage
    api = Api()

    # comparison methods
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-39-36_-1044078422889696991_EmoDeep3DFace_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-39-32_6108539290469616315_EmoDeep3DFace_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_14-18-44_-5607778736970990207_Emo3DDFA_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_14-08-18_15578703095531241_Emo3DDFA_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_14-08-15_-7029531744226117801_Emo3DDFA_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_14-07-53_4456762721214245215_Emo3DDFA_shake_samp-balanced_expr_early"]

    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-39-09_-5731619448091644006_EmoMGCNet_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-39-23_-1563842771012871107_EmoMGCNet_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-40-47_788901720705055085_EmoExpNet_shake_samp-balanced_expr_early"]
    # resume_folders += ["/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-39-22_7185746630127973131_EmoExpNet_shake_samp-balanced_expr_early"]

    # image based
    resume_folders += [
        "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_09_20-48-55_-7323345455363258885_EmoNet_shake_samp-balanced_expr_Aug_early_d0.9000"]
    resume_folders += [
        "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_09_05-15-38_-8198495972451127810_EmoCnn_resnet50_shake_samp-balanced_expr_Aug_early"]
    resume_folders += [
        "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_09_04-12-56_7559763461347220097_EmoNet_shake_samp-balanced_expr_Aug_early"]
    resume_folders += [
        "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_09_04-05-57_1011354483695245068_EmoSwin_swin_tiny_patch4_window7_224_shake_samp-balanced_expr_Aug_early"]
    resume_folders += [
        "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_09_04-04-01_-3592833751800073730_EmoSwin_swin_base_patch4_window7_224_shake_samp-balanced_expr_Aug_early"]
    resume_folders += [
        "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_09_04-02-49_-1360894345964690046_EmoCnn_vgg19_bn_shake_samp-balanced_expr_Aug_early"]

    # # some of the best candidates
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_12_19-56-13_704003715291275370_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_15-42-30_8680779076656978317_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_12-13-16_-8024089022190881636_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_01-59-07_-9007648997833454518_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_11_01-58-56_1043302978911105834_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_20-58-31_-7948033884851958030_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_20-58-27_-5553059236244394333_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_20-57-28_-4957717700349337532_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_16-34-49_8015192522733347822_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_16-33-02_-5975857231436227431_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_16-33-00_-1889770853677981780_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]
    # resume_folders += [
    #     "/is/cluster/work/rdanecek/emoca/emodeca/2021_11_10_16-32-49_-6879167987895418873_EmoDECA_Affec_ExpDECA_nl-4BatchNorm1d_id_exp_jaw_shake_samp-balanced_expr_early"]

    # TODO: some of the DECA dataset trained ExpDECAs are missing ablations are missing
    # resume_folders += [""]
    # resume_folders += [""]
    # resume_folders += [""]
    # resume_folders += [""]

    # submit_ = False
    submit_ = True

    for resume_folder in resume_folders:
        name = str(Path(resume_folder).name)
        idx = name.find("Emo")
        run_id = name[:idx-1]
        run = api.run("rdanecek/EmoDECA/" + run_id)
        tags = set(run.tags)

        allowed_tags = set(["COMPARISON", "INTERESTING", "FINAL_CANDIDATE", "BEST_CANDIDATE", "BEST_IMAGE_BASED"])

        if len(allowed_tags.intersection(tags)) == 0:
            print(f"Run '{name}' is not tagged to be tested and will be skipped.")
            continue

        cfg = OmegaConf.load(Path(resume_folder) / "cfg.yaml")

        cfg.data.data_class = "AffectNetEmoNetSplitModuleTest"


        if submit_:
            submit(cfg, stage, bid=bid)
        else:
            project_name = "E"
            stage = 1
            start_from_previous = 1
            force_new_location = 1
            train_emodeca.train_emodeca(cfg, stage, start_from_previous, force_new_location, "AffectNetEmoDECATest")


if __name__ == "__main__":
    train_emodeca_on_cluster()

