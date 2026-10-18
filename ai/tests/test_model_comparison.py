import importlib.util
import unittest
HAS_TORCH=importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from ai.compare_models import build,head,configure,training_mode,frozen_digest,score,validate_tuning_config
    from ai.train_baseline import seed_everything


@unittest.skipUnless(HAS_TORCH,'Requires .venv-ai')
class ModelComparisonTests(unittest.TestCase):
    def test_all_architectures_have_eight_outputs_and_respect_both_stage_boundaries(self):
        seed_everything(3403,2)
        for arch in ('efficientnet_b0','resnet50','densenet121'):
            with self.subTest(architecture=arch):
                model=build(arch,pretrained=False)
                for full in (False,True):
                    configure(model,arch,full); before=frozen_digest(model)
                    training_mode(model,arch,full)
                    for module in model.modules():
                        if isinstance(module,torch.nn.modules.batchnorm._BatchNorm):
                            self.assertFalse(module.training)
                            self.assertFalse(any(p.requires_grad for p in module.parameters()))
                    optim=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-3)
                    output=model(torch.randn(2,3,64,64))
                    self.assertEqual(tuple(output.shape),(2,8))
                    torch.nn.functional.cross_entropy(output,torch.tensor([0,7])).backward(); optim.step()
                    self.assertEqual(before,frozen_digest(model))
                    if full:
                        head_ids={id(p) for p in head(model,arch).parameters()}
                        self.assertTrue(any(p.grad is not None for p in model.parameters() if p.requires_grad and id(p) not in head_ids))

    def test_accuracy_target_selection_does_not_replace_ties_arbitrarily(self):
        a={'accuracy':.7,'macro_f1':.5,'loss':1.0}
        self.assertGreater(score(a),score({'accuracy':.69,'macro_f1':.6,'loss':.5}))
        self.assertGreater(score({**a,'macro_f1':.6}),score(a))
        self.assertGreater(score({**a,'loss':.9}),score(a))

    def test_partial_tuning_preserves_lower_blocks_and_batchnorm(self):
        seed_everything(3403,2)
        model=build('efficientnet_b0',pretrained=False)
        blocks=[6,7,8]
        configure(model,'efficientnet_b0',True,blocks)
        before=frozen_digest(model)
        training_mode(model,'efficientnet_b0',True,blocks)
        self.assertFalse(model.features[5].training)
        self.assertTrue(model.features[6].training)
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-3)
        loss=torch.nn.functional.cross_entropy(model(torch.randn(2,3,64,64)),torch.tensor([0,7]))
        loss.backward();optimizer.step()
        self.assertEqual(before,frozen_digest(model))
        for i in blocks:self.assertTrue(any(p.grad is not None for p in model.features[i].parameters()))
        for i in range(6):self.assertTrue(all(p.grad is None for p in model.features[i].parameters()))
        with self.assertRaises(ValueError):configure(model,'efficientnet_b0',True,[5,6,7,8])

    def test_tuning_configs_only_change_predeclared_settings(self):
        import json
        from pathlib import Path
        root=Path(__file__).resolve().parents[2]
        control=json.loads((root/'ai/model_comparison_config.json').read_text())
        for name in ('lower_lr_full','partial_freeze'):
            config=json.loads((root/f'ai/tuning_{name}_config.json').read_text())
            validate_tuning_config(config,control)
            with self.assertRaises(ValueError):validate_tuning_config(dict(config,seed=999),control)
            with self.assertRaises(ValueError):validate_tuning_config(dict(config,feature_lr=.01),control)


if __name__=='__main__': unittest.main()
