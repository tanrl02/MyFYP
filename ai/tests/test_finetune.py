"""Protect the fine-tuning boundary: early layers and all BatchNorm stay frozen."""
import unittest
import importlib.util

HAS_TORCH = importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from ai.train_baseline import build_model, seed_everything
    from ai.train_finetune import configure_trainable, training_mode, state_checks


@unittest.skipUnless(HAS_TORCH, 'Fine-tuning checks require .venv-ai')
class FineTuneTests(unittest.TestCase):
    def test_optimizer_updates_upper_features_and_head_only(self):
        seed_everything(3403, 2)
        model = build_model(8, pretrained=False)
        source = {key: value.clone() for key, value in model.state_dict().items()}
        configure_trainable(model, [6, 7, 8])
        training_mode(model, [6, 7, 8])
        self.assertFalse(model.features[5].training)
        self.assertTrue(model.features[6].training)
        self.assertTrue(model.classifier.training)
        for module in model.modules():
            if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
                self.assertFalse(module.training)
                self.assertFalse(any(p.requires_grad for p in module.parameters()))
        optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=0.001)
        loss = torch.nn.functional.cross_entropy(model(torch.randn(2, 3, 64, 64)), torch.tensor([0, 7]))
        loss.backward(); optimizer.step()
        checks = state_checks(model, source, [6, 7, 8])
        self.assertTrue(checks['frozen_parameters_and_buffers_unchanged'])
        self.assertTrue(all(checks['changed_feature_blocks'].values()))
        # Catch an accidentally mutated frozen buffer even without a gradient.
        model.features[0][1].running_mean.add_(1)
        with self.assertRaises(ValueError): state_checks(model, source, [6, 7, 8])

    def test_reject_wrong_block_boundary(self):
        with self.assertRaises(ValueError): configure_trainable(build_model(8, pretrained=False), [5, 6, 7, 8])


if __name__ == '__main__': unittest.main()
