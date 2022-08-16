import imp
from pathlib import Path 
from gdl.models.temporal.SequenceEncoders import *
from gdl.models.temporal.SequenceDecoders import *
from gdl.models.temporal.TemporalFLAME import FlameShapeModel
from gdl.models.temporal.Renderers import FlameRenderer
from gdl.models.temporal.AudioEncoders import AvHubertAudioEncoder, Wav2Vec2Encoder
from gdl.models.temporal.VideoEncoders import EmocaVideoEncoder


def load_avhubert_model(ckpt_path):
    from fairseq import checkpoint_utils, options, tasks, utils
    if str(path_to_av_hubert) not in sys.path:
        sys.path.insert(0, str(path_to_av_hubert))
    import avhubert
    models, saved_cfg, task = checkpoint_utils.load_model_ensemble_and_task([ckpt_path])
    #   models = [model.eval().cuda() for model in models]
    return models, saved_cfg, task


def sequence_encoder_from_cfg(cfg):
    if cfg.type == "avhubert": 
        path = Path(cfg.checkpoint_folder) / cfg.model_filename
        models, saved_cfg, task = load_avhubert_model(str(path))
        encoder = AvHubertSequenceEncoder(models[0])
    elif cfg.type in ["simple_transformer", "stf"]: 
        encoder = SimpleTransformerSequenceEncoder(cfg)
    elif cfg.type in ["linear"]: 
        encoder = LinearSequenceEncoder(cfg)
    elif cfg.type in ["mlp"]: 
        encoder = MLPSequenceEncoder(cfg)
    elif cfg.type in ["gru"]:
        encoder = GRUSeqEnc(cfg)
    elif cfg.type in ["temporal_cnn"]:
        encoder = TemporalConvNet(cfg)
    elif cfg.type in ["parallel"]:
        encoder = ParallelSequenceEncoder(cfg)
    else: 
        raise ValueError(f"Unknown sequence encoder model type '{cfg.type}'")
    return encoder 


class ParallelSequenceEncoder(SequenceEncoder): 
    
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        encoders = []
        self.outputs = []
        self.input_feature_dim_ = None
        assert len(cfg.encoders) > 1, "At least two encoders are required"
        self.names = []
        for encoder_cfg in cfg.encoders:
            name = list(encoder_cfg.keys())[0]
            encoder = sequence_encoder_from_cfg(encoder_cfg[name].cfg)
            if self.input_feature_dim_ is None:
                self.input_feature_dim_ = encoder.input_feature_dim()
            assert self.input_feature_dim_ == encoder.input_feature_dim(), \
                "All encoders must have the same input feature dim"
            encoders += [encoder]
            self.outputs += [encoder_cfg.outputs]
            self.names += [name]
        self.encoders = torch.nn.ModuleList(encoders)

    def get_trainable_parameters(self): 
        return list(self.parameters())

    def input_feature_dim(self):
        # return self.cfg.feature_dim
        return self.input_feature_dim_

    def output_feature_dim(self):
        # dim = 0 
        # for encoder in self.encoders:
        #     dim += encoder.output_feature_dim() 
        dim = self.encoders[0].output_feature_dim()
        return dim

    def forward(self, sample):
        input_feature = sample["fused_feature"]
        # results = []
        results = {}
        for ei, encoder in enumerate(self.encoders):
            # results += [encoder(x)]
            sample_ = {} 
            sample_["fused_feature"] = input_feature 
            results[self.names[ei]] = encoder(sample_)["seq_encoder_output"]
        # results = torch.cat(results, dim=1)
        sample["seq_encoder_output"] = results
        return sample


    

def face_model_from_cfg(cfg): 
    if cfg.type in ["flame", "flame_mediapipe"]: 
        return FlameShapeModel(cfg)
    else:
        raise ValueError(f"Unknown face model type '{cfg.type}'")


def renderer_from_cfg(cfg):
    if cfg.type in ["deca", "emoca"]: 
        renderer = FlameRenderer(cfg)
    else: 
        raise ValueError(f"Unknown renderer model type '{cfg.type}'")
    return renderer


def norm_from_cfg(cfg, input_tensor_shape):
    if cfg is None or cfg.type == "none":
        return None
    elif cfg.type == "batchnorm2d":
        assert len(input_tensor_shape) == 4 # B, C, H, W
        return torch.nn.BatchNorm2d(input_tensor_shape[1])
    elif cfg.type == "instancenorm2d":
        assert len(input_tensor_shape) == 4 # B, C, H, W
        return torch.nn.InstanceNorm2d(input_tensor_shape[1]) 
    elif cfg.type == "batchnorm1d":
        assert len(input_tensor_shape) == 2 # B, F
        return torch.nn.BatchNorm1d(input_tensor_shape[1])
    elif cfg.type == "instancenorm1d":
        assert len(input_tensor_shape) == 2 # B, F
        return torch.nn.InstanceNorm1d(input_tensor_shape[1])
    elif cfg.type == "layernorm_temporal":
        assert len(input_tensor_shape) == 3  # B, T, F
        return torch.nn.LayerNorm(input_tensor_shape[2])
    elif cfg.type == "layernorm_image":
        assert len(input_tensor_shape) == 4 # B, C, H, W
        return torch.nn.LayerNorm(input_tensor_shape[1:])
    else:
        raise ValueError(f"Unknown norm type '{cfg.type}'")


def video_encoder_from_cfg(cfg):
    if cfg.type == "none":
        return None
    if cfg.type == "emoca": 
        # instantate EMOCA 
        from gdl_apps.EMOCA.utils.io import load_model
        mode = "detail"
        path_to_models = Path(cfg.path).parent 
        model_name = Path(cfg.path).name
        emoca, emoca_cfg =  load_model(path_to_models, model_name, mode)
        return EmocaVideoEncoder(emoca,  cfg.use_features, cfg.use_shapecode, 
                                cfg.use_expcode, cfg.use_texcode, cfg.use_jawpose, cfg.use_globalpose,
                                cfg.use_lightcode, 
                                # cfg.use_posecode, 
                                cfg.use_cam, 
                                cfg.trainable, 
                                cfg.get('discard_feature', False),)
    elif cfg.type == "deca": 
        from gdl_apps.EMOCA.utils.io import load_model
        mode = "detail"
        path_to_models = Path(cfg.path_to_models).parent 
        model_name = Path(cfg.path_to_models).name
        deca =  load_model(path_to_models, model_name, mode)
        return deca

    # elif cfg.type == "linear":
    #     LinearVideoEncoder

    raise ValueError(f"Unknown video encoder type '{cfg.type}'")


def audio_model_from_cfg(cfg):
    if cfg.type == "none":
        return None
    if cfg.type == "avhubert": 
        path = Path(cfg.checkpoint_folder) / cfg.model_filename
        models, saved_cfg, task = load_avhubert_model(str(path))
        if 'audio' not in saved_cfg.task.modalities:
            raise ValueError("This AVHubert model does not support audio")
        encoder = AvHubertAudioEncoder(models[0], cfg.trainable)
    elif cfg.type == "wav2vec2": 
        encoder = Wav2Vec2Encoder(cfg.model_specifier, cfg.trainable)
    else: 
        raise ValueError(f"Unknown audio model type '{cfg.type}'")

    return encoder


def sequence_decoder_from_cfg(cfg):
    decoder_cfg = cfg.model.sequence_decoder
    if decoder_cfg is None or decoder_cfg.type in ["none", "no"]:
        return None
    elif decoder_cfg.type == "avhubert": 
        path = Path(cfg.checkpoint_folder) / cfg.model_filename
        models, saved_cfg, task = load_avhubert_model(str(path))
        decoder = AvHubertSequenceDecoder(models[0])
    elif decoder_cfg.type == "fairseq": 
        output_dim = 0 
        if cfg.model.output.predict_shapecode: 
            output_dim += cfg.model.sizes.n_shape 
        if cfg.model.output.predict_expcode:
            output_dim += cfg.model.sizes.n_exp
        if cfg.model.output.predict_texcode:
            output_dim += cfg.model.sizes.n_tex
        # if cfg.model.output.predict_posecode:
        #     output_dim += cfg.model.sizes.n_pose
        if cfg.model.output.predict_jawpose:
            output_dim += cfg.model.sizes.n_pose // 2
        if cfg.model.output.predict_globalpose:
            output_dim += cfg.model.sizes.n_pose // 2
        if cfg.model.output.predict_cam:
            output_dim += cfg.model.sizes.n_cam
        if cfg.model.output.predict_light:
            output_dim += cfg.model.sizes.n_light
        if cfg.model.output.predict_detail:
            output_dim += cfg.model.sizes.n_detail
        
        with open_dict(decoder_cfg):
            decoder_cfg.output_layer_size = output_dim

        decoder = FairSeqModifiedDecoder(decoder_cfg)

    else: 
        raise ValueError(f"Unknown sequence decoder model type '{cfg.type}'")

    return decoder