"""Delivery contract tests: dated names, mandatory portrait art and no clobbering."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import v4_package as package


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.folder=Path(self.tmp.name)
        self.video=self.folder/'source.mp4';self.video.write_bytes(b'video-fixture')
        self.thumb=self.folder/'cover.jpg';self.thumb.write_bytes(b'image-fixture')
        self.root=self.folder/'packages'
        self.meta={'title':'Los Santos Was Home #Shorts','description':'Source credit and tribute description.',
                   'tags':['GTA 5','Shorts'],'keywords':['GTA nostalgia'],'file':str(self.video),
                   'payoff_review':{'setup':'The shared memories.','resolution':'A complete final thank-you.',
                                    'why_it_resolves':'It completes the farewell.','reviewed_by':'test reviewer'},
                   'ending_audit':{'passed':True,'last_word':'you.'},'upload':False}
        self.media=patch('v4_media.probe',return_value={'duration':52.4,'streams':[
            {'codec_type':'video','codec_name':'h264','width':1080,'height':1920}]})
        self.dimensions=patch('v4_package.thumbnail_size',return_value=(1080,1920))
        self.media.start();self.dimensions.start()
    def tearDown(self):
        self.dimensions.stop();self.media.stop();self.tmp.cleanup()
    def build(self,**changes):
        args={'video':self.video,'thumbnail':self.thumb,'metadata':self.meta,'root':self.root,
              'short_title':'Los Santos Was Home','day':'2026-11-17'}
        args.update(changes)
        return package.build_package(**args)
    def test_readable_dated_complete_package(self):
        out=self.build()
        self.assertEqual(out.name,'los-santos-was-home_2026-11-17')
        for name in ['video.mp4','thumbnail.jpg','metadata.json','UPLOAD-DETAILS.txt',
                     'README.txt','ending-audit.json','payoff-review.json','manifest.json']:
            self.assertTrue((out/name).is_file(),name)
        meta=json.loads((out/'metadata.json').read_text())
        self.assertEqual(meta['file'],'video.mp4')
        self.assertEqual(meta['thumbnail'],'thumbnail.jpg')
        self.assertIn('Source credit',(out/'UPLOAD-DETAILS.txt').read_text())
        self.assertEqual((out/'video.mp4').read_bytes(),self.video.read_bytes())
        package.validate_package(out)
    def test_same_day_revision_never_overwrites(self):
        first=self.build();original=(first/'manifest.json').read_bytes()
        second=self.build()
        self.assertEqual(second.name,'los-santos-was-home_2026-11-17_v2')
        self.assertEqual((first/'manifest.json').read_bytes(),original)
    def test_portable_package_can_be_saved_as_a_new_revision(self):
        first=self.build()
        meta=json.loads((first/'metadata.json').read_text())
        second=self.build(video=first/'video.mp4',thumbnail=first/'thumbnail.jpg',metadata=meta)
        self.assertEqual(second.name,'los-santos-was-home_2026-11-17_v2')
        self.assertEqual((first/'video.mp4').read_bytes(),(second/'video.mp4').read_bytes())
    def test_missing_or_wrong_thumbnail_is_not_packaged(self):
        with patch('v4_package.thumbnail_size',side_effect=ValueError('thumbnail must be portrait')):
            with self.assertRaisesRegex(ValueError,'portrait'):self.build()
        self.assertFalse(self.root.exists())
    def test_failed_ending_or_missing_payoff_is_not_packaged(self):
        for field,value in [('ending_audit',{'passed':False}),('payoff_review',{})]:
            with self.subTest(field=field):
                meta={**self.meta,field:value}
                with self.assertRaises(ValueError):self.build(metadata=meta)
        self.assertFalse(self.root.exists())
    def test_other_video_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'different video'):
            self.build(metadata={**self.meta,'file':str(self.folder/'other.mp4')})
    def test_bad_date_and_unsafe_title_do_not_create_packages(self):
        with self.assertRaises(ValueError):self.build(day='2026-02-30')
        with self.assertRaises(ValueError):self.build(short_title='../../')
        self.assertFalse(self.root.exists())
        self.assertEqual(package.short_slug('GTA 5: Home! #Shorts'),'gta-5-home')
    def test_deleting_thumbnail_or_altering_video_invalidates_package(self):
        out=self.build();(out/'thumbnail.jpg').unlink()
        with self.assertRaisesRegex(ValueError,'missing'):package.validate_package(out)
        out=self.build();(out/'video.mp4').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):package.validate_package(out)
    def test_portrait_dimensions_are_checked_from_media(self):
        self.dimensions.stop()
        with patch('v4_package.subprocess.run',return_value=type('Result',(),{
                'stdout':json.dumps({'streams':[{'width':1280,'height':720}]})})()):
            with self.assertRaisesRegex(ValueError,'1080x1920'):package.thumbnail_size(self.thumb)
        with patch('v4_package.subprocess.run',return_value=type('Result',(),{
                'stdout':json.dumps({'streams':[{'width':1080,'height':1920}]})})()):
            self.assertEqual(package.thumbnail_size(self.thumb),(1080,1920))
    def test_long_clip_is_preserved_and_optional_artifacts_are_copied(self):
        ass=self.folder/'captions.ass';ass.write_text('caption fixture')
        prompt=self.folder/'prompt.txt';prompt.write_text('image prompt fixture')
        out=self.build(captions=ass,thumbnail_prompt=prompt)
        m=package.validate_package(out)
        self.assertEqual(m['duration'],52.4)
        self.assertEqual((out/'captions.ass').read_text(),'caption fixture')
        self.assertEqual((out/'THUMBNAIL-PROMPT.txt').read_text(),'image prompt fixture')


if __name__=='__main__':
    unittest.main()
