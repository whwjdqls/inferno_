# EMOTE : Emotional Speech-Driven Animation with Content-Emotion Disentanglement

This is the official implementation of [EMOCA: Emotion-Driven Monocular Face Capture and Animation](https://emote.is.tue.mpg.de/). EMOCA takes a single in-the-wild image as input and reconstructs a 3D face with sufficient facial expression detail to convey the emotional state of the
input image. 



## Installation 

1) Follow the steps at the [root of this repo](../..). If for some reason the environment from there is not valid, create one using a `.yml` file from `envs`.

2) In order to run the demos you will need to download and unzip a few assets. Run `download_assets.sh` to do that: 
```bash 
cd demos 
bash download_assets.sh
```
3) (Optional for inference, required for training) [Basel Face Model](https://faces.dmi.unibas.ch/bfm/bfm2019.html) texture space adapted to FLAME. Unfortunately, we are not allowed to distribute the texture space, since the license does not permit it. Therefore, please go to the [BFM page](https://faces.dmi.unibas.ch/bfm/bfm2019.html) sign up and dowload BFM. Then use the tool from this [repo](https://github.com/TimoBolkart/BFM_to_FLAME) to convert the texture space to FLAME. Put the resulting texture model file file into [`../../assets/FLAME/texture`](../../assets/FLAME/texture) as `FLAME_albedo_from_BFM.npz`


## Demos 

Then activate your environment: 
```bash
conda activate work38
```

### Create a speech-driven animation for all of 8 basic emotions
If you want to run EMOTE on any .wav file, run the following:

```python 
python evaluation/TODO 
```

The script will detect faces in every image in the folder output the results that you specify with `--save_video`, `--save_flame`, `--save_meshes` to the output folder. 