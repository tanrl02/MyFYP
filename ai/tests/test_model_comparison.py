import importlib.util
import unittest
HAS_TORCH=importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from ai.compare_models import build,head,configure,training_mode,frozen_digest,score
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


if __name__=='__main__': unittest.main()
