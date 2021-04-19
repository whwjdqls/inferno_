import os, sys
from enum import Enum
from pathlib import Path
import numpy as np
import torch
import pytorch_lightning as pl
import pandas as pd
from skimage.io import imread, imsave
from datasets.IO import load_segmentation, process_segmentation
from utils.image import numpy_image_to_torch
from transforms.keypoints import KeypointNormalization
import imgaug
from datasets.FaceDataModuleBase import FaceDataModuleBase
from datasets.ImageDatasetHelpers import bbox2point, bbpoint_warp
from datasets.EmotionalImageDataset import EmotionalImageDatasetBase
from utils.FaceDetector import save_landmark, load_landmark
from tqdm import auto
import traceback
from torch.utils.data.dataloader import DataLoader
from transforms.imgaug import create_image_augmenter


class AffectNetExpressions(Enum):
    Neutral = 0
    Happy = 1
    Sad = 2
    Surprise = 3
    Fear = 4
    Disgust = 5
    Anger = 6
    Contempt = 7
    None_ = 8
    Uncertain = 9
    Occluded = 10
    xxx = 11


    @staticmethod
    def from_str(string : str):
        string = string[0].upper() + string[1:]
        return AffectNetExpressions[string]

    # _expressions = {0: 'neutral', 1:'happy', 2:'sad', 3:'surprise', 4:'fear', 5:'disgust', 6:'anger', 7:'contempt', 8:'none'}


class AffectNetDataModule(FaceDataModuleBase):

    def __init__(self,
                 input_dir,
                 output_dir,
                 processed_subfolder = None,
                 ignore_invalid = False,
                 mode="manual",
                 face_detector='fan',
                 face_detector_threshold=0.9,
                 image_size=224,
                 scale=1.25,
                 device=None,
                 augmentation=None,
                 train_batch_size=64,
                 val_batch_size=64,
                 test_batch_size=64,
                 num_workers=0,
                 ):
        super().__init__(input_dir, output_dir, processed_subfolder,
                         face_detector=face_detector,
                         face_detector_threshold=face_detector_threshold,
                         image_size=image_size,
                         scale=scale,
                         device=device)
        # accepted_modes = ['manual', 'automatic', 'all'] # TODO: add support for the other images
        accepted_modes = ['manual']
        if mode not in accepted_modes:
            raise ValueError(f"Invalid mode '{mode}'. Accepted modes: {'_'.join(accepted_modes)}")
        self.mode = mode
        # self.subsets = sorted([f.name for f in (Path(input_dir) / "Manually_Annotated" / "Manually_Annotated_Images").glob("*") if f.is_dir()])
        self.input_dir = Path(self.root_dir) / "Manually_Annotated" / "Manually_Annotated_Images"
        train = pd.read_csv(self.input_dir.parent / "training.csv")
        val = pd.read_csv(self.input_dir.parent / "validation.csv")
        self.df = pd.concat([train, val], ignore_index=True, sort=False)
        self.face_detector_type = 'fan'
        self.scale = scale
        self.use_processed = True
        self.ignore_invalid = ignore_invalid

        self.train_batch_size = train_batch_size
        self.val_batch_size = val_batch_size
        self.test_batch_size = test_batch_size
        self.num_workers = num_workers
        self.augmentation = augmentation

    @property
    def subset_size(self):
        return 1000

    @property
    def num_subsets(self):
        num_subsets = len(self.df) // self.subset_size
        if len(self.df) % self.subset_size != 0:
            num_subsets += 1
        return num_subsets

    def _detect_faces(self):
        subset_size = 1000
        num_subsets = len(self.df) // subset_size
        if len(self.df) % subset_size != 0:
            num_subsets += 1
        for sid in range(self.num_subsets):
            self._detect_landmarks_and_segment_subset(self.subset_size * sid, min((sid + 1) * self.subset_size, len(self.df)))

    def _path_to_detections(self):
        return Path(self.output_dir) / "detections"

    def _path_to_segmentations(self):
        return Path(self.output_dir) / "segmentations"

    def _path_to_landmarks(self):
        return Path(self.output_dir) / "landmarks"

    def _detect_landmarks_and_segment_subset(self, start_i, end_i):
        self._path_to_detections().mkdir(parents=True, exist_ok=True)
        self._path_to_segmentations().mkdir(parents=True, exist_ok=True)
        self._path_to_landmarks().mkdir(parents=True, exist_ok=True)

        detection_fnames = []
        out_segmentation_folders = []

        status_array = np.memmap(self.status_array_path,
                                 dtype=np.bool,
                                 mode='r',
                                 shape=(self.num_subsets,)
                                 )

        completed = status_array[start_i // self.subset_size]
        if not completed:
            print(f"Processing subset {start_i // self.subset_size}")
            for i in auto.tqdm(range(start_i, end_i)):
                im_file = self.df.loc[i]["subDirectory_filePath"]
                left = self.df.loc[i]["face_x"]
                top = self.df.loc[i]["face_y"]
                right = left + self.df.loc[i]["face_width"]
                bottom = top + self.df.loc[i]["face_height"]
                bb = np.array([top, left, bottom, right])

                im_fullfile = Path(self.input_dir) / im_file
                try:
                    detection, _, _, bbox_type, landmarks = self._detect_faces_in_image(im_fullfile, detected_faces=[bb])
                except Exception as e:
                # except ValueError as e:
                    print(f"Failed to load file:")
                    print(f"{im_fullfile}")
                    print(traceback.print_exc())
                    continue
                # except SyntaxError as e:
                #     print(f"Failed to load file:")
                #     print(f"{im_fullfile}")
                #     print(traceback.print_exc())
                #     continue

                out_detection_fname = self._path_to_detections() / Path(im_file).parent / (Path(im_file).stem + ".png")
                # detection_fnames += [out_detection_fname.relative_to(self.output_dir)]
                out_detection_fname.parent.mkdir(exist_ok=True)
                detection_fnames += [out_detection_fname]
                imsave(out_detection_fname, detection[0])

                # out_segmentation_folders += [self._path_to_segmentations() / Path(im_file).parent]

                # save landmarks
                out_landmark_fname = self._path_to_landmarks() / Path(im_file).parent / (Path(im_file).stem + ".pkl")
                out_landmark_fname.parent.mkdir(exist_ok=True)
                # landmark_fnames += [out_landmark_fname.relative_to(self.output_dir)]
                save_landmark(out_landmark_fname, landmarks[0], bbox_type)

            self._segment_images(detection_fnames, self._path_to_segmentations(), path_depth=1)

            status_array = np.memmap(self.status_array_path,
                                     dtype=np.bool,
                                     mode='r+',
                                     shape=(self.num_subsets,)
                                     )
            status_array[start_i // self.subset_size] = True
            status_array.flush()
            del status_array
            print(f"Processing subset {start_i // self.subset_size} finished")
        else:
            print(f"Subset {start_i // self.subset_size} is already processed")

    @property
    def status_array_path(self):
        return Path(self.output_dir) / "status.memmap"

    @property
    def is_processed(self):
        status_array = np.memmap(self.status_array_path,
                                 dtype=np.bool,
                                 mode='r',
                                 shape=(self.num_subsets,)
                                 )
        all_processed = status_array.all()
        return all_processed

    def prepare_data(self):
        if self.use_processed:
            if not self.status_array_path.is_file():
                print(f"Status file does not exist. Creating '{self.status_array_path}'")
                self.status_array_path.parent.mkdir(exist_ok=True, parents=True)
                status_array = np.memmap(self.status_array_path,
                                         dtype=np.bool,
                                         mode='w+',
                                         shape=(self.num_subsets,)
                                         )
                status_array[...] = False
                del status_array

            all_processed = self.is_processed
            if not all_processed:
                self._detect_faces()

    def setup(self, stage=None):
        self.train_dataframe_path = Path(self.root_dir) / "Manually_Annotated" / "training.csv"
        self.val_dataframe_path = Path(self.root_dir) / "Manually_Annotated" / "validation.csv"

        if self.use_processed:
            self.image_path = Path(self.output_dir) / "detections"
            # self.training_set = AffectNetOriginal(image_path, self.train_dataframe_path, self.image_size, self.scale,
            #                                       self.train_augmenter)
            # self.validation_set = AffectNetOriginal(image_path, self.val_dataframe_path, self.image_size, self.scale,
            #                                       self.val_augmenter)
        else:
            self.image_path = Path(self.output_dir) / "Manually_Annotated" / "Manually_Annotated_Images"

        im_transforms_train = create_image_augmenter(self.image_size, self.augmentation)
        self.training_set = AffectNet(self.image_path, self.train_dataframe_path, self.image_size, self.scale,
                                      im_transforms_train, ignore_invalid=self.ignore_invalid)
        self.validation_set = AffectNet(self.image_path, self.val_dataframe_path, self.image_size, self.scale,
                                        None, ignore_invalid=self.ignore_invalid)

        self.test_dataframe_path = Path(self.output_dir) / "validation_representative_selection.csv"
        self.test_set = AffectNet(self.image_path, self.test_dataframe_path, self.image_size, self.scale,
                                    None, ignore_invalid= self.ignore_invalid)
        # if self.mode in ['all', 'manual']:
        #     # self.image_list += sorted(list((Path(self.path) / "Manually_Annotated").rglob(".jpg")))
        #     self.dataframe = pd.load_csv(self.path / "Manually_Annotated" / "Manually_Annotated.csv")
        # if self.mode in ['all', 'automatic']:
        #     # self.image_list += sorted(list((Path(self.path) / "Automatically_Annotated").rglob("*.jpg")))
        #     self.dataframe = pd.load_csv(
        #         self.path / "Automatically_Annotated" / "Automatically_annotated_file_list.csv")

    def train_dataloader(self):
        dl = DataLoader(self.training_set, shuffle=True, num_workers=self.num_workers, batch_size=self.train_batch_size)
        return dl

    def val_dataloader(self):
        return DataLoader(self.validation_set, shuffle=False, num_workers=self.num_workers,
                          batch_size=self.val_batch_size)

    def test_dataloader(self):
        return DataLoader(self.test_set, shuffle=False, num_workers=self.num_workers,
                          batch_size=self.test_batch_size)


class AffectNetTestModule(AffectNetDataModule):

    def prepare_data(self):
        if not self.is_processed:
            raise RuntimeError("The dataset should have been processed but is not")

    def setup(self, stage=None):
        self.test_dataframe_path = Path(self.output_dir) / "validation_representative_selection.csv"
        if self.use_processed:
            self.image_path = Path(self.output_dir) / "detections"
        else:
            self.image_path = Path(self.output_dir) / "Manually_Annotated" / "Manually_Annotated_Images"
        self.test_set = AffectNet(self.image_path, self.test_dataframe_path, self.image_size, self.scale,
                                    None, self.ignore_invalid)

    def train_dataloader(self):
        raise NotImplementedError()

    def val_dataloader(self):
        # raise NotImplementedError()
        return None

    def test_dataloader(self):
        return DataLoader(self.test_set, shuffle=False, num_workers=self.num_workers,
                          batch_size=self.test_batch_size)


class AffectNet(EmotionalImageDatasetBase):

    def __init__(self,
                 image_path,
                 dataframe_path,
                 image_size,
                 scale = 1.4,
                 transforms : imgaug.augmenters.Augmenter = None,
                 use_gt_bb=True,
                 ignore_invalid=False,
                 ):
        self.dataframe_path = dataframe_path
        self.image_path = image_path
        self.df = pd.read_csv(dataframe_path)
        self.image_size = image_size
        self.use_gt_bb = use_gt_bb
        self.transforms = transforms or imgaug.augmenters.Identity()
        self.scale = scale
        self.landmark_normalizer = KeypointNormalization()
        self.use_processed = True
        self.ignore_invalid = ignore_invalid

        if ignore_invalid:
            # filter invalid classes
            ignored_classes = [AffectNetExpressions.Uncertain.value, AffectNetExpressions.Occluded.value]
            self.df = self.df[self.df["expression"].isin(ignored_classes) == False]
            # self.df = self.df.drop(self.df[self.df["expression"].isin(ignored_classes)].index)

            # filter invalid va values
            self.df = self.df[self.df.valence != -2.]
            # self.df = self.df.drop(self.df.valence == -2.)
            self.df = self.df[self.df.arousal != -2.]
            # self.df = self.df.drop(self.df.arousal == -2.)
            self.df = self.df.reset_index(drop=True)


    def __len__(self):
        return len(self.df)

    def __getitem__(self, index):
        left = self.df.loc[index]["face_x"]
        top = self.df.loc[index]["face_y"]
        right = left + self.df.loc[index]["face_width"]
        bottom = top + self.df.loc[index]["face_height"]
        facial_landmarks = self.df.loc[index]["facial_landmarks"]
        expression = self.df.loc[index]["expression"]
        valence = self.df.loc[index]["valence"]
        arousal = self.df.loc[index]["arousal"]

        try:
            im_rel_path = self.df.loc[index]["subDirectory_filePath"]
            im_file = Path(self.image_path) / im_rel_path
            im_file = im_file.parent / (im_file.stem + ".png")
            input_img = imread(im_file)
        except Exception as e:
            # if the image is corrupted or missing (there is a few :-/), find some other one
            while True:
                index += 1
                index = index % len(self)
                im_rel_path = self.df.loc[index]["subDirectory_filePath"]
                im_file = Path(self.image_path) / im_rel_path
                im_file = im_file.parent / (im_file.stem + ".png")
                try:
                    input_img = imread(im_file)
                    success = True
                except Exception as e2:
                    success = False
                if success:
                    break
        input_img_shape = input_img.shape

        if not self.use_processed:
            # Use AffectNet as is provided (their bounding boxes, and landmarks, no segmentation)
            old_size, center = bbox2point(left, right, top, bottom, type='kpt68')
            size = int(old_size * self.scale)
            input_landmarks = np.array([float(f) for f in facial_landmarks.split(";")]).reshape(-1,2)
            img, landmark = bbpoint_warp(input_img, center, size, self.image_size, landmarks=input_landmarks)
            img *= 255.

            if not self.use_gt_bb:
                raise NotImplementedError()
                # landmark_type, landmark = load_landmark(
                #     self.path_prefix / self.landmark_list[index])
            landmark = landmark[np.newaxis, ...]
            seg_image = None
        else:
            # use AffectNet processed by me. I used their bounding boxes (to not have to worry about detecting
            # the correct face in case there's more) and I ran our FAN and segmentation over it
            img = input_img

            # the image has already been cropped in preprocessing (make sure the input root path
            # is specificed to the processed folder and not the original one

            landmark_path = Path(self.image_path).parent / "landmarks" / im_rel_path
            landmark_path = landmark_path.parent / (landmark_path.stem + ".pkl")

            landmark_type, landmark = load_landmark(
                landmark_path)
            landmark = landmark[np.newaxis, ...]

            segmentation_path = Path(self.image_path).parent / "segmentations" / im_rel_path
            segmentation_path = segmentation_path.parent / (segmentation_path.stem + ".pkl")

            seg_image, seg_type = load_segmentation(
                segmentation_path)
            seg_image = seg_image[np.newaxis, :, :, np.newaxis]

            seg_image = process_segmentation(
                seg_image, seg_type).astype(np.uint8)

        img, seg_image, landmark = self._augment(img, seg_image, landmark)

        sample = {
            "image": numpy_image_to_torch(img),
            "path": str(im_file),
            "affectnetexp": torch.tensor([expression, ]),
            "va": torch.tensor([valence, arousal]),
            "label": str(im_file.stem),
        }

        if landmark is not None:
            sample["landmark"] = torch.from_numpy(landmark)
        if seg_image is not None:
            sample["mask"] = numpy_image_to_torch(seg_image)
        # print(self.df.loc[index])
        return sample


def sample_representative_set(dataset, output_file, sample_step=0.1, num_per_bin=2):
    va_array = []
    size = int(2 / sample_step)
    for i in range(size):
        va_array += [[]]
        for j in range(size):
            va_array[i] += [[]]

    print("Binning dataset")
    for i in auto.tqdm(range(len(dataset.df))):
        v = max(-1., min(1., dataset.df.loc[i]["valence"]))
        a = max(-1., min(1., dataset.df.loc[i]["arousal"]))
        row_ = int((v + 1) / sample_step)
        col_ = int((a + 1) / sample_step)
        va_array[row_][ col_] += [i]


    selected_indices = []
    for i in range(len(va_array)):
        for j in range(len(va_array[i])):
            if len(va_array[i][j]) > 0:
                # selected_indices += [va_array[i][j][0:num_per_bin]]
                selected_indices += va_array[i][j][0:num_per_bin]
            else:
                print(f"No value for {i} and {j}")

    selected_samples = dataset.df.loc[selected_indices]
    selected_samples.to_csv(output_file)
    print(f"Selected samples saved to '{output_file}'")



if __name__ == "__main__":
    # d = AffectNetOriginal(
    #     "/home/rdanecek/Workspace/mount/project/EmotionalFacialAnimation/data/affectnet/Manually_Annotated/Manually_Annotated_Images",
    #     "/home/rdanecek/Workspace/mount/project/EmotionalFacialAnimation/data/affectnet/Manually_Annotated/validation.csv",
    #     224
    # )
    # print(f"Num sample {len(d)}")
    # for i in range(100):
    #     sample = d[i]
    #     d.visualize_sample(sample)

    dm = AffectNetDataModule(
             "/home/rdanecek/Workspace/mount/project/EmotionalFacialAnimation/data/affectnet/",
             "/home/rdanecek/Workspace/mount/scratch/rdanecek/data/affectnet/",
             # processed_subfolder="processed_2021_Apr_02_03-13-33",
             processed_subfolder="processed_2021_Apr_05_15-22-18",
             mode="manual",
             scale=1.25,
             ignore_invalid=True
            )
    print(dm.num_subsets)
    dm.prepare_data()
    dm.setup()
    # dl = dm.val_dataloader()
    print(f"len training set: {len(dm.training_set)}")
    print(f"len validation set: {len(dm.validation_set)}")

    out_path = Path(dm.output_dir) / "validation_representative_selection_.csv"
    sample_representative_set(dm.validation_set, out_path)

    validation_set = AffectNet(dm.image_path, out_path, dm.image_size, dm.scale, None)
    for i in range(len(validation_set)):
        sample = validation_set[i]
        validation_set.visualize_sample(sample)

    # dl = DataLoader(validation_set, shuffle=False, num_workers=1, batch_size=1)

    "/home/rdanecek/Workspace/mount/scratch/rdanecek/data/affectnet/processed_2021_Apr_02_03-13-33/validation_representative_selection_.csv"

    # dm._detect_faces()