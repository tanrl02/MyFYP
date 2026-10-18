"""Pinned local research classifier. No training, downloads or clinical decisions."""
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
from threading import Lock
from PIL import Image,ImageOps
from .store import RuleError

ROOT=Path(__file__).resolve().parents[3]
CONFIG=Path(__file__).resolve().parents[1]/'disease_model.json'
LABELS={'acne':'Acne','eczema':'Eczema','psoriasis':'Psoriasis','folliculitis':'Folliculitis',
        'urticaria':'Urticaria','allergic_contact_dermatitis':'Allergic contact dermatitis',
        'seborrheic_dermatitis':'Seborrhoeic dermatitis','scabies':'Scabies'}


class DiseaseModel:
    def __init__(self,config_path=CONFIG):
        self.config=json.loads(Path(config_path).read_text())
        config=self.config
        path=(ROOT/config['checkpoint_path']).resolve()
        if not path.is_relative_to((ROOT/'ai/runs').resolve()):raise ValueError('Checkpoint path outside local runs')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=config['checkpoint_sha256']:raise ValueError('Disease checkpoint hash mismatch')
        if config['preprocessing']!='exif_rgb_official_centre_crop_v1' or config['architecture']!='efficientnet_b0':
            raise ValueError('Unsupported disease model contract')
        import torch
        from torchvision.models import efficientnet_b0,EfficientNet_B0_Weights
        torch.set_num_threads(4)
        checkpoint=torch.load(path,map_location='cpu',weights_only=True)
        metadata=checkpoint['metadata'];mapping=config['class_to_index']
        if mapping!=metadata['class_to_index'] or set(mapping)!=set(LABELS) or sorted(mapping.values())!=list(range(8)):
            raise ValueError('Disease class mapping mismatch')
        if checkpoint['epoch']!=config['epoch'] or metadata['config']['dataset_version']!=config['dataset_version']:
            raise ValueError('Disease checkpoint version mismatch')
        if abs(checkpoint['validation']['accuracy']-config['validation_accuracy'])>1e-10:
            raise ValueError('Validation metadata mismatch')
        self.model=efficientnet_b0(weights=None)
        self.model.classifier[-1]=torch.nn.Linear(self.model.classifier[-1].in_features,8)
        self.model.load_state_dict(checkpoint['model_state_dict'],strict=True);self.model.eval()
        self.transform=EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()
        if repr(self.transform)!=metadata['validation_transform']:raise ValueError('Preprocessing differs from training evaluation')
        self.classes=sorted(mapping,key=mapping.get);self.lock=Lock()

    def predict(self,content):
        import torch
        with Image.open(BytesIO(content)) as source:image=ImageOps.exif_transpose(source).convert('RGB')
        with self.lock,torch.inference_mode():
            logits=self.model(self.transform(image).unsqueeze(0))
            if logits.shape!=(1,8) or not torch.isfinite(logits).all():raise ValueError('Invalid disease model output')
            scores=logits.softmax(dim=1)[0]
            indices=sorted(range(8),key=lambda index:(-float(scores[index]),index))[:3]
            top=[{'condition':self.classes[index],'label':LABELS[self.classes[index]],'score':float(scores[index])} for index in indices]
        return {key:self.config[key] for key in ('model_id','checkpoint_sha256','preprocessing','dataset_version',
                'validation_accuracy','validation_macro_f1','validation_cases','test_evaluated')} | {
            'top_predictions':top,'input_sha256':hashlib.sha256(content).hexdigest(),
            'created_at':datetime.now(timezone.utc).isoformat()}


_model=None
_initialise=Lock()


def predict_disease(content):
    global _model
    try:
        with _initialise:
            if _model is None:_model=DiseaseModel()
        return _model.predict(content)
    except (ImportError,OSError,RuntimeError,ValueError,KeyError) as error:
        raise RuleError('The experimental disease model is unavailable. No new assessment was saved. Restart the API with its AI environment and retry.',503) from error
