import importlib.util
import unittest

HAS_TORCH = importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    import torch
    from PIL import Image
    from ai.preprocessing import FullFrame224, fit_geometry, MEAN, STD


@unittest.skipUnless(HAS_TORCH, 'Geometry checks require .venv-ai')
class FullFrameTests(unittest.TestCase):
    def test_edges_survive_landscape_and_portrait_with_neutral_padding(self):
        for dimensions in ((448, 224), (224, 448)):
            image = Image.new('RGB', dimensions, 'white')
            # Four distinct broad corner markers expose centre cropping or flipping.
            colours = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0))
            width, height = dimensions
            for colour, box in zip(colours, ((0, 0, 64, 64), (width-64, 0, width, 64),
                                            (0, height-64, 64, height), (width-64, height-64, width, height))):
                image.paste(colour, box)
            result = FullFrame224()(image)
            w, h, left, top = fit_geometry(width, height)
            self.assertEqual(tuple(result.shape), (3, 224, 224))
            self.assertTrue(torch.isfinite(result).all())
            for colour, (x, y) in zip(colours, ((left+4, top+4), (left+w-5, top+4),
                                              (left+4, top+h-5), (left+w-5, top+h-5))):
                expected = torch.tensor([(value/255-mean)/std for value, mean, std in zip(colour, MEAN, STD)])
                torch.testing.assert_close(result[:, y, x], expected)
            if top: self.assertEqual(torch.count_nonzero(result[:, :top]).item(), 0)
            if left: self.assertEqual(torch.count_nonzero(result[:, :, :left]).item(), 0)

    def test_dimensions_preserve_scale_with_integer_rounding(self):
        for width, height in ((603, 343), (314, 426), (1277, 1255), (1, 10000), (10000, 1), (224, 224)):
            w, h, left, top = fit_geometry(width, height)
            self.assertEqual(max(w, h), 224)
            scale = 224 / max(width, height)
            self.assertLessEqual(abs(w-width*scale), 1)
            self.assertLessEqual(abs(h-height*scale), 1)
            self.assertLessEqual(abs(left - (224-w-left)), 1)
            self.assertLessEqual(abs(top - (224-h-top)), 1)
        with self.assertRaises(ValueError): fit_geometry(0, 100)

    def test_square_has_no_padding_and_is_deterministic(self):
        image = Image.new('RGB', (400, 400), (50, 100, 150))
        first, second = FullFrame224()(image), FullFrame224()(image)
        self.assertTrue(torch.equal(first, second))
        self.assertTrue(torch.equal(first[:, 0, 0], first[:, 223, 223]))


if __name__ == '__main__': unittest.main()
