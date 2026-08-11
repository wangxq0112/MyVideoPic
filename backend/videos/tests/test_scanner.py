"""Scanner tests that do not access user media directories."""

from unittest.mock import patch

from django.test import SimpleTestCase

from videos import scanner
from videos.scanning.detect import detect_file


class FileDetectionTests(SimpleTestCase):
    def test_detect_file_is_case_insensitive(self):
        self.assertEqual(detect_file('movie.MKV'), 'video')
        self.assertEqual(detect_file('photo.JpEg'), 'photo')
        self.assertIsNone(detect_file('notes.txt'))


class ScanQueueTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        with scanner._lock:
            scanner._scan_tasks.clear()
            scanner._queued_library_ids.clear()
            scanner._active_task_id = None

    def tearDown(self):
        with scanner._lock:
            scanner._scan_tasks.clear()
            scanner._queued_library_ids.clear()
            scanner._active_task_id = None
        super().tearDown()

    @patch('videos.scanner.threading.Thread')
    def test_new_library_is_queued_while_scan_is_active(self, thread_class):
        first = scanner.start_scan(['library-a'])
        second = scanner.start_scan(['library-b'])

        self.assertFalse(first['already_running'])
        self.assertTrue(second['already_running'])
        self.assertTrue(second['queued'])
        self.assertEqual(scanner._queued_library_ids, {'library-b'})
        thread_class.return_value.start.assert_called_once()
