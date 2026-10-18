"""Predeclared synthetic lighting probes and candidate guard; no clinical claim."""
from PIL import ImageEnhance


class BrightnessProbe:
    def __init__(self,factor):self.factor=factor
    def __call__(self,image):return ImageEnhance.Brightness(image).enhance(self.factor)
    def __repr__(self):return f'BrightnessProbe({self.factor})'


def candidate_guard(control,candidate):
    reference=control['validation'];metrics=candidate['validation']
    recall_drops=[a['recall']-b['recall'] for a,b in zip(reference['per_class'],metrics['per_class'])]
    checks={'higher_clean_accuracy':metrics['accuracy']>reference['accuracy'],
        'higher_clean_macro_f1':metrics['macro_f1']>reference['macro_f1'],
        'no_recall_drop_over_10_percentage_points':max(recall_drops)<=.10+1e-9,
        'lighting_probe_mean_accuracy_not_lower':candidate['lighting_probe_mean_accuracy']+1e-9>=control['lighting_probe_mean_accuracy']}
    return {'checks':checks,'passes':all(checks.values()),'largest_class_recall_drop':max(recall_drops)}
