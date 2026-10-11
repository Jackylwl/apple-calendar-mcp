"""Regression tests using a separately compiled backend with no EventKit access."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from client import Client, RPCError


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='calendar-tests-')
        cls.binary = Path(cls.build.name) / 'fixture-mcp'
        subprocess.run(['xcrun', 'swiftc', '-module-cache-path', cls.build.name + '/modules',
                        str(ROOT / 'server/CalendarCore.swift'), str(ROOT / 'server/CalendarMCP.swift'),
                        str(ROOT / 'tests/FixtureSource.swift'), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.state = tempfile.TemporaryDirectory(prefix='calendar-state-')
        self.addCleanup(self.state.cleanup)
        self.config = Path(self.state.name) / 'allowed-calendars.json'
        self.config.write_text('["fixture"]')
        self.env = {**os.environ, 'LOCAL_APPLE_CALENDAR_HOME': self.state.name}

    def client(self, scenario='empty'):
        c = Client([str(self.binary)], env={**self.env, 'CALENDAR_TEST_SCENARIO': scenario})
        self.addCleanup(c.close)
        return c

    def invoke(self, c, name='read_events', **args):
        if name != 'list_calendars':
            args = {'start': '2026-10-01T00:00:00+08:00', 'end': '2026-10-09T00:00:00+08:00', **args}
        return c.call('tools/call', {'name': name, 'arguments': args})

    def payload(self, value):
        self.assertFalse(value['isError'], value)
        return json.loads(value['content'][0]['text'])

    def test_catalog_and_unknown_write_tool(self):
        c = self.client()
        definitions = c.call('tools/list', {})['tools']
        self.assertEqual({x['name'] for x in definitions}, {'list_calendars', 'read_events', 'search_events'})
        self.assertTrue(all(x['annotations']['readOnlyHint'] and not x['annotations']['destructiveHint'] for x in definitions))
        with self.assertRaises(RPCError) as error:
            self.invoke(c, 'create_event')
        self.assertEqual(error.exception.code, -32602)

    def test_invalid_dates_do_not_reach_backend(self):
        c = self.client()
        for start in ['2026-02-30T00:00:00+08:00', '2026-10-01T24:00:00+08:00', '2026-10-01T00:60:00Z',
                      '2026-10-01T00:00:00', '2026-10-01T00:00:00+08:99', '2026-10-01T00:00:00Zjunk', '٢٠٢٦-10-01T00:00:00Z',
                      '2026-１０-01T00:00:00Z', '2026-10-01T00:00:00+٠٨:00']:
            with self.subTest(start=start):
                self.assertIn('INVALID_DATE', self.invoke(c, start=start)['content'][0]['text'])
        self.assertFalse((Path(self.state.name) / 'backend-called').exists())

    def test_fractional_seconds_and_valid_leap_day(self):
        c = self.client()
        for start, end in [('2026-10-01T00:00:00.123456789+08:00', '2026-10-02T00:00:00Z'),
                           ('2028-02-29T00:00:00Z', '2028-03-01T00:00:00Z')]:
            self.assertEqual(self.payload(self.invoke(c, start=start, end=end))['events'], [])

    def test_invalid_ranges_timezone_and_empty_search(self):
        c = self.client()
        for args, message in [({'end': '2026-10-01T00:00:00+08:00'}, 'INVALID_RANGE'),
                              ({'end': '2026-11-02T00:00:00+08:00'}, 'INVALID_RANGE'),
                              ({'timezone': 'Invalid/Zone'}, 'INVALID_TIMEZONE')]:
            self.assertIn(message, self.invoke(c, **args)['content'][0]['text'])
        self.assertIn('EMPTY_QUERY', self.invoke(c, 'search_events', query=' ')['content'][0]['text'])
        self.assertFalse((Path(self.state.name) / 'backend-called').exists())

    def test_empty_missing_and_malformed_config(self):
        c = self.client()
        for config in ['[]', None, '{']:
            if config is None:
                self.config.unlink()
            else:
                self.config.write_text(config)
            self.assertTrue(self.invoke(c)['isError'])
        self.assertFalse((Path(self.state.name) / 'backend-called').exists())

    def test_missing_calendar_and_denied_access(self):
        c = self.client()
        self.config.write_text('["gone"]')
        self.assertIn('CALENDAR_UNAVAILABLE', self.invoke(c)['content'][0]['text'])
        denied = self.client('denied')
        self.assertIn('CALENDAR_ACCESS_REQUIRED', self.invoke(denied)['content'][0]['text'])

    def test_all_day_inclusive_exclusive_and_cross_zone(self):
        c = self.client('all-day')
        for zone in ['Asia/Hong_Kong', 'America/Los_Angeles', 'Pacific/Kiritimati']:
            rows = self.payload(self.invoke(c, timezone=zone))['events']
            self.assertEqual(len(rows), 3)
            by_title = {x['title']: x for x in rows}
            self.assertEqual(by_title['Inclusive']['end'], '2026-10-02')
            self.assertEqual(by_title['Exclusive']['end'], '2026-10-02')
            self.assertEqual(by_title['Multi']['end'], '2026-10-04')
            self.assertTrue(all(x['start'] == '2026-10-01' for x in rows))

    def test_all_day_dst(self):
        rows = self.payload(self.invoke(self.client('dst'), start='2026-11-01T00:00:00-04:00',
                                      end='2026-11-02T00:00:00-05:00', timezone='America/New_York'))['events']
        self.assertEqual((rows[0]['start'], rows[0]['end']), ('2026-11-01', '2026-11-02'))

    def test_occurrences_search_boundaries_and_timezone(self):
        c = self.client('occurrences')
        rows = self.payload(self.invoke(c))['events']
        self.assertEqual([x['title'] for x in rows], ['Point', 'Sample meeting', 'Sample meeting'])
        rows = self.payload(self.invoke(c, 'search_events', query=' MEETING ', timezone='UTC'))['events']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['start'], '2026-10-01T02:00:00Z')
        self.assertEqual(self.payload(self.invoke(c, 'search_events', query='not present'))['events'], [])

    def test_cap_and_empty_result(self):
        result = self.payload(self.invoke(self.client('many')))
        self.assertEqual(len(result['events']), 500)
        self.assertEqual(result['total_count'], 502)
        self.assertTrue(result['truncated'])
        result = self.payload(self.invoke(self.client()))
        self.assertEqual(result['events'], [])
        self.assertFalse(result['truncated'])

    def test_bad_argument_shapes_do_not_dispatch(self):
        c = self.client()
        for arguments in [[], None, 'text', 42, {'include_notes': 'true'}]:
            with self.subTest(arguments=arguments), self.assertRaises(RPCError) as error:
                c.call('tools/call', {'name': 'list_calendars', 'arguments': arguments})
            self.assertEqual(error.exception.code, -32602)
        self.assertFalse((Path(self.state.name) / 'backend-called').exists())

    def test_parse_envelope_and_initialize_errors(self):
        inputs = ['{', '[]', 'null', json.dumps({'jsonrpc': '2.0', 'id': True, 'method': 'ping'}),
                  json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})]
        result = subprocess.run([str(self.binary)], input='\n'.join(inputs)+'\n', capture_output=True, text=True, env=self.env, timeout=5)
        self.assertEqual([json.loads(x)['error']['code'] for x in result.stdout.splitlines()], [-32700, -32600, -32600, -32600, -32602])


class ClientTests(unittest.TestCase):
    def test_initialization_failures_cleanup_child(self):
        real_popen = subprocess.Popen
        for script in ['import time; time.sleep(30)',
                       'import sys,time; sys.stdout.write("{"); sys.stdout.flush(); time.sleep(30)',
                       'import json,time; print(json.dumps({"id":1,"result":{"protocolVersion":"bad"}}),flush=True); time.sleep(30)']:
            children = []
            def spawn(*args, **kwargs):
                child = real_popen(*args, **kwargs)
                children.append(child)
                return child
            with self.subTest(script=script), patch('client.subprocess.Popen', side_effect=spawn):
                with self.assertRaises((TimeoutError, RuntimeError)):
                    Client([sys.executable, '-c', script], timeout=0.2)
            self.assertIsNotNone(children[0].poll())
            self.assertTrue(children[0].stdout.closed)
            self.assertTrue(children[0].stdin.closed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
