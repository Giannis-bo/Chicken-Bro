import base64
import io
import unittest
from server.app.chickenbro.images import normalize_image, ImageError, MAX_BYTES
from PIL import Image, PngImagePlugin


def picture(size=(20, 30)):
    output = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('private', 'must disappear')
    Image.new('RGB', size, 'red').save(output, format='PNG', pnginfo=metadata)
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


class ImageValidationTest(unittest.TestCase):
    def test_decodes_and_strips_metadata(self):
        image = normalize_image(picture())
        self.assertEqual((image.width, image.height, image.mime_type), (20, 30, 'image/png'))
        self.assertNotIn(b'must disappear', image.data)
        Image.open(io.BytesIO(image.data)).load()

    def test_rejects_executable_corrupt_mismatched_and_oversized_inputs(self):
        for value in ['data:image/svg+xml;base64,PHN2Zz4=', 'https://example.com/a.png',
                      'data:image/png;base64,AAAA', picture().replace('image/png', 'image/jpeg'),
                      'data:image/png;base64,' + 'A' * (4 * (MAX_BYTES // 3 + 2)),
                      picture((8193, 1))]:
            with self.subTest(size=len(value)), self.assertRaises(ImageError):
                normalize_image(value)

    def test_rejects_animated_png_and_excessive_pixel_count(self):
        output=io.BytesIO()
        first=Image.new('RGB',(10,10),'red')
        first.save(output,format='PNG',save_all=True,append_images=[Image.new('RGB',(10,10),'blue')])
        for value in ['data:image/png;base64,'+base64.b64encode(output.getvalue()).decode(),picture((5000,4001))]:
            with self.assertRaises(ImageError): normalize_image(value)

    def test_jpeg_orientation_applied_before_exif_is_removed(self):
        output=io.BytesIO()
        source=Image.new('RGB',(20,30),'red')
        exif=Image.Exif()
        exif[274]=6
        source.save(output,format='JPEG',exif=exif)
        image=normalize_image('data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode())
        self.assertEqual((image.width,image.height),(30,20))
        with Image.open(io.BytesIO(image.data)) as decoded:
            self.assertFalse(decoded.getexif())
